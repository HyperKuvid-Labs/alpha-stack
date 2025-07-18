from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from karyaksham_api.api.deps import get_async_db
from karyaksham_api.auth.security import (
    get_current_active_admin_user,
    get_current_active_user,
    get_password_hash,
)
from karyaksham_api.crud.crud_user import user_crud
from karyaksham_api.schemas import user as user_schemas
from karyaksham_api.db.models.user import User as DBUser

router = APIRouter()


@router.get("/me", response_model=user_schemas.UserResponse, summary="Get current user details")
async def read_current_user(
    current_user: DBUser = Depends(get_current_active_user),
) -> DBUser:
    """
    Retrieve details of the current authenticated user.

    Requires authentication.
    """
    return current_user


@router.put("/me", response_model=user_schemas.UserResponse, summary="Update current user details")
async def update_current_user(
    user_in: user_schemas.UserUpdate,
    current_user: DBUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> DBUser:
    """
    Update details of the current authenticated user.

    Allows updating fields like `full_name`, `email`, and `password`.
    If `password` is provided, it will be hashed.
    Requires authentication.
    """
    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data and user_data["password"]:
        user_data["hashed_password"] = get_password_hash(user_data["password"])
        del user_data["password"]  # Remove plaintext password from input data

    # Check for email conflict if email is being updated to a different one
    if "email" in user_data and user_data["email"] != current_user.email:
        existing_user_with_new_email = await user_crud.get_by_email(db, email=user_data["email"])
        if existing_user_with_new_email and existing_user_with_new_email.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )

    updated_user = await user_crud.update(db, db_obj=current_user, obj_in=user_data)
    return updated_user


@router.get("/", response_model=List[user_schemas.UserResponse], summary="Retrieve multiple users (Admin only)")
async def read_users(
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    current_user: DBUser = Depends(get_current_active_admin_user),  # Requires admin role
) -> List[DBUser]:
    """
    Retrieve a list of users with pagination.

    Requires administrator privileges.
    """
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users


@router.post("/", response_model=user_schemas.UserResponse, status_code=status.HTTP_201_CREATED, summary="Create new user (Admin only)")
async def create_user(
    user_in: user_schemas.UserCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: DBUser = Depends(get_current_active_admin_user),  # Requires admin role
) -> DBUser:
    """
    Create a new user.

    Checks if a user with the given email already exists.
    Requires administrator privileges.
    """
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    new_user = await user_crud.create(db, obj_in=user_in)
    return new_user


@router.get("/{user_id}", response_model=user_schemas.UserResponse, summary="Get user by ID (Admin only)")
async def read_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: DBUser = Depends(get_current_active_admin_user),  # Requires admin role
) -> DBUser:
    """
    Retrieve a user by their unique ID.

    Requires administrator privileges.
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/{user_id}", response_model=user_schemas.UserResponse, summary="Update user by ID (Admin only)")
async def update_user_by_id(
    user_id: UUID,
    user_in: user_schemas.UserUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: DBUser = Depends(get_current_active_admin_user),  # Requires admin role
) -> DBUser:
    """
    Update details for a specific user by their ID.

    If `password` is provided, it will be hashed.
    Requires administrator privileges.
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data and user_data["password"]:
        user_data["hashed_password"] = get_password_hash(user_data["password"])
        del user_data["password"]

    # If email is updated, check for conflicts with other users
    if "email" in user_data and user_data["email"] != user.email:
        existing_user_with_new_email = await user_crud.get_by_email(db, email=user_data["email"])
        if existing_user_with_new_email and existing_user_with_new_email.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists.",
            )

    updated_user = await user_crud.update(db, db_obj=user, obj_in=user_data)
    return updated_user


@router.delete("/{user_id}", response_model=user_schemas.UserResponse, summary="Delete user by ID (Admin only)")
async def delete_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: DBUser = Depends(get_current_active_admin_user),  # Requires admin role
) -> DBUser:
    """
    Delete a user by their unique ID.

    Requires administrator privileges.
    """
    deleted_user = await user_crud.remove(db, id=user_id)
    if not deleted_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return deleted_user