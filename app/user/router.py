from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import LoginRateLimiter
from app.database import get_db
from app.user.controller import get_current_user, login_user, register_user
from app.user.dtos import LoginRequest, RegistrationRequest, TokenResponse, UserPublic
from app.user.models import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


async def enforce_login_rate_limit(request: Request) -> None:
    """Rate-limit by client IP; use a shared Redis-backed limiter across workers."""
    client_ip = request.client.host if request.client else "unknown"
    await request.app.state.login_rate_limiter.check(client_ip)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await register_user(payload, db)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(enforce_login_rate_limit)])
async def login(
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await login_user(payload, db)


@router.get("/me", response_model=UserPublic)
async def read_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user
