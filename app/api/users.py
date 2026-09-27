from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    try:
        existing = await db.scalar(select(User).where(User.email == payload.email))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
    if existing is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    user = User(name=payload.name, email=str(payload.email))
    db.add(user)  # Stage the INSERT in the session's unit of work.
    try:
        await db.commit()  # Send pending changes in a transaction to PostgreSQL.
        await db.refresh(user)  # Load server-generated id and created_at values.
    except IntegrityError as exc:
        await db.rollback()
        # The unique database constraint also protects against two simultaneous requests.
        if getattr(exc.orig, "constraint_name", "") in {"ix_users_email", "users_email_key"}:
            raise HTTPException(status_code=409, detail="A user with this email already exists") from exc
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    try:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Database operation failed") from exc
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
