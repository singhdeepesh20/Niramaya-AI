import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.rate_limit import LoginRateLimiter
from app.core.security import verify_password
from app.database import get_db
from app.user.dtos import LoginRequest, RegistrationRequest
from app.user.models import User

PASSWORD = "A-long-example-passphrase-123"


def register(client, *, username="deepesh", email="deepesh@example.com", password=PASSWORD):
    return client.post(
        "/api/v1/users/register",
        json={"username": username, "email": email, "password": password},
    )


def login(client, *, username="deepesh", password=PASSWORD):
    return client.post("/api/v1/users/login", json={"username": username, "password": password})


def register_then_login(client, username="deepesh", email="deepesh@example.com"):
    response = register(client, username=username, email=email)
    assert response.status_code == 201
    token_response = login(client, username=username)
    assert token_response.status_code == 200
    return response.json(), token_response.json()["access_token"]


def test_registration_returns_safe_profile_and_normalizes_identifiers(client):
    response = register(client, username="  Deepesh_1 ", email=" DEEPESH@EXAMPLE.COM ")

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "deepesh_1"
    assert body["email"] == "deepesh@example.com"
    assert body["is_active"] is True
    assert UUID(body["id"])
    assert "hashed_password" not in body
    assert "password" not in body


def test_registration_password_is_hashed_in_database(client):
    response = register(client)
    user_id = UUID(response.json()["id"])
    factory = client.app.state.test_session_factory

    async def read_user():
        async with factory() as session:
            return await session.get(User, user_id)

    user = asyncio.run(read_user())
    assert user.hashed_password != PASSWORD
    assert verify_password(PASSWORD, user.hashed_password)


def test_registration_rejects_missing_fields(client):
    response = client.post("/api/v1/users/register", json={"username": "deepesh"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("username", ["", "   ", "ab", "a" * 31, "has space", "bad-name"])
def test_registration_rejects_invalid_username(client, username):
    response = register(client, username=username)
    assert response.status_code == 422


@pytest.mark.parametrize("email", ["not-an-email", "", "a@b", "x" * 320 + "@example.com"])
def test_registration_rejects_invalid_email(client, email):
    response = register(client, email=email)
    assert response.status_code == 422


@pytest.mark.parametrize("password", ["", "short", "p" * 129])
def test_registration_rejects_out_of_range_password(client, password):
    response = register(client, password=password)
    assert response.status_code == 422


def test_validation_errors_never_echo_password_values(client):
    response = client.post(
        "/api/v1/users/register",
        json={"username": "x", "email": "bad", "password": "sensitive-value"},
    )
    assert response.status_code == 422
    assert "sensitive-value" not in response.text
    assert "input" not in response.text


def test_credential_schema_string_representations_are_redacted():
    registration = RegistrationRequest(username="deepesh", email="deepesh@example.com", password=PASSWORD)
    login_payload = LoginRequest(username="deepesh", password=PASSWORD)
    assert PASSWORD not in repr(registration)
    assert PASSWORD not in str(registration)
    assert PASSWORD not in repr(login_payload)
    assert PASSWORD not in str(login_payload)


def test_registration_rejects_case_insensitive_duplicate_username(client):
    assert register(client).status_code == 201
    response = register(client, username="DEEPESH", email="other@example.com")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_conflict"


def test_registration_rejects_duplicate_normalized_email(client):
    assert register(client).status_code == 201
    response = register(client, username="other_user", email="DEEPESH@EXAMPLE.COM")
    assert response.status_code == 409


def test_login_returns_signed_token_and_actual_expiry(client):
    profile = register(client).json()
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    claims = jwt.decode(
        body["access_token"],
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
        options={"verify_aud": False},
    )
    assert claims["sub"] == profile["id"]
    assert "iat" in claims and "exp" in claims


def test_login_uses_generic_error_for_unknown_user_and_wrong_password(client):
    unknown = login(client, username="missing_user")
    assert unknown.status_code == 401
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    register(client)
    wrong_password = login(client, password="Another-long-passphrase-123")
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_login_rejects_inactive_account(client):
    profile = register(client).json()
    factory = client.app.state.test_session_factory

    async def deactivate():
        async with factory() as session:
            user = await session.get(User, UUID(profile["id"]))
            user.is_active = False
            await session.commit()

    asyncio.run(deactivate())
    response = login(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_login_rejects_malformed_body(client):
    response = client.post("/api/v1/users/login", json={"username": "deepesh"})
    assert response.status_code == 422


def test_login_rate_limit_returns_retry_after(client):
    client.app.state.login_rate_limiter = LoginRateLimiter(max_attempts=2, window_seconds=60)
    login(client, username="missing")
    login(client, username="missing")
    response = login(client, username="missing")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_current_user_requires_bearer_token(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_malformed_and_tampered_tokens(client):
    for token in ("not-a-jwt", "a.b.c"):
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    _, token = register_then_login(client)
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{header}.{payload}.{replacement}{signature[1:]}"
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered}"})
    assert response.status_code == 401


def test_current_user_rejects_expired_tokens(client):
    profile, _ = register_then_login(client)
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {"sub": profile["id"], "iat": now - timedelta(minutes=2), "exp": now - timedelta(minutes=1)},
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_current_user_rejects_token_signed_with_disallowed_algorithm(client):
    profile, _ = register_then_login(client)
    now = datetime.now(timezone.utc)
    invalid_algorithm = jwt.encode(
        {"sub": profile["id"], "iat": now, "exp": now + timedelta(minutes=5)},
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS512",
    )
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {invalid_algorithm}"})
    assert response.status_code == 401


def test_me_returns_only_authenticated_users_profile(client):
    profile, token = register_then_login(client)
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == profile["id"]
    assert "hashed_password" not in response.json()


def test_me_ignores_client_supplied_identity(client):
    first, token = register_then_login(client)
    register(client, username="second_user", email="second@example.com")
    response = client.get(
        f"/api/v1/users/me?user_id={UUID(int=1)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == first["id"]


def test_current_user_rejects_deleted_account(client):
    profile, token = register_then_login(client)
    factory = client.app.state.test_session_factory

    async def delete_user():
        async with factory() as session:
            user = await session.get(User, UUID(profile["id"]))
            await session.delete(user)
            await session.commit()

    asyncio.run(delete_user())
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_current_user_rejects_inactive_account(client):
    profile, token = register_then_login(client)
    factory = client.app.state.test_session_factory

    async def deactivate():
        async with factory() as session:
            user = await session.get(User, UUID(profile["id"]))
            user.is_active = False
            await session.commit()

    asyncio.run(deactivate())
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


def test_request_id_is_returned_for_correlation(client):
    response = client.get("/health", headers={"X-Request-ID": "support-ticket-42"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "support-ticket-42"


def test_untrusted_request_id_is_replaced(client):
    untrusted_id = "x" * 65
    response = client.get("/health", headers={"X-Request-ID": untrusted_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != untrusted_id


def test_database_failure_during_registration_returns_503(client):
    async def broken_db():
        raise OperationalError("query", {}, OSError("database offline"))
        yield  # Keeps this dependency an async generator.

    client.app.dependency_overrides[get_db] = broken_db
    response = register(client)
    assert response.status_code == 503
    assert "database offline" not in response.text


def test_registration_commit_failure_rolls_back_and_redacts_database_error(client, caplog):
    factory = client.app.state.test_session_factory
    sync_engine = factory.kw["bind"].sync_engine

    def fail_user_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO USERS"):
            raise OperationalError(statement, parameters, OSError("sensitive database detail"))

    event.listen(sync_engine, "before_cursor_execute", fail_user_insert)
    try:
        response = register(client)
    finally:
        event.remove(sync_engine, "before_cursor_execute", fail_user_insert)

    assert response.status_code == 503
    assert "sensitive database detail" not in response.text
    assert "sensitive database detail" not in caplog.text

    async def count_users():
        async with factory() as session:
            return await session.scalar(select(func.count()).select_from(User))

    assert asyncio.run(count_users()) == 0


def test_database_failure_during_login_returns_503(client):
    async def broken_db():
        raise OperationalError("query", {}, OSError("database offline"))
        yield

    client.app.dependency_overrides[get_db] = broken_db
    response = login(client)
    assert response.status_code == 503
