from __future__ import annotations

from typing import BinaryIO
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
)

from app.core.config import Settings, settings


class S3StorageError(Exception):
    """Safe, categorized S3 error. Never includes credentials or response payloads."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.public_message = message


class S3Storage:
    def __init__(self, config: Settings = settings):
        self.config = config
        self._client = None

    @property
    def bucket(self) -> str:
        if not self.config.S3_BUCKET_NAME:
            raise S3StorageError("bucket_not_configured", "S3 bucket is not configured.")
        return self.config.S3_BUCKET_NAME

    def qualify_key(self, key: str) -> str:
        """Place a new logical key inside the configured namespace."""
        key = key.strip("/")
        if not key or "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
            raise S3StorageError("invalid_object_key", "The document storage key is invalid.")
        prefix = self.config.S3_KEY_PREFIX
        if not prefix:
            return key
        if key == prefix or key.startswith(f"{prefix}/"):
            return key
        return f"{prefix}/{key}"

    def _require_scoped_key(self, key: str) -> str:
        """Reject reads, deletes, or URLs outside the configured prefix."""
        if not key or "\\" in key or key.startswith("/") or any(part in {"", ".", ".."} for part in key.split("/")):
            raise S3StorageError("invalid_object_key", "The document storage key is invalid.")
        prefix = self.config.S3_KEY_PREFIX
        if prefix and not key.startswith(f"{prefix}/"):
            raise S3StorageError("key_outside_prefix", "The document is outside the configured storage namespace.")
        return key

    def _s3(self):
        if self._client is not None:
            return self._client
        access_key = self.config.AWS_ACCESS_KEY_ID.get_secret_value() if self.config.AWS_ACCESS_KEY_ID else None
        secret_key = self.config.AWS_SECRET_ACCESS_KEY.get_secret_value() if self.config.AWS_SECRET_ACCESS_KEY else None
        session_token = self.config.AWS_SESSION_TOKEN.get_secret_value() if self.config.AWS_SESSION_TOKEN else None
        if bool(access_key) != bool(secret_key):
            raise S3StorageError("incomplete_credentials", "Configure both AWS access key values or use an IAM role/profile.")
        session = boto3.Session(
            region_name=self.config.AWS_REGION,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
        )
        try:
            self._client = session.client(
                "s3",
                region_name=self.config.AWS_REGION,
                config=Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=4,
                    read_timeout=10,
                ),
            )
        except (BotoCoreError, ValueError) as exc:
            raise S3StorageError("invalid_configuration", "AWS storage configuration is invalid.") from exc
        return self._client

    def credential_source(self) -> str | None:
        """Report only the SDK credential source, never credential values."""
        if self.config.AWS_ACCESS_KEY_ID and self.config.AWS_SECRET_ACCESS_KEY:
            return "application_configuration"
        try:
            credentials = boto3.Session(region_name=self.config.AWS_REGION).get_credentials()
            return credentials.method if credentials else None
        except (BotoCoreError, ValueError):
            return None

    @staticmethod
    def _raise_safe(exc: Exception, configured_region: str) -> None:
        if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
            raise S3StorageError("credentials_missing", "AWS credentials are missing or incomplete.") from exc
        if isinstance(exc, EndpointConnectionError):
            raise S3StorageError("network_unavailable", "Could not connect to the configured AWS S3 endpoint.") from exc
        if isinstance(exc, ClientError):
            response = exc.response
            error = response.get("Error", {})
            code = str(error.get("Code", "Unknown"))
            status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            headers = response.get("ResponseMetadata", {}).get("HTTPHeaders", {})
            actual_region = headers.get("x-amz-bucket-region")
            if code in {"InvalidAccessKeyId", "SignatureDoesNotMatch", "ExpiredToken", "InvalidToken", "AuthFailure"}:
                category, message = "invalid_credentials", "AWS rejected the configured credentials."
            elif code in {"NoSuchBucket", "NotFound"} or status == 404:
                category, message = "bucket_not_found", "The configured S3 bucket was not found."
            elif code in {"PermanentRedirect", "IncorrectEndpoint", "AuthorizationHeaderMalformed", "IllegalLocationConstraintException"} or (actual_region and actual_region != configured_region):
                category, message = "region_mismatch", "The S3 bucket region does not match AWS_REGION."
            elif code in {"AccessDenied", "AllAccessDisabled", "403"} or status == 403:
                category, message = "missing_permissions", "AWS denied access; check the IAM policy and bucket permissions."
            elif code in {"SlowDown", "ServiceUnavailable", "InternalError"} or (status and status >= 500):
                category, message = "aws_unavailable", "Amazon S3 is temporarily unavailable."
            else:
                category, message = "aws_request_failed", "The S3 request could not be completed."
            raise S3StorageError(category, message) from exc
        if isinstance(exc, BotoCoreError):
            raise S3StorageError("aws_client_error", "The AWS SDK could not complete the S3 request.") from exc
        raise S3StorageError("storage_error", "The storage operation could not be completed.") from exc

    def _call(self, operation: str, **kwargs):
        try:
            return getattr(self._s3(), operation)(**kwargs)
        except S3StorageError:
            raise
        except Exception as exc:
            self._raise_safe(exc, self.config.AWS_REGION)

    def upload_fileobj(self, source: BinaryIO, key: str, content_type: str, filename: str) -> None:
        key = self._require_scoped_key(self.qualify_key(key))
        safe_filename = quote(filename, safe="")
        self._call(
            "upload_fileobj",
            Fileobj=source,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={
                "ContentType": content_type,
                "ContentDisposition": f"attachment; filename*=UTF-8''{safe_filename}",
                "Metadata": {"storage-format": "private-medical-document-v1"},
            },
        )

    def download_file(self, key: str, destination: str) -> None:
        """Download an authorized private object to a worker-owned temporary path."""
        key = self._require_scoped_key(key)
        self._call("download_file", Bucket=self.bucket, Key=key, Filename=destination)

    def delete_object(self, key: str) -> None:
        key = self._require_scoped_key(key)
        self._call("delete_object", Bucket=self.bucket, Key=key)

    def presigned_url(self, key: str, filename: str, content_type: str, inline: bool) -> str:
        key = self._require_scoped_key(key)
        disposition = "inline" if inline else "attachment"
        encoded_name = quote(filename, safe="")
        try:
            return self._s3().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition": f"{disposition}; filename*=UTF-8''{encoded_name}",
                },
                ExpiresIn=self.config.S3_PRESIGNED_URL_EXPIRES_SECONDS,
                HttpMethod="GET",
            )
        except S3StorageError:
            raise
        except Exception as exc:
            self._raise_safe(exc, self.config.AWS_REGION)

    def verify_bucket(self) -> dict:
        """Read bucket access and exposure settings. This method never changes them."""
        client = self._s3()
        self._call("head_bucket", Bucket=self.bucket)
        checks: dict[str, bool | None] = {
            "block_public_acls": None,
            "ignore_public_acls": None,
            "block_public_policy": None,
            "restrict_public_buckets": None,
            "policy_is_public": None,
            "public_acl_grant_found": None,
        }
        unverified: list[str] = []
        try:
            response = client.get_public_access_block(Bucket=self.bucket)
            settings = response["PublicAccessBlockConfiguration"]
            setting_names = {
                "BlockPublicAcls": "block_public_acls",
                "IgnorePublicAcls": "ignore_public_acls",
                "BlockPublicPolicy": "block_public_policy",
                "RestrictPublicBuckets": "restrict_public_buckets",
            }
            for aws_name, check_name in setting_names.items():
                checks[check_name] = bool(settings.get(aws_name))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "NoSuchPublicAccessBlockConfiguration":
                for name in ("block_public_acls", "ignore_public_acls", "block_public_policy", "restrict_public_buckets"):
                    checks[name] = False
            else:
                unverified.append("public_access_block")
        except BotoCoreError:
            unverified.append("public_access_block")
        try:
            checks["policy_is_public"] = bool(client.get_bucket_policy_status(Bucket=self.bucket)["PolicyStatus"]["IsPublic"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchBucketPolicy":
                checks["policy_is_public"] = False
            else:
                unverified.append("bucket_policy")
        except BotoCoreError:
            unverified.append("bucket_policy")
        try:
            grants = client.get_bucket_acl(Bucket=self.bucket).get("Grants", [])
            public_uris = {
                "http://acs.amazonaws.com/groups/global/AllUsers",
                "http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
            }
            checks["public_acl_grant_found"] = any(
                grant.get("Grantee", {}).get("URI") in public_uris for grant in grants
            )
        except ClientError:
            unverified.append("bucket_acl")
        except BotoCoreError:
            unverified.append("bucket_acl")

        required_block_flags = ("block_public_acls", "ignore_public_acls", "block_public_policy", "restrict_public_buckets")
        private_verified = (
            not unverified
            and all(checks[key] is True for key in required_block_flags)
            and checks["policy_is_public"] is False
            and checks["public_acl_grant_found"] is False
        )
        return {
            "bucket_accessible": True,
            "private_configuration_verified": private_verified,
            "checks": checks,
            "unverified_checks": unverified,
        }


def get_s3_storage() -> S3Storage:
    return S3Storage()
