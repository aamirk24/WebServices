from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.limiter import limiter
from crud.users import create_user, get_user_by_email, get_user_by_id, get_user_by_username
from models.user import APIKey, User

from schemas.auth import (
    APIKeyCreate,
    APIKeyListItem,
    APIKeyResponse,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
)

from services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_password,
)


router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def register(
    request: Request,
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    existing_email = await get_user_by_email(db, user_create.email)
    if existing_email is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    existing_username = await get_user_by_username(db, user_create.username)
    if existing_username is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken",
        )

    user = await create_user(db, user_create)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("60/minute")
async def login(
    request: Request,
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
@limiter.limit("60/minute")
async def refresh_access_token(
    request: Request,
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
@limiter.limit("60/minute")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    Return the currently authenticated active user.

    This endpoint is protected by bearer-token authentication and is useful
    for verifying that JWT-based auth works end-to-end.
    """
    return current_user


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("60/minute")
async def create_api_key(
    request: Request,
    api_key_create: APIKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """
    Create a new API key for the authenticated user.

    The raw API key is returned exactly once in this response and is never
    stored in plain text. Only its SHA-256 hash is stored in the database.
    """
    raw_key, key_hash = generate_api_key()

    api_key = APIKey(
        name=api_key_create.name,
        key_hash=key_hash,
        user_id=current_user.id,
        scopes=api_key_create.scopes,
        is_active=True,
    )

    db.add(api_key)
    await db.commit()

    return APIKeyResponse(
        name=api_key.name,
        key=raw_key,
    )


@router.get(
    "/api-keys",
    response_model=list[APIKeyListItem],
)
@limiter.limit("60/minute")
async def list_api_keys(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[APIKeyListItem]:
    """
    List API keys for the authenticated user.

    Returns metadata only. The raw key and stored key hash are never exposed.
    """
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == current_user.id)
        .order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()
    return list(api_keys)


@router.delete(
    "/api-keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("60/minute")
async def revoke_api_key(
    request: Request,
    api_key_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Revoke an API key owned by the authenticated user.

    This marks the key as inactive so it can no longer be used.
    """
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == api_key_id,
            APIKey.user_id == current_user.id,
        )
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)