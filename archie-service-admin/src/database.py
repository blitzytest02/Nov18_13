"""
Database session management for archie-service-admin.

This module provides centralized database session management using SQLAlchemy's
session factory pattern. It enables consistent session handling across the
application while supporting different session scopes for web requests, background
tasks, and testing.

The module follows SQLAlchemy best practices:
- Thread-local session scope for web requests
- Explicit session lifecycle management
- Context manager support for transaction handling
- Lazy initialization of engine and session factory

Usage in Production:
    ```python
    from database import get_db_session
    
    # Get session for database operations
    session = get_db_session()
    try:
        # Perform database operations
        result = session.query(Model).all()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    ```

Usage with Context Manager:
    ```python
    from database import get_db_session
    
    with get_db_session() as session:
        # Session automatically committed on exit or rolled back on exception
        result = session.query(Model).all()
    ```

Configuration:
    Database URL should be provided via environment variable DATABASE_URL or
    configured in application settings. Format:
    postgresql://user:password@host:port/database

Thread Safety:
    The sessionmaker is thread-safe and can be shared across threads. However,
    Session instances are NOT thread-safe and should not be shared between threads.
    Each thread/request should get its own session via get_db_session().
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

# Global session factory - initialized lazily on first use
_SessionLocal: Optional[sessionmaker] = None

# Global engine - initialized lazily on first use
_engine = None


def init_db(database_url: Optional[str] = None) -> None:
    """
    Initialize database engine and session factory.
    
    This function should be called once during application startup to configure
    the database connection. It creates the SQLAlchemy engine and session factory
    that will be used throughout the application lifecycle.
    
    :param database_url: Database connection URL (optional, defaults to DATABASE_URL env var)
    :type database_url: Optional[str]
    
    :raises ValueError: If database_url is not provided and DATABASE_URL env var not set
    :raises Exception: If database connection cannot be established
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        # Already initialized
        return
    
    # Get database URL from parameter or environment variable
    db_url = database_url or os.getenv('DATABASE_URL')
    
    if not db_url:
        raise ValueError(
            "Database URL must be provided via database_url parameter or "
            "DATABASE_URL environment variable"
        )
    
    # Create engine with appropriate settings
    # For testing: Use NullPool to avoid connection pooling issues
    # For production: Use default pooling (typically 5 connections)
    if 'pytest' in os.environ.get('_', ''):
        _engine = create_engine(db_url, poolclass=NullPool)
    else:
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600    # Recycle connections after 1 hour
        )
    
    # Create session factory
    _SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine
    )


def get_db_session() -> Session:
    """
    Get a new database session.
    
    Creates and returns a new SQLAlchemy Session instance for database operations.
    The caller is responsible for closing the session when done. Consider using
    the context manager pattern (get_db_session_ctx) for automatic cleanup.
    
    :return: SQLAlchemy Session instance
    :rtype: Session
    
    :raises RuntimeError: If database has not been initialized via init_db()
    
    Example:
        >>> session = get_db_session()
        >>> try:
        >>>     result = session.query(Model).all()
        >>>     session.commit()
        >>> except Exception:
        >>>     session.rollback()
        >>>     raise
        >>> finally:
        >>>     session.close()
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        # Try to initialize with default database URL
        init_db()
    
    if _SessionLocal is None:
        raise RuntimeError(
            "Database session factory not initialized. "
            "Call init_db() first or set DATABASE_URL environment variable."
        )
    
    return _SessionLocal()


@contextmanager
def get_db_session_ctx() -> Generator[Session, None, None]:
    """
    Context manager for database session with automatic cleanup.
    
    Provides a database session that automatically commits on success and
    rolls back on exception. The session is closed automatically when the
    context exits.
    
    :return: SQLAlchemy Session instance
    :rtype: Generator[Session, None, None]
    
    :yields: Session: SQLAlchemy Session instance
    
    :raises RuntimeError: If database has not been initialized via init_db()
    
    Example:
        >>> with get_db_session_ctx() as session:
        >>>     result = session.query(Model).all()
        >>>     # Automatically commits on exit
        >>>     # Automatically rolls back on exception
    """
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_db() -> None:
    """
    Close database engine and dispose of connection pool.
    
    This function should be called during application shutdown to properly
    close all database connections and dispose of the connection pool.
    After calling this function, init_db() must be called again before
    using get_db_session().
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
