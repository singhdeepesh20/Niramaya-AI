from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.csrf import generate_csrf_token
from app.database import get_db
from app.user.controller import get_current_user, login_user, logout_user, register_user
from app.user.dtos import CSRFResponse, LoginRequest, RegistrationRequest, TokenResponse, UserPublic
from app.user.models import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])


async def enforce_login_rate_limit(request: Request) -> None:
    """Rate-limit by client IP; use a shared Redis-backed limiter across workers."""
    client_ip = request.client.host if request.client else "unknown"
    await request.app.state.login_rate_limit.check(client_ip) if hasattr(request.app.state, "login_rate_limit") else await request.app.state.login_rate_limiter.check(client_ip)


@router.get("/csrf", response_model=CSRFResponse)
async def get_csrf(response: Response) -> CSRFResponse:
    """Issue a fresh CSRF token and set the matching double-submit cookie."""
    token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    return CSRFResponse(csrf_token=token)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await register_user(payload, db)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(enforce_login_rate_limit)])
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    return await login_user(payload, db, response)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Invalidate session by clearing authentication and CSRF cookies."""
    return logout_user(response)


@router.get("/me", response_model=UserPublic)
async def read_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user

