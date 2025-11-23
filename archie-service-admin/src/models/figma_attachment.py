"""
SQLAlchemy ORM model for Figma design frame attachments.

This module defines the FigmaAttachment model representing lightweight metadata
for Figma design frames attached to projects and optionally to tech specs. The
model stores only frame URLs, titles retrieved from Figma API, and user-provided
descriptions without downloading actual files to GCS.

Attachments are linked to a FigmaInstallation which provides the PAT credentials
for validating frame access. The unique constraint on (project_id, frame_url, deleted_at)
ensures that the same frame URL can only exist once per project, with last-write-wins
behavior for updates (additive, idempotent).

Table: figma_attachment
Indexes: project_id, tech_spec_id, figma_installation_id, deleted_at for efficient querying
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

# Import FigmaInstallation for relationship definition
from .figma_installation import FigmaInstallation

# Import the shared declarative base from the models.base module
# Base is defined in base.py to avoid circular import issues
from .base import Base


class FigmaAttachment(Base):
    """
    Represents a Figma design frame attached to a project or tech spec.

    FigmaAttachment provides lightweight storage for Figma frame references without
    downloading files. Each attachment links a Figma frame URL to a project (required)
    and optionally to a specific tech spec. The frame_title is automatically retrieved
    from the Figma API during validation, while users can provide custom descriptions.

    Attachments are validated against the Figma API using the PAT stored in the
    associated FigmaInstallation before creation. The unique constraint ensures
    that duplicate frame URLs cannot exist for the same project, supporting an
    additive and idempotent attachment workflow where the last write wins.

    Soft deletion is supported via the deleted_at field, allowing attachments to
    be marked as deleted while preserving historical records and maintaining
    referential integrity for audit purposes.

    :ivar id: Primary key, unique identifier for the attachment
    :type id: int
    :ivar project_id: Project ID this frame is attached to, references projects.id (required)
    :type project_id: int
    :ivar tech_spec_id: Optional tech spec association, references tech_specs.id
    :type tech_spec_id: Optional[int]
    :ivar figma_installation_id: Figma installation providing PAT, references figma_installation.id (required)
    :type figma_installation_id: int
    :ivar frame_url: Full URL to the Figma frame (required)
    :type frame_url: str
    :ivar frame_title: Frame title retrieved from Figma API (max 500 characters)
    :type frame_title: Optional[str]
    :ivar description: User-provided description of the frame's purpose
    :type description: Optional[str]
    :ivar created_by: User ID who created the attachment, references users.id (required)
    :type created_by: int
    :ivar created_at: Timestamp when attachment was created
    :type created_at: datetime
    :ivar updated_at: Timestamp when attachment was last modified
    :type updated_at: datetime
    :ivar deleted_at: Soft delete timestamp, NULL indicates active attachment
    :type deleted_at: Optional[datetime]

    :ivar installation: Relationship to FigmaInstallation model (provides PAT for validation)
    :ivar project: Relationship to Project model (parent project)
    :ivar tech_spec: Relationship to TechSpec model (optional parent tech spec)
    :ivar creator: Relationship to User model (user who created attachment)
    """

    __tablename__ = 'figma_attachment'

    # Define table-level constraints and indexes
    __table_args__ = (
        # Unique constraint prevents duplicate frame URLs per project (last write wins)
        UniqueConstraint(
            'project_id',
            'frame_url',
            'deleted_at',
            name='uq_figma_attachment_project_frame_deleted'
        ),
        # Indexes for efficient querying by foreign keys and soft delete status
        Index('idx_figma_attachment_project', 'project_id'),
        Index('idx_figma_attachment_techspec', 'tech_spec_id'),
        Index('idx_figma_attachment_installation', 'figma_installation_id'),
        Index('idx_figma_attachment_deleted', 'deleted_at'),
    )

    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Unique identifier for the Figma frame attachment'
    )

    # Foreign Keys
    project_id = Column(
        BigInteger,
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        comment='Project ID this frame is attached to, references projects table'
    )

    tech_spec_id = Column(
        BigInteger,
        ForeignKey('tech_specs.id', ondelete='CASCADE'),
        nullable=True,
        comment='Optional tech spec association, references tech_specs table'
    )

    figma_installation_id = Column(
        BigInteger,
        ForeignKey('figma_installation.id', ondelete='CASCADE'),
        nullable=False,
        comment='Figma installation providing PAT credentials, references figma_installation table'
    )

    created_by = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment='User ID who created the attachment, references users table'
    )

    # Data Fields
    frame_url = Column(
        Text,
        nullable=False,
        comment='Full URL to the Figma frame (e.g., https://www.figma.com/file/...?node-id=...)'
    )

    frame_title = Column(
        String(500),
        nullable=True,
        comment='Frame title retrieved from Figma API during validation'
    )

    description = Column(
        Text,
        nullable=True,
        comment='User-provided description of the frame purpose and context'
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment='Timestamp when attachment was created'
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='Timestamp when attachment was last modified'
    )

    # Soft Delete Support
    deleted_at = Column(
        DateTime,
        nullable=True,
        comment='Soft delete timestamp, NULL indicates active attachment'
    )

    # Relationships
    installation = relationship(
        'FigmaInstallation',
        foreign_keys=[figma_installation_id],
        back_populates='attachments',
        lazy='joined',
        doc='The Figma installation providing PAT credentials for this attachment'
    )

    project = relationship(
        'Project',
        foreign_keys=[project_id],
        backref='figma_attachments',
        lazy='joined',
        doc='The project this frame is attached to'
    )

    tech_spec = relationship(
        'TechSpec',
        foreign_keys=[tech_spec_id],
        backref='figma_attachments',
        lazy='joined',
        doc='Optional tech spec this frame is specifically associated with'
    )

    creator = relationship(
        'User',
        foreign_keys=[created_by],
        backref='created_figma_attachments',
        lazy='joined',
        doc='The user who created this attachment'
    )

    def __repr__(self) -> str:
        """
        Return a string representation of the FigmaAttachment instance.

        :return: String representation including id, project_id, and frame_url
        :rtype: str
        """
        return (
            f"<FigmaAttachment(id={self.id}, project_id={self.project_id}, "
            f"frame_url='{self.frame_url[:50]}...', installation_id={self.figma_installation_id})>"
        )

    def is_active(self) -> bool:
        """
        Check if the attachment is currently active (not soft-deleted).

        An attachment is considered active if its deleted_at field is NULL.
        This method provides a convenient way to filter out soft-deleted records
        in business logic without directly checking the deleted_at timestamp.

        :return: True if attachment is active (not deleted), False otherwise
        :rtype: bool
        """
        return self.deleted_at is None

    def has_tech_spec(self) -> bool:
        """
        Check if the attachment is associated with a specific tech spec.

        Attachments can be project-level (no tech spec) or tech-spec-level
        (associated with a specific tech spec within the project). This method
        provides a convenient way to determine the attachment scope.

        :return: True if attachment has a tech_spec_id, False if project-level only
        :rtype: bool
        """
        return self.tech_spec_id is not None
