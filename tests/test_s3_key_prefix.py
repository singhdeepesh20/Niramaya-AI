from types import SimpleNamespace

import pytest

from app.storage.s3 import S3Storage, S3StorageError


def test_staging_prefix_is_applied_once_and_allows_scoped_keys():
    storage = S3Storage(SimpleNamespace(S3_KEY_PREFIX="niramaya-staging"))
    logical_key = "users/user-id/documents/document-id"

    key = storage.qualify_key(logical_key)

    assert key == "niramaya-staging/users/user-id/documents/document-id"
    assert storage.qualify_key(key) == key
    assert storage._require_scoped_key(key) == key


@pytest.mark.parametrize("key", ["users/a/documents/b", "niramaya-staging/../outside", "/niramaya-staging/object"])
def test_staging_prefix_rejects_unscoped_or_traversal_keys(key: str):
    storage = S3Storage(SimpleNamespace(S3_KEY_PREFIX="niramaya-staging"))

    with pytest.raises(S3StorageError):
        storage._require_scoped_key(key)


def test_empty_prefix_preserves_legacy_key_layout():
    storage = S3Storage(SimpleNamespace(S3_KEY_PREFIX=""))

    assert storage.qualify_key("users/a/documents/b") == "users/a/documents/b"
    assert storage._require_scoped_key("users/a/documents/b") == "users/a/documents/b"
