from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.csrf import generate_csrf_token
from app.core.errors import APIError
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, hash_password, verify_password
from app.database import get_db
from app.user.dtos import LoginRequest, RegistrationRequest, TokenResponse
from app.user.models import User

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def _is_unique_violation(exc: IntegrityError) -> bool:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate == "23505":
        return True
    message = str(original).lower()
    return "unique constraint failed" in message or "duplicate key value violates unique constraint" in message


async def register_user(payload: RegistrationRequest, db: AsyncSession) -> User:
    try:
        existing_id = await db.scalar(
            select(User.id).where(or_(User.username == payload.username, User.email == str(payload.email)))
        )
        if existing_id is not None:
            await db.rollback()
            raise APIError(409, "account_conflict", "An account with those credentials already exists.")

        user = User(
            username=payload.username,
            email=str(payload.email),
            hashed_password=hash_password(payload.password),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except APIError:
        raise
    except IntegrityError as exc:
        await db.rollback()
        if _is_unique_violation(exc):
            raise APIError(409, "account_conflict", "An account with those credentials already exists.") from exc
        raise
    except SQLAlchemyError:
        await db.rollback()
        raise
    return user


async def login_user(payload: LoginRequest, db: AsyncSession, response: Response | None = None) -> TokenResponse:
    user = await db.scalar(select(User).where(User.username == payload.username))
    stored_hash = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, stored_hash)
    if user is None or not password_valid:
        raise APIError(
            401,
            "invalid_credentials",
            "Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise APIError(403, "account_inactive", "This account is inactive.")

    token, expires_in = create_access_token(user.id)
    csrf_token = generate_csrf_token()

    if response is not None:
        response.set_cookie(
            key=settings.COOKIE_NAME,
            value=token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path="/",
            domain=settings.COOKIE_DOMAIN,
            max_age=expires_in,
        )
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=csrf_token,
            httponly=False,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            path="/",
            domain=settings.COOKIE_DOMAIN,
            max_age=expires_in,
        )

    return TokenResponse(access_token=token, expires_in=expires_in, csrf_token=csrf_token)


def logout_user(response: Response) -> dict[str, str]:
    response.delete_cookie(key=settings.COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/", domain=settings.COOKIE_DOMAIN)
    return {"message": "Logged out successfully."}


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    raw_token: str | None = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    elif request is not None:
        raw_token = request.cookies.get(settings.COOKIE_NAME)

    if not raw_token:
        raise APIError(
            401,
            "authentication_required",
            "A valid bearer token or session cookie is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    required_claims = ["sub", "iat", "exp"]
    decode_options: dict[str, object] = {"require": required_claims, "verify_aud": bool(settings.JWT_AUDIENCE)}
    if settings.JWT_ISSUER:
        required_claims.append("iss")
    if settings.JWT_AUDIENCE:
        required_claims.append("aud")
    try:
        claims = jwt.decode(
            raw_token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options=decode_options,
        )
        subject = UUID(claims["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise APIError(
            401,
            "invalid_token",
            "The bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await db.get(User, subject)
    if user is None:
        raise APIError(
            401,
            "invalid_token",
            "The bearer token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise APIError(403, "account_inactive", "This account is inactive.")
    return user
