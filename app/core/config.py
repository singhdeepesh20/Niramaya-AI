from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings sourced from the environment or local .env file."""

    DATABASE_URL: str
    JWT_SECRET_KEY: SecretStr = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, gt=0, le=1440)
    JWT_ISSUER: str | None = None
    JWT_AUDIENCE: str | None = None
    FRONTEND_ORIGINS: list[str] = Field(default_factory=list)
    LLM_API_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_TIMEOUT_SECONDS: float = Field(default=20, gt=0, le=120)
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: SecretStr | None = None
    QDRANT_COLLECTION: str = "niramaya_medical_chunks"
    HEALTH_RETRIEVAL_LIMIT: int = Field(default=8, ge=1, le=30)
    HEALTH_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("DATABASE_URL must not be empty")
        if not value.startswith(("postgresql+asyncpg://", "postgresql+psycopg://", "sqlite+aiosqlite://")):
            raise ValueError("DATABASE_URL must use an async PostgreSQL driver or sqlite+aiosqlite")
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 UTF-8 bytes")
        if len(set(secret)) < 8 or any(marker in secret.lower() for marker in ("replace", "changeme", "your_secret")):
            raise ValueError("JWT_SECRET_KEY must be a strong, randomly generated secret")
        return value

    @field_validator("JWT_ISSUER", "JWT_AUDIENCE", mode="before")
    @classmethod
    def empty_optional_claims_are_none(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("FRONTEND_ORIGINS")
    @classmethod
    def validate_frontend_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            origin = origin.strip().rstrip("/")
            parsed = urlsplit(origin)
            local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if (
                not origin
                or origin == "*"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or (parsed.scheme != "https" and not local_http)
            ):
                raise ValueError("FRONTEND_ORIGINS must contain explicit HTTPS or localhost origins")
            normalized.append(origin)
        return list(dict.fromkeys(normalized))

    @field_validator("LLM_API_BASE_URL", "QDRANT_URL")
    @classmethod
    def validate_service_url(cls, value: str | None, info) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError(f"{info.field_name} must be an HTTP(S) URL without embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError(f"{info.field_name} must not contain a query or fragment")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(f"{info.field_name} must use HTTPS outside localhost")
        return normalized

    @field_validator("LLM_API_KEY", "QDRANT_API_KEY", mode="before")
    @classmethod
    def empty_provider_secrets_are_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
