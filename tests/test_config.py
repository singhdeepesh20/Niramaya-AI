import pytest
from pydantic import ValidationError

from app.core.config import Settings

SECRET = "test-secret-with-enough-random-looking-characters-123456"


def settings(**overrides):
    values = {
        "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/db",
        "JWT_SECRET_KEY": SECRET,
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
        "FRONTEND_ORIGINS": [],
    }
    values.update(overrides)
    return Settings(**values)


def test_settings_reject_weak_jwt_secret():
    with pytest.raises(ValidationError):
        settings(JWT_SECRET_KEY="short")


def test_settings_reject_unsupported_jwt_algorithm():
    with pytest.raises(ValidationError):
        settings(JWT_ALGORITHM="none")


def test_settings_bound_token_lifetime():
    with pytest.raises(ValidationError):
        settings(ACCESS_TOKEN_EXPIRE_MINUTES=0)
    with pytest.raises(ValidationError):
        settings(ACCESS_TOKEN_EXPIRE_MINUTES=1441)


def test_settings_reject_wildcard_cors_origin():
    with pytest.raises(ValidationError):
        settings(FRONTEND_ORIGINS=["*"])


def test_settings_allow_unique_https_and_local_origins():
    configured = settings(FRONTEND_ORIGINS=["https://app.example.com", "http://localhost:3000/"])
    assert configured.FRONTEND_ORIGINS == ["https://app.example.com", "http://localhost:3000"]
