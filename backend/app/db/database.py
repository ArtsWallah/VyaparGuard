import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("uvicorn.error")

# Locate and load .env file
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=env_path, override=True)
load_dotenv(override=True)

DEFAULT_DATABASE_URL = "postgresql://postgres:Kevaall%401500@db.vdvguqcdveztlluyoaba.supabase.co:5432/postgres"
DATABASE_URL = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL

# Primary engine
primary_engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3} if "postgresql" in DATABASE_URL else {},
)

# Local SQLite fallback engine
db_path = Path(__file__).resolve().parent.parent.parent / "local_vyaparguard.db"
sqlite_engine = create_engine(
    f"sqlite:///{db_path.as_posix()}",
    connect_args={"check_same_thread": False},
)

Base = declarative_base()
_sqlite_initialized = False


def _init_sqlite_if_needed():
    global _sqlite_initialized
    if not _sqlite_initialized:
        Base.metadata.create_all(bind=sqlite_engine)
        _sqlite_initialized = True


class ResilientSessionFactory:
    """Session factory that tries primary remote DB, falling back to local SQLite if offline."""

    def __init__(self):
        self._primary_factory = sessionmaker(
            bind=primary_engine,
            autoflush=False,
            autocommit=False,
        )
        self._sqlite_factory = sessionmaker(
            bind=sqlite_engine,
            autoflush=False,
            autocommit=False,
        )

    def __call__(self):
        try:
            with primary_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return self._primary_factory()
        except Exception as exc:
            logger.warning(
                "Primary database connection failed (%s: %s). Falling back to local SQLite.",
                type(exc).__name__,
                exc,
            )
            _init_sqlite_if_needed()
            return self._sqlite_factory()


SessionLocal = ResilientSessionFactory()
engine = primary_engine


def test_database_connection() -> bool:
    """Check that database is reachable."""
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    return True
