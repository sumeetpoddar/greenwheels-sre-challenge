
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


# SQLAlchemy engine manages database connectivity and connection pooling.
engine_options = {
    "pool_size": settings.database_pool_size,
    "max_overflow": settings.database_max_overflow,
    "pool_timeout": settings.database_pool_timeout,
    "pool_pre_ping": True,
    "echo": False,
}

if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_options.pop("pool_size")
        engine_options.pop("max_overflow")
        engine_options.pop("pool_timeout")
        engine_options["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_options)


# Session factory creates independent database sessions.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base class for all SQLAlchemy ORM models.
Base = declarative_base()


def initialize_database() -> None:
    """Create missing tables before serving requests."""
    from app.models.db_models import LeaseDB, LeaseEventDB

    Base.metadata.create_all(
        bind=engine,
        tables=[LeaseDB.__table__, LeaseEventDB.__table__],
    )


def get_db():
    """
    Provide a database session to FastAPI endpoints.

    Each request gets its own session.
    The session is closed after the request completes.
    """
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Verify that PostgreSQL is reachable.

    Executes a lightweight SELECT 1 query.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False
