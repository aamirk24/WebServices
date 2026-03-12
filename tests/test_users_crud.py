import uuid

import pytest
from sqlalchemy import delete

from app.database import AsyncSessionLocal
from crud.users import create_user, get_user_by_email, get_user_by_id
from schemas.auth import UserCreate
from services.auth import verify_password
from models.user import User


@pytest.mark.asyncio
async def test_create_user_and_fetch_by_email_and_id():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    username = f"user_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as db:
        created_user = await create_user(
            db,
            UserCreate(
                username=username,
                email=email,
                password="test12345",
            ),
        )

        fetched_by_email = await get_user_by_email(db, email)
        fetched_by_id = await get_user_by_id(db, created_user.id)

        assert created_user.id is not None
        assert created_user.email == email
        assert created_user.username == username
        assert created_user.hashed_password != "test12345"
        assert verify_password("test12345", created_user.hashed_password)

        assert fetched_by_email is not None
        assert fetched_by_email.id == created_user.id
        assert fetched_by_email.email == email

        assert fetched_by_id is not None
        assert fetched_by_id.id == created_user.id
        assert fetched_by_id.username == username

        # Cleanup so repeated test runs don't keep adding rows
        await db.execute(delete(User).where(User.id == created_user.id))
        await db.commit()