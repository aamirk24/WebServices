from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from crud.users import create_user, get_user_by_email, get_user_by_id
from schemas.auth import RefreshTokenRequest, Token, UserCreate, UserResponse
from services.auth import create_access_token, create_refresh_token, verify_password, decode_token

from app.dependencies import get_current_active_user
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Register a new user account.

    Validates that the email is not already in use, hashes the password,
    creates the user in the database, and returns the created user without
    exposing any password fields.
    """
    existing_user = await get_user_by_email(db, user_create.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    user = await create_user(db, user_create)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Authenticate a user and issue JWT tokens.

    Expects OAuth2 form data where the `username` field should contain the
    user's email address and the `password` field contains the plain-text
    password. Returns both an access token and a refresh token on success.
    """
    user = await get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    token_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Exchange a valid refresh token for a new access token.

    Accepts a refresh token in the request body, validates that it is a
    refresh token belonging to an existing active user, and returns a new
    access token along with the same refresh token.
    """
    try:
        payload = decode_token(token_data.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access_token = create_access_token({"sub": str(user.id)})

    return Token(
        access_token=new_access_token,
        refresh_token=token_data.refresh_token,
        token_type="bearer",
    )

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Return the currently authenticated active user.

    This endpoint is protected by bearer-token authentication and is useful
    for verifying that JWT-based auth works end-to-end.
    """
    return current_user