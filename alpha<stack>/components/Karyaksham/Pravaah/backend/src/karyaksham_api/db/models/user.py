from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from karyaksham_api.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Define relationship to Job model
    # 'Job' is a string literal to avoid circular imports if Job model
    # also needs to refer to User. The back_populates ensures a bidirectional relationship.
    jobs = relationship("Job", back_populates="owner")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"