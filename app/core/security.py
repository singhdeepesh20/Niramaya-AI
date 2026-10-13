from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()
# A process-local dummy hash keeps unknown-user login attempts doing Argon2 work too.
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(subject: UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    claims: dict[str, object] = {
        "sub": str(subject),
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if settings.JWT_ISSUER:
        claims["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        claims["aud"] = settings.JWT_AUDIENCE
    token = jwt.encode(
        claims,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires_in
