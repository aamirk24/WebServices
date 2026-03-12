from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from schemas.auth import UserCreate
from services.auth import hash_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    user = User(
        username=user_create.username,
        email=user_create.email,
        hashed_password=hash_password(user_create.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user