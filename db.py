"""Database configuration and reusable helper functions for CustomerHub."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Define database file name and absolute file path
DB_FILENAME = "shop.db"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / DB_FILENAME

# SQLite database URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Global table name constants
TABLE_ORDERS = "orders"

# SQLAlchemy engine instance
_engine: Engine | None = None


def get_engine() -> Engine:
    """Return a singleton SQLAlchemy engine for SQLite database operations."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, echo=False)
    return _engine


def get_db_path() -> str:
    """Return the absolute string path to the SQLite database file."""
    return str(DB_PATH)


def get_connection():
    """Return an active connection from the engine.
    
    Can be used with a context manager:
        with get_connection() as conn:
            ...
    """
    return get_engine().connect()
