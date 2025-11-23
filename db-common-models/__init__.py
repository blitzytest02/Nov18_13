"""
db-common-models Package
========================

Shared database model definitions for Figma integration across Blitzy microservices.

This package provides consistent SQLAlchemy model definitions for the Figma integration
feature, enabling archie-service-admin and archie-service-backend to share the same
database schema representation without duplication.

Overview
--------
The Figma integration supports connecting Figma accounts via Personal Access Tokens (PATs),
sharing integrations across teams with role-based access control, and attaching Figma design
frames to projects with lightweight metadata storage.

Models
------
FigmaInstallation : class
    Represents a Figma integration connection storing PAT metadata.
    
    Attributes:
        id (int): Primary key, auto-generated installation identifier
        user_id (int): Owner of the installation (foreign key to users table)
        team_id (int, optional): Team association (foreign key to teams table)
        name (str): Human-readable installation name
        description (str, optional): Installation description
        status (str): PAT status - 'active', 'expired', or 'disabled'
        created_at (datetime): Timestamp when installation was created
        updated_at (datetime): Timestamp of last update
        deleted_at (datetime, optional): Soft delete timestamp

FigmaInstallationAccess : class
    Access control for sharing Figma installations between users.
    
    Attributes:
        id (int): Primary key, auto-generated access record identifier
        figma_installation_id (int): Reference to shared installation
        user_id (int): User who has been granted access
        access_level (str): Access level - 'viewer', 'editor', or 'admin'
        granted_by (int): Admin user who granted access
        created_at (datetime): Timestamp when access was granted
        updated_at (datetime): Timestamp of last update
        deleted_at (datetime, optional): Soft delete timestamp for revoked access

FigmaAttachment : class
    Lightweight metadata for Figma design frames attached to projects.
    
    Attributes:
        id (int): Primary key, auto-generated attachment identifier
        project_id (int): Project this frame is attached to (foreign key)
        tech_spec_id (int, optional): Optional tech spec association (foreign key)
        figma_installation_id (int): Installation used to validate frame access
        frame_url (str): Figma frame URL (unique per project when not deleted)
        frame_title (str, optional): Frame title retrieved from Figma API
        description (str, optional): User-provided description of the frame
        created_by (int): User who created the attachment
        created_at (datetime): Timestamp when attachment was created
        updated_at (datetime): Timestamp of last update
        deleted_at (datetime, optional): Soft delete timestamp

Usage
-----
Services can import models directly from the db_common_models package::

    from db_common_models import FigmaInstallation, FigmaInstallationAccess, FigmaAttachment
    
    # Use models for database operations
    installation = FigmaInstallation(
        user_id=user_id,
        name="My Figma Integration",
        status="active"
    )

Notes
-----
- All models support soft deletion via the deleted_at timestamp column
- PAT (Personal Access Token) values are stored in Google Secret Manager, not in the database
- The status field enables tracking PAT validity (Active/Expired) without exposing the actual token
- Frame attachments store only URLs and metadata - no file downloads or GCS uploads are performed

Architecture
------------
These models are part of the db-common-models shared package to ensure schema consistency
across the following services:
- archie-service-admin: Primary implementation with business logic
- archie-service-backend: Public-facing gateway with authorization
- platform-event-listener: Consumer of internal APIs

See Also
--------
- Agent Action Plan Section 0.4: Database Schema Specifications
- Agent Action Plan Section 0.5: Repository 3 (db-common-models) changes
- docs/figma_technical_guide.md: Complete implementation guide
"""

# Import all Figma integration models from the models subpackage
from .models import (
    Base,
    FigmaInstallation,
    FigmaInstallationAccess,
    FigmaAttachment,
)

# Define explicit public API for the package
# This enables controlled imports and makes the package interface clear
__all__ = [
    'Base',
    'FigmaInstallation',
    'FigmaInstallationAccess',
    'FigmaAttachment',
]
