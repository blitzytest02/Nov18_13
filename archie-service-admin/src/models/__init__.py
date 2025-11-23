"""
Database models package for archie-service-admin.

This package contains SQLAlchemy models for the Figma integration feature.
All models share a common declarative base to ensure proper relationship
resolution and metadata management.

Models:
    FigmaInstallation: Represents a Figma integration connection (PAT metadata)
    FigmaInstallationAccess: Role-based access control for sharing Figma installations
    FigmaAttachment: Lightweight references to Figma frames attached to projects

Usage:
    from models import FigmaInstallation, FigmaInstallationAccess, FigmaAttachment, Base
"""

# Import Base from base module (defined separately to avoid circular imports)
from .base import Base

# Now import models which use Base from base.py
from .figma_installation import FigmaInstallation
from .figma_installation_access import FigmaInstallationAccess
from .figma_attachment import FigmaAttachment

# Export all models and Base for external use
__all__ = [
    'Base',
    'FigmaInstallation',
    'FigmaInstallationAccess',
    'FigmaAttachment',
]
