"""
Database models package for archie-service-admin.

This package contains SQLAlchemy models for the Figma integration feature.
All models share a common declarative base to ensure proper relationship
resolution and metadata management.

Models:
    FigmaInstallation: Represents a Figma integration connection (PAT metadata)
    FigmaAttachment: Lightweight references to Figma frames attached to projects

Usage:
    from models import FigmaInstallation, FigmaAttachment, Base
"""

# Import Base first from figma_installation to ensure it's available for all models
from .figma_installation import Base, FigmaInstallation
from .figma_attachment import FigmaAttachment

# Export all models and Base for external use
__all__ = [
    'Base',
    'FigmaInstallation',
    'FigmaAttachment',
]
