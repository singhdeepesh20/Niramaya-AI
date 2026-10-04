from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.core.identifiers import normalize_username
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import TokenResponse, UserRegister
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    email = str(payload.email).lower()
    try:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        existing_username = await db.scalar(
            select(User).where(User.username == normalize_username(payload.username))
        )
        if existing_username is not None:
            raise HTTPException(status_code=409, detail="This username is already taken")
        user = User(
            name=payload.name.strip(),
            username=normalize_username(payload.username),
            email=email,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except HTTPException:
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database operation failed") from exc


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == form.username.strip().lower()))
    valid = user is not None and user.password_hash is not None and verify_password(form.password, user.password_hash)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserResponse)
async def read_current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
