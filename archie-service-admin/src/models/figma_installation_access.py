"""
SQLAlchemy ORM model for Figma Installation Access Control.

This module defines the FigmaInstallationAccess model representing role-based
access control for Figma installations. It enables sharing of Figma integrations
across team members by tracking which users have permission to use specific
Figma installations and at what access level.

The model implements the authorization layer for Figma integration sharing,
allowing ADMIN and SUPER_ADMIN users to grant or revoke access to Figma PATs
without exposing the actual token values. Access grants are tracked with full
audit information including who granted the access and when.

Table: figma_installation_access
Unique Constraint: (figma_installation_id, user_id, deleted_at) prevents duplicate active grants
Indexes: figma_installation_id, user_id, deleted_at for efficient access checks and queries
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

# Import the shared declarative base from the models.base module
# Base is defined in base.py to avoid circular import issues
from .base import Base


class FigmaInstallationAccess(Base):
    """
    Represents access control grants for Figma installations.

    This model implements role-based access control (RBAC) for sharing Figma
    integrations across users. When a user with ADMIN or SUPER_ADMIN privileges
    grants access to a Figma installation, a record is created here to authorize
    the recipient user to use that installation's PAT for Figma API operations.

    Access levels define the scope of permissions:
    - 'viewer': Read-only access to use the installation for viewing Figma frames
    - 'editor': Can attach/detach Figma frames using the installation
    - 'admin': Full control including sharing/revoking access to others

    The model supports soft deletion to maintain a complete audit trail of access
    grants and revocations. The unique constraint ensures a user cannot have
    duplicate active access grants to the same installation while allowing
    historical records of revoked access.

    :ivar id: Primary key, unique identifier for the access grant
    :type id: int
    :ivar figma_installation_id: Foreign key to figma_installation.id
    :type figma_installation_id: int
    :ivar user_id: User who has been granted access, references users.id
    :type user_id: int
    :ivar access_level: Permission level - 'viewer', 'editor', or 'admin'
    :type access_level: str
    :ivar granted_by: User ID of admin who granted this access, references users.id
    :type granted_by: int
    :ivar created_at: Timestamp when access was granted
    :type created_at: datetime
    :ivar updated_at: Timestamp when access record was last modified
    :type updated_at: datetime
    :ivar deleted_at: Soft delete timestamp for access revocation, NULL indicates active access
    :type deleted_at: Optional[datetime]

    :ivar installation: Relationship to FigmaInstallation (the installation being shared)
    :ivar user: Relationship to User model (the user who has access)
    :ivar granted_by_user: Relationship to User model (admin who granted access)
    """

    __tablename__ = 'figma_installation_access'

    # Define table-level constraints and indexes
    __table_args__ = (
        # Unique constraint prevents duplicate active access grants
        # Including deleted_at allows maintaining history of revoked grants
        UniqueConstraint(
            'figma_installation_id',
            'user_id',
            'deleted_at',
            name='uq_figma_access_installation_user_deleted'
        ),
        # Index for efficient queries by installation when listing access grants
        Index('idx_figma_access_installation', 'figma_installation_id'),
        # Index for efficient queries by user when checking permissions
        Index('idx_figma_access_user', 'user_id'),
        # Index for efficient filtering of soft-deleted records
        Index('idx_figma_access_deleted', 'deleted_at'),
    )

    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Unique identifier for the access grant record'
    )

    # Foreign Keys
    figma_installation_id = Column(
        BigInteger,
        ForeignKey('figma_installation.id', ondelete='CASCADE'),
        nullable=False,
        comment='Reference to the Figma installation being shared'
    )

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        comment='User who has been granted access to the installation'
    )

    granted_by = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=False,
        comment='Admin user who granted this access'
    )

    # Data Fields
    access_level = Column(
        String(50),
        nullable=False,
        default='viewer',
        comment='Permission level: viewer (read-only), editor (attach frames), or admin (full control)'
    )

    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment='Timestamp when access was granted'
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='Timestamp when access record was last modified'
    )

    # Soft Delete Support
    deleted_at = Column(
        DateTime,
        nullable=True,
        comment='Soft delete timestamp for access revocation, NULL indicates active access'
    )

    # Relationships
    installation = relationship(
        'FigmaInstallation',
        back_populates='access_records',
        foreign_keys=[figma_installation_id],
        lazy='joined',
        doc='The Figma installation that is being shared'
    )

    user = relationship(
        'User',
        foreign_keys=[user_id],
        backref='figma_installation_access_grants',
        lazy='joined',
        doc='The user who has been granted access to the installation'
    )

    granted_by_user = relationship(
        'User',
        foreign_keys=[granted_by],
        backref='figma_access_grants_given',
        lazy='joined',
        doc='The admin user who granted this access'
    )

    def __repr__(self) -> str:
        """
        Return a string representation of the FigmaInstallationAccess instance.

        :return: String representation including id, installation_id, user_id, and access_level
        :rtype: str
        """
        return (
            f"<FigmaInstallationAccess(id={self.id}, "
            f"installation_id={self.figma_installation_id}, "
            f"user_id={self.user_id}, access_level='{self.access_level}')>"
        )

    def is_active(self) -> bool:
        """
        Check if the access grant is currently active (not revoked).

        An access grant is considered active if its deleted_at field is NULL.
        This method provides a convenient way to filter out revoked access grants
        in authorization checks without directly examining the deleted_at timestamp.

        :return: True if access is active (not revoked), False otherwise
        :rtype: bool
        """
        return self.deleted_at is None

    def is_admin_level(self) -> bool:
        """
        Check if this access grant provides admin-level permissions.

        Admin-level access allows the user to perform privileged operations including
        sharing the installation with other users, revoking access, and updating
        the installation's PAT. This is used in authorization logic to determine
        if a user can perform administrative actions.

        :return: True if access_level is 'admin', False otherwise
        :rtype: bool
        """
        return self.access_level == 'admin'  # type: ignore[return-value]

    def is_editor_or_above(self) -> bool:
        """
        Check if this access grant provides editor-level permissions or higher.

        Editor and admin levels allow the user to attach and detach Figma frames
        to projects. This is the minimum permission level required for mutating
        operations on Figma attachments.

        :return: True if access_level is 'editor' or 'admin', False otherwise
        :rtype: bool
        """
        return self.access_level in ('editor', 'admin')

    def can_share(self) -> bool:
        """
        Determine if this access level permits sharing the installation with others.

        Only users with admin-level access can grant or revoke access for other users.
        This method encapsulates the authorization rule for sharing operations,
        ensuring consistent enforcement across the application.

        :return: True if user can share the installation, False otherwise
        :rtype: bool
        """
        return self.is_active() and self.is_admin_level()

    def can_attach_frames(self) -> bool:
        """
        Determine if this access level permits attaching Figma frames to projects.

        Editor and admin levels can create Figma attachments. Viewers can only
        see existing attachments but cannot create new ones. This method is used
        in authorization checks before allowing frame attachment operations.

        :return: True if user can attach frames, False otherwise
        :rtype: bool
        """
        return self.is_active() and self.is_editor_or_above()
