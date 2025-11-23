"""
Database models package for db-common-models.

This package contains all SQLAlchemy models for the Figma integration feature,
including installation management, access control, and frame attachments.

The models follow a consistent pattern:
    - Soft delete support with deleted_at timestamps
    - Comprehensive indexing for query optimization
    - Relationships with proper back_populates for bidirectional access
    - Type hints and detailed docstrings
    - Helper methods for common operations

Models:
    FigmaInstallation: Represents a Figma integration connection (PAT metadata)
    FigmaInstallationAccess: Access control for sharing installations between users
    FigmaAttachment: Lightweight references to Figma frames attached to projects

Usage:
    from models import FigmaInstallation, FigmaInstallationAccess, FigmaAttachment, Base
    
    # All models share the same declarative base for proper relationship resolution
"""

# Import Base first to ensure it's available for all models
from .figma_installation import Base, FigmaInstallation
from .figma_installation_access import FigmaInstallationAccess
from .figma_attachment import FigmaAttachment

# Export all models and Base for external use
__all__ = [
    'Base',
    'FigmaInstallation',
    'FigmaInstallationAccess',
    'FigmaAttachment',
]
