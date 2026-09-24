"""
Shared database dependency for FastAPI routes.
Import get_db from here instead of defining it in each file.
"""
from models import DatabaseManager

db_manager = DatabaseManager()


def get_db():
    """FastAPI dependency: yields a database session, closes it after request."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
