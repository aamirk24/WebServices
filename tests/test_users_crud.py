import uuid

import pytest

from crud.users import create_user, get_user_by_email, get_user_by_id
from schemas.auth import UserCreate


@pytest.mark.asyncio
async def test_create_user_and_fetch_by_email_and_id(test_db):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    username = f"user_{uuid.uuid4().hex[:8]}"

    created_user = await create_user(
        test_db,
        UserCreate(
            username=username,
            email=email,
            password="test12345",
        ),
    )

    fetched_by_email = await get_user_by_email(test_db, email)
    fetched_by_id = await get_user_by_id(test_db, created_user.id)

    assert created_user.email == email
    assert created_user.username == username

    assert fetched_by_email is not None
    assert fetched_by_email.id == created_user.id

    assert fetched_by_id is not None
    assert fetched_by_id.id == created_user.id