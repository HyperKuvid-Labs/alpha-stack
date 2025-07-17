from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config.settings import settings

# Create the asynchronous engine for database connections.
# The database URL is loaded from application settings.
# `echo=settings.debug` will log SQL statements to stdout if debug mode is enabled,
# which is useful for development and debugging.
# `pool_pre_ping=True` enables connection pre-ping, which tests connections for liveness
# before they are used, helping to prevent errors with stale connections.
# `pool_size` and `max_overflow` configure the connection pool for performance and scalability,
# defining the minimum and maximum number of connections maintained.
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

# Configure an asynchronous sessionmaker. This factory will produce new AsyncSession objects.
# `autocommit=False` ensures that changes are not automatically committed; explicit commits are required.
# `autoflush=False` prevents SQLAlchemy from automatically flushing pending changes to the database
# before certain operations (e.g., query execution).
# `bind=engine` links this sessionmaker to our created database engine.
# `expire_on_commit=False` prevents ORM objects from being expired (detached from the session)
# after a commit, which can be convenient in web applications where objects might be accessed
# after a transaction is completed.
# `class_=AsyncSession` explicitly specifies that sessions created by this factory will be
# instances of AsyncSession, crucial for asynchronous operations.
AsyncSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an asynchronous database session.

    This generator function creates a new `AsyncSession` from `AsyncSessionLocal`,
    yields it for use in an API endpoint or other application logic, and ensures
    the session is properly closed afterwards, even if an error occurs during processing.

    This pattern is crucial for managing database connection lifecycles within FastAPI,
    ensuring that resources are released efficiently after each request.

    Yields:
        AsyncSession: An asynchronous SQLAlchemy database session.
    """
    db_session: AsyncSession = AsyncSessionLocal()
    try:
        yield db_session
    finally:
        await db_session.close()