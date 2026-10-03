from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_current_user
from app.db.models import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    # This demo has no roles or sharing model, so users can only read their own profile.
    if current_user.id != user_id:
        raise HTTPException(status_code=404, detail="User not found")
    return current_user
