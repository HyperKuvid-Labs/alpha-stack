from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from karyaksham_api.schemas import user as schemas_user
from karyaksham_api.schemas import token as schemas_token
from karyaksham_api.crud import crud_user
from karyaksham_api.auth import security, jwt
from karyaksham_api.db.session import get_db
from karyaksham_api.core.config import settings
from karyaksham_api.db.models.user import User as DBUser


router = APIRouter()


@router.post("/register", response_model=schemas_user.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: schemas_user.UserCreate,
    db: Session = Depends(get_db)
) -> schemas_user.UserResponse:
    """
    Register a new user in the system.

    Raises:
        HTTPException: If a user with the provided email already exists.
    """
    user = crud_user.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    
    # Assuming crud_user.user.create method handles password hashing internally from user_in.password
    created_user = crud_user.user.create(db, obj_in=user_in) 
    
    return created_user


@router.post("/token", response_model=schemas_token.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> schemas_token.Token:
    """
    OAuth2 compatible token login endpoint. 
    Authenticates user and returns an access token for future requests.

    Raises:
        HTTPException: If authentication fails due to incorrect credentials.
    """
    user = security.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas_user.UserResponse)
def read_current_user(
    current_user: DBUser = Depends(security.get_current_active_user)
) -> schemas_user.UserResponse:
    """
    Retrieve details of the current authenticated user.
    Requires a valid JWT token in the Authorization header.
    """
    return current_user

```