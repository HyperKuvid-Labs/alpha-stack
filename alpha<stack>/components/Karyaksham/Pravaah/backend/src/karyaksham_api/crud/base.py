from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, DeclarativeBase

# Define TypeVars for the SQLAlchemy model and Pydantic schemas.
# ModelType is bound to `DeclarativeBase`, assuming all SQLAlchemy models in the project
# inherit from a base class that ultimately derives from sqlalchemy.orm.DeclarativeBase.
ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    CRUD object with default methods for common database operations (Create, Read, Update, Delete).

    Args:
        model: A SQLAlchemy declarative model class (e.g., `User` or `Job`).
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """
        Retrieve a single record by its primary key ID.
        Assumes the model has an 'id' attribute as its primary key.

        Args:
            db: The SQLAlchemy database session.
            id: The primary key value of the record to retrieve.

        Returns:
            The SQLAlchemy model instance if found, otherwise None.
        """
        stmt = select(self.model).where(self.model.id == id)
        return db.scalar(stmt)

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Retrieve multiple records with optional offset and limit for pagination.

        Args:
            db: The SQLAlchemy database session.
            skip: The number of records to skip (offset).
            limit: The maximum number of records to return.

        Returns:
            A list of SQLAlchemy model instances.
        """
        stmt = select(self.model).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record in the database from a Pydantic create schema.

        Args:
            db: The SQLAlchemy database session.
            obj_in: The Pydantic schema containing data for the new record.

        Returns:
            The newly created SQLAlchemy model instance, refreshed with database values.
        """
        # Pydantic V2 uses .model_dump() to convert the Pydantic model to a dictionary
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing record in the database.

        Args:
            db: The SQLAlchemy database session.
            db_obj: The existing SQLAlchemy model instance to update.
            obj_in: The Pydantic schema or dictionary containing update data.
                    If a Pydantic schema, only fields that are explicitly set
                    in the schema (i.e., not unset) will be used for the update.

        Returns:
            The updated SQLAlchemy model instance, refreshed with database values.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Pydantic V2 uses .model_dump(exclude_unset=True) for partial updates,
            # ensuring only provided fields are considered.
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """
        Remove a record from the database by its primary key ID.
        Assumes the model has an 'id' attribute as its primary key.

        Args:
            db: The SQLAlchemy database session.
            id: The primary key value of the record to remove.

        Returns:
            The deleted SQLAlchemy model instance if found and deleted, otherwise None.
        """
        stmt = select(self.model).where(self.model.id == id)
        obj = db.scalar(stmt)
        if obj:
            db.delete(obj)
            db.commit()
        return obj