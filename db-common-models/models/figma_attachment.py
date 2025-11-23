"""
SQLAlchemy model for figma_attachment table.

This module defines the FigmaAttachment model representing Figma design frame
attachments to projects in the Blitzy platform. Each attachment links a Figma
frame URL to a project (and optionally a technical specification) for reference.

IMPORTANT: This is a lightweight attachment system that stores ONLY URLs and
metadata. No Figma files are downloaded or stored in Google Cloud Storage.

Key Behavior:
    - Additive and idempotent: Same frame URL for same project overwrites previous
    - Frame URLs are validated against Figma API before attachment
    - Frame titles are retrieved from Figma API during validation
    - Multiple frames can be attached in a single operation
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

# Import Base from figma_installation module to ensure consistency
from .figma_installation import Base


class FigmaAttachment(Base):
    """
    Represents a Figma design frame attached to a project or technical specification.
    
    This model stores lightweight references to Figma frames via URLs, allowing
    users to associate design assets with their development projects without
    storing actual file content.
    
    Key Relationships:
        - Belongs to a Project via project_id foreign key
        - Optionally belongs to a TechSpec via tech_spec_id foreign key
        - References a FigmaInstallation (defined as ORM relationship)
        - Created by a User via created_by foreign key
        
        Note: Only the FigmaInstallation relationship is defined at the ORM level.
        Relationships to Project, TechSpec, and User should be defined in services
        that use this model where all models share the same SQLAlchemy registry.
    
    Attachment Process:
        1. Frame URL validated against Figma API using installation's PAT
        2. Frame title retrieved from Figma API
        3. URL and metadata stored in database
        4. NO file download or GCS upload occurs
    
    Uniqueness:
        - Same frame URL can only exist once per project (active records)
        - If same URL added again, previous record is updated (upsert behavior)
    
    Soft Delete:
        - Uses deleted_at timestamp for soft deletion
        - Allows frame to be re-attached after deletion
        - Filter using: .filter(FigmaAttachment.deleted_at.is_(None))
    
    Attributes:
        id: Primary key, auto-incrementing BIGINT
        project_id: Foreign key to projects table (required)
        tech_spec_id: Optional foreign key to tech_specs table
        figma_installation_id: Foreign key to figma_installation (for PAT access)
        frame_url: Full Figma frame URL (e.g., https://www.figma.com/file/...)
        frame_title: Title of the frame retrieved from Figma API
        description: Optional user-provided description of the frame's purpose
        created_by: User who attached this frame
        created_at: Timestamp when frame was attached
        updated_at: Timestamp when attachment was last modified
        deleted_at: Timestamp when attachment was removed (NULL if active)
        figma_installation: ORM relationship to FigmaInstallation model
    """
    
    __tablename__ = 'figma_attachment'
    
    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Primary key for figma_attachment table'
    )
    
    # Foreign Keys
    project_id = Column(
        BigInteger,
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='Project this frame is attached to'
    )
    
    tech_spec_id = Column(
        BigInteger,
        ForeignKey('tech_specs.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
        comment='Optional technical specification association'
    )
    
    figma_installation_id = Column(
        BigInteger,
        ForeignKey('figma_installation.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='Figma installation used to validate and access this frame'
    )
    
    created_by = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=False,
        comment='User who attached this frame'
    )
    
    # Data Fields
    frame_url = Column(
        Text,
        nullable=False,
        comment='Full Figma frame URL'
    )
    
    frame_title = Column(
        String(500),
        nullable=True,
        comment='Frame title retrieved from Figma API during validation'
    )
    
    description = Column(
        Text,
        nullable=True,
        comment='Optional user-provided description of frame purpose'
    )
    
    # Timestamp Fields
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default='now()',
        comment='Timestamp when frame was attached'
    )
    
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default='now()',
        comment='Timestamp when attachment was last updated'
    )
    
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment='Soft delete timestamp, NULL if attachment is active'
    )
    
    # Relationships
    # NOTE: Relationships to external models (Project, TechSpec, User) are NOT defined here
    # because those models exist in separate packages (archie-service-admin, archie-service-backend).
    # Services that use this model should define those relationships in their own codebase
    # where all models are available in the same SQLAlchemy registry.
    # 
    # Only the relationship to FigmaInstallation is defined here since it's in the same package.
    
    figma_installation = relationship(
        'FigmaInstallation',
        foreign_keys=[figma_installation_id],
        back_populates='attachments',
        lazy='select',
        doc='Figma installation used for this attachment'
    )
    
    # Indexes and constraints for query optimization and data integrity
    __table_args__ = (
        # Unique constraint: One active attachment per frame URL per project
        # This enables upsert behavior - same URL overwrites previous
        UniqueConstraint(
            'project_id',
            'frame_url',
            'deleted_at',
            name='uq_figma_attachment_project_url_deleted'
        ),
        # Index for querying attachments by project
        Index(
            'idx_figma_attachment_project',
            'project_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        # Index for querying attachments by tech spec
        Index(
            'idx_figma_attachment_techspec',
            'tech_spec_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        # Index for querying attachments by installation
        Index(
            'idx_figma_attachment_installation',
            'figma_installation_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        # Index for soft delete filtering
        Index(
            'idx_figma_attachment_deleted',
            'deleted_at'
        ),
        # Composite index for common query pattern: project + tech_spec filtering
        Index(
            'idx_figma_attachment_project_techspec',
            'project_id',
            'tech_spec_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        {
            'comment': 'Lightweight storage for Figma frame URLs attached to projects. '
                       'No file downloads - URLs and metadata only.'
        }
    )
    
    def __repr__(self) -> str:
        """
        String representation of FigmaAttachment instance.
        
        Returns:
            Human-readable string showing key identifying information.
        """
        return (
            f"<FigmaAttachment("
            f"id={self.id}, "
            f"project_id={self.project_id}, "
            f"frame_title='{self.frame_title}', "
            f"deleted={self.deleted_at is not None}"
            f")>"
        )
    
    def is_active(self) -> bool:
        """
        Check if this attachment is active (not soft-deleted).
        
        Returns:
            True if deleted_at is None, False otherwise.
        """
        return self.deleted_at is None
    
    def mark_as_deleted(self) -> None:
        """
        Soft delete this attachment by setting deleted_at timestamp.
        
        This removes the frame reference from the project without permanently
        deleting the record, allowing for audit trail and potential restoration.
        
        Note:
            The caller is responsible for committing the transaction.
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
    
    def update_metadata(
        self,
        frame_title: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """
        Update attachment metadata.
        
        Args:
            frame_title: New frame title (if None, keeps existing)
            description: New description (if None, keeps existing)
        """
        if frame_title is not None:
            self.frame_title = frame_title
        if description is not None:
            self.description = description
        self.updated_at = datetime.now(timezone.utc)


# Export the model class for easy imports
__all__ = ['FigmaAttachment']
