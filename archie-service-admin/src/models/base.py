"""
SQLAlchemy declarative base for all models.

This module provides the shared Base class that all SQLAlchemy ORM models
inherit from. Defining Base in a separate module avoids circular import
issues that can occur when models try to import Base from __init__.py.

Usage:
    from models.base import Base

    class MyModel(Base):
        __tablename__ = 'my_table'
        ...
"""

from sqlalchemy.ext.declarative import declarative_base

# Create the declarative base that all models will inherit from
# This base provides the metaclass and metadata registry for SQLAlchemy ORM
Base = declarative_base()
