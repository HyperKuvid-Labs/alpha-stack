from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session

from karyaksham_api.db.models.user import User
from karyaksham_api.schemas.user import UserCreate, UserUpdate
from karyaksham_api.auth import security
from .base import CRUDBase


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        """
        Retrieve a user by their email address.
        """
        return db.query(User).filter(User.email == email).first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """
        Create a new user, hashing the password before storing it.
        """
        hashed_password = security.get_password_hash(obj_in.password)
        db_obj = User(
            email=obj_in.email,
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            is_active=True,  # Users are active by default upon creation
            is_superuser=obj_in.is_superuser if obj_in.is_superuser is not None else False,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        Update an existing user's data. Handles password re-hashing if a new password is provided.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if "password" in update_data and update_data["password"]:
            hashed_password = security.get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        
        return super().update(db, db_obj=db_obj, obj_in=update_data)


user = CRUDUser(User)