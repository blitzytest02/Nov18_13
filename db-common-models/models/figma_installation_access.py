"""
SQLAlchemy model for figma_installation_access table.

This module defines the FigmaInstallationAccess model representing access control
for Figma integration sharing in the Blitzy platform. Each record grants a user
access to a specific Figma installation with a defined access level.

This model mirrors the github_installation_access pattern to provide consistent
role-based access control across different integration types.

Access Control:
    - Only ADMIN and SUPER_ADMIN roles can grant or revoke access
    - Access levels: viewer, editor, admin
    - All grants are tracked with grantor information for audit purposes
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

# Import Base from figma_installation module to ensure consistency
from .figma_installation import Base


class FigmaInstallationAccess(Base):
    """
    Represents access control for sharing Figma installations between users.

    This model enables role-based sharing of Figma integrations, allowing
    installation owners to grant other users access to their Figma PAT for
    use within the platform.

    Key Relationships:
        - Belongs to a FigmaInstallation (the shared integration)
        - References a User (who has access)
        - References a User (who granted the access)

    Access Levels:
        - viewer: Can view and use the Figma installation for attaching frames
        - editor: Can use and modify attachments
        - admin: Can use, modify, and share the installation with others

    Soft Delete:
        - Uses deleted_at timestamp for soft deletion
        - Soft-deleted records represent revoked access
        - Filter using: .filter(FigmaInstallationAccess.deleted_at.is_(None))

    Attributes:
        id: Primary key, auto-incrementing BIGINT
        figma_installation_id: Foreign key to figma_installation table
        user_id: User who has been granted access
        access_level: Level of access granted (viewer, editor, admin)
        granted_by: User who granted this access (must be ADMIN or SUPER_ADMIN)
        created_at: Timestamp when access was granted
        updated_at: Timestamp when access record was last modified
        deleted_at: Timestamp when access was revoked (NULL if active)
        installation: Relationship to FigmaInstallation model
        user: Relationship to User model (who has access)
        grantor: Relationship to User model (who granted access)
    """

    __tablename__ = 'figma_installation_access'

    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Primary key for figma_installation_access table'
    )

    # Foreign Keys
    figma_installation_id = Column(
        BigInteger,
        ForeignKey('figma_installation.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='References the Figma installation being shared'
    )

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='User who has been granted access to the installation'
    )

    granted_by = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=False,
        comment='User who granted this access (ADMIN or SUPER_ADMIN)'
    )

    # Data Fields
    access_level = Column(
        String(50),
        nullable=False,
        default='viewer',
        server_default='viewer',
        comment='Level of access: viewer, editor, or admin'
    )

    # Timestamp Fields
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default='now()',
        comment='Timestamp when access was granted'
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default='now()',
        comment='Timestamp when access record was last updated'
    )

    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment='Soft delete timestamp, NULL if access is active'
    )

    # Relationships
    installation = relationship(
        'FigmaInstallation',
        foreign_keys=[figma_installation_id],
        back_populates='access_grants',
        lazy='select',
        doc='The Figma installation being shared'
    )

    # Relationships to User model using string references
    # These use viewonly=True since back_populates cannot be configured
    # from this package (User model is external)
    #
    # NOTE: These relationships will only work when User model is available
    # in the same SQLAlchemy registry. When using db-common-models standalone,
    # these relationships should be configured in the consuming application.
    # Uncomment these when integrating into full application with User model:
    #
    # user = relationship(
    #     'User',
    #     foreign_keys=[user_id],
    #     viewonly=True,
    #     doc='User who has been granted access'
    # )
    #
    # granter = relationship(
    #     'User',
    #     foreign_keys=[granted_by],
    #     viewonly=True,
    #     doc='User who granted this access'
    # )

    # For standalone model compatibility, define placeholder properties
    # These will be overridden by actual relationships when integrated
    @property
    def user(self):
        """
        Placeholder for User relationship.

        This property provides a hook for the User relationship that should
        be configured when integrating into the full application. In standalone
        usage, this returns None.

        Returns:
            None in standalone mode, User object when relationship is configured.
        """
        # This will be overridden by SQLAlchemy relationship when User model is available
        return getattr(self, '_user', None)

    @property
    def granter(self):
        """
        Placeholder for granter (User) relationship.

        This property provides a hook for the granter relationship that should
        be configured when integrating into the full application. In standalone
        usage, this returns None.

        Returns:
            None in standalone mode, User object when relationship is configured.
        """
        # This will be overridden by SQLAlchemy relationship when User model is available
        return getattr(self, '_granter', None)

    @property
    def figma_installation(self):
        """
        Alias for installation relationship to match export specification.

        This property provides access to the FigmaInstallation object using
        the name specified in the export interface while maintaining
        compatibility with the back_populates relationship name.

        Returns:
            FigmaInstallation: The Figma installation being shared.
        """
        return self.installation

    # Indexes and constraints for query optimization and data integrity
    __table_args__ = (
        # Unique constraint: One active access record per user per installation
        UniqueConstraint(
            'figma_installation_id',
            'user_id',
            'deleted_at',
            name='uq_figma_access_installation_user_deleted'
        ),
        # Index for querying access by installation
        Index(
            'idx_figma_access_installation',
            'figma_installation_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        # Index for querying access by user
        Index(
            'idx_figma_access_user',
            'user_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        # Index for soft delete filtering
        Index(
            'idx_figma_access_deleted',
            'deleted_at'
        ),
        {
            'comment': 'Access control for sharing Figma installations between users'
        }
    )

    def __repr__(self) -> str:
        """
        String representation of FigmaInstallationAccess instance.

        Returns:
            Human-readable string showing key identifying information.
        """
        return (
            f"<FigmaInstallationAccess("
            f"id={self.id}, "
            f"installation_id={self.figma_installation_id}, "
            f"user_id={self.user_id}, "
            f"access_level='{self.access_level}', "
            f"deleted={self.deleted_at is not None}"
            f")>"
        )

    def is_active(self) -> bool:
        """
        Check if this access grant is active (not revoked).

        Returns:
            True if deleted_at is None, False otherwise.
        """
        return self.deleted_at is None

    def revoke(self) -> None:
        """
        Revoke this access grant by setting deleted_at timestamp.

        This method should be called within a transaction context. The caller
        is responsible for verifying that the requestor has permission to
        revoke access (must be ADMIN or SUPER_ADMIN).

        Note:
            The caller is responsible for committing the transaction.
        """
        self.deleted_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_access_level(self, new_level: str) -> None:
        """
        Update the access level for this grant.

        Args:
            new_level: New access level ('viewer', 'editor', or 'admin')

        Raises:
            ValueError: If new_level is not a valid access level.
        """
        valid_levels = {'viewer', 'editor', 'admin'}
        if new_level not in valid_levels:
            raise ValueError(
                f"Invalid access level '{new_level}'. "
                f"Must be one of: {', '.join(valid_levels)}"
            )
        self.access_level = new_level
        self.updated_at = datetime.now(timezone.utc)


# Export the model class for easy imports
__all__ = ['FigmaInstallationAccess']
