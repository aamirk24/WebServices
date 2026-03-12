from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from crud.users import get_user_by_id
from models.user import User
from services.auth import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        user = await get_user_by_id(db, uuid.UUID(user_id))
        if user is None:
            raise credentials_exception

        return user
    except (ValueError, TypeError):
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )
    return current_user