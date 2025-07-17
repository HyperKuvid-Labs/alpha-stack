from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.v1.dependencies import get_db
from app.api.v1.schemas import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.db.models.user import User
from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.auth.security import hash_password # Assumed to exist for password hashing

router = APIRouter(prefix="/users", tags=["users"])

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Admin only)",
    description="Allows an admin user to create a new user account with specified details, including password hashing. Ensures email uniqueness."
)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user) # Requires admin privileges
):
    """
    Creates a new user in the database.
    
    Args:
        user_in (UserCreate): The Pydantic model containing the new user's details.
        db (Session): Database session dependency.
        current_user (User): The authenticated admin user (dependency).

    Returns:
        UserResponse: The newly created user's details, excluding sensitive information.

    Raises:
        HTTPException 409: If a user with the provided email already exists.
        HTTPException 500: For other database integrity errors.
    """
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The user with this email already exists in the system.",
        )

    hashed_password = hash_password(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        is_admin=user_in.is_admin,
    )
    db.add(db_user)
    try:
        db.commit()
        db.refresh(db_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Could not create user. Check unique constraints or other issues."
        )
    return db_user

@router.get(
    "/",
    response_model=UserListResponse,
    summary="Retrieve a list of all users (Admin only)",
    description="Fetches a paginated list of all users available in the system. Requires admin privileges.",
)
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user) # Requires admin privileges
):
    """
    Retrieves a list of all users with pagination.
    
    Args:
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return.
        db (Session): Database session dependency.
        current_user (User): The authenticated admin user (dependency).

    Returns:
        UserListResponse: A list of user details, along with the total count.
    """
    users = db.query(User).offset(skip).limit(limit).all()
    total_users = db.query(User).count()
    return UserListResponse(total=total_users, items=users)

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Retrieve a specific user by ID",
    description="Fetches details for a single user by their ID. Accessible by admin users or the user themselves.",
)
async def read_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Requires active user authentication
):
    """
    Retrieves a specific user by their ID.
    
    Args:
        user_id (int): The ID of the user to retrieve.
        db (Session): Database session dependency.
        current_user (User): The authenticated user (dependency).

    Returns:
        UserResponse: The requested user's details.

    Raises:
        HTTPException 404: If the user is not found.
        HTTPException 403: If the authenticated user does not have permission to view this user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    
    # Authorization check: only admin or the user themselves can view their details
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this user's information",
        )
    return user

@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update an existing user",
    description="Updates details for an existing user. Accessible by admin users or the user themselves for their own profile.",
)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user) # Requires active user authentication
):
    """
    Updates an existing user's details.
    
    Args:
        user_id (int): The ID of the user to update.
        user_in (UserUpdate): The Pydantic model containing the updated user's details.
        db (Session): Database session dependency.
        current_user (User): The authenticated user (dependency).

    Returns:
        UserResponse: The updated user's details.

    Raises:
        HTTPException 404: If the user is not found.
        HTTPException 403: If the authenticated user does not have permission to update this user
                           or attempts to change admin status without privileges.
        HTTPException 409: If the updated email already exists.
        HTTPException 500: For other database integrity errors.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    
    # Authorization check: only admin or the user themselves can update their details
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this user",
        )

    # Convert Pydantic model to dict, excluding unset fields
    update_data = user_in.model_dump(exclude_unset=True)

    # Handle password hashing if a new password is provided
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    
    # Prevent non-admin users from changing their own admin status
    if not current_user.is_admin and "is_admin" in update_data:
        if update_data["is_admin"] != user.is_admin: # If they try to change it
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to change admin status."
            )

    # Update user object with new data
    for key, value in update_data.items():
        setattr(user, key, value)

    try:
        db.add(user) # Re-add to session for potential changes tracking
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: Could not update user. Check unique constraints (e.g., email)."
        )
    return user

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user (Admin only)",
    description="Deletes a user account by ID. Requires admin privileges.",
)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user) # Requires admin privileges
):
    """
    Deletes a user from the database.
    
    Args:
        user_id (int): The ID of the user to delete.
        db (Session): Database session dependency.
        current_user (User): The authenticated admin user (dependency).

    Returns:
        Response: An empty response with a 204 No Content status code upon successful deletion.

    Raises:
        HTTPException 404: If the user is not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)