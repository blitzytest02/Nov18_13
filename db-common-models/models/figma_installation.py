"""
SQLAlchemy model for figma_installation table.

This module defines the FigmaInstallation model representing Figma integration
connections in the Blitzy platform. Each installation represents a user's or
team's connection to Figma through a Personal Access Token (PAT).

SECURITY NOTE: The actual PAT is NEVER stored in this table. PATs are stored
securely in Google Secret Manager following the naming pattern:
figma-secret-<installation_id>

The status field in this model tracks the computed validity state of the PAT
(active/expired/disabled) which is determined by validating the PAT against
the Figma API.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


# Create declarative base for SQLAlchemy models
# This will be shared across all db-common-models
Base = declarative_base()


class FigmaInstallation(Base):
    """
    Represents a Figma integration installation for a user or team.
    
    This model stores metadata about a Figma integration connection including
    ownership, naming, and status information. The actual Personal Access Token
    (PAT) is stored separately in Google Secret Manager for security.
    
    Key Relationships:
        - Belongs to a User (owner of the integration)
        - Optionally belongs to a Team
        - Has many FigmaInstallationAccess records (sharing)
        - Has many FigmaAttachment records (design frames)
    
    Security Model:
        - PAT stored in Google Secret Manager as: figma-secret-{installation_id}
        - PAT never exposed through this model or API responses
        - Status field reflects PAT validity (determined via Figma API validation)
    
    Soft Delete:
        - Uses deleted_at timestamp for soft deletion
        - Soft-deleted records should be filtered in queries using:
          .filter(FigmaInstallation.deleted_at.is_(None))
    
    Attributes:
        id: Primary key, auto-incrementing BIGINT
        user_id: Foreign key to users table (owner of the installation)
        team_id: Optional foreign key to teams table
        name: Human-readable name for the installation (max 255 chars)
        description: Optional detailed description
        status: PAT validity state ('active', 'expired', or 'disabled')
        created_at: Timestamp when installation was created
        updated_at: Timestamp when installation was last modified
        deleted_at: Timestamp when installation was soft-deleted (NULL if active)
        user: Relationship to User model (owner)
        team: Relationship to Team model (optional)
    """
    
    __tablename__ = 'figma_installation'
    
    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Primary key for figma_installation table'
    )
    
    # Foreign Keys
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='Owner of the Figma installation, references users.id'
    )
    
    team_id = Column(
        BigInteger,
        ForeignKey('teams.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='Optional team association, references teams.id'
    )
    
    # Data Fields
    name = Column(
        String(255),
        nullable=False,
        comment='Human-readable name for the Figma installation'
    )
    
    description = Column(
        Text,
        nullable=True,
        comment='Optional detailed description of the installation purpose'
    )
    
    status = Column(
        String(50),
        nullable=False,
        default='active',
        server_default='active',
        comment='PAT validity state: active, expired, or disabled'
    )
    
    # Timestamp Fields
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default='now()',
        comment='Timestamp when the installation was created'
    )
    
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default='now()',
        comment='Timestamp when the installation was last updated'
    )
    
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment='Soft delete timestamp, NULL if installation is active'
    )
    
    # Relationships
    # NOTE: These relationships use string references and viewonly=True
    # to avoid requiring User, Team, etc. models to be defined in this package.
    # When integrating with a full application, these can be configured with
    # back_populates on both sides for bidirectional access.
    
    # Commented out to avoid dependency on external models
    # Uncomment and configure back_populates when integrating into full application
    # user = relationship(
    #     'User',
    #     foreign_keys=[user_id],
    #     viewonly=True,
    #     doc='Owner of the Figma installation'
    # )
    # 
    # team = relationship(
    #     'Team',
    #     foreign_keys=[team_id],
    #     viewonly=True,
    #     doc='Optional team associated with the installation'
    # )
    
    # Relationships to other Figma models in this package
    access_grants = relationship(
        'FigmaInstallationAccess',
        foreign_keys='FigmaInstallationAccess.figma_installation_id',
        back_populates='installation',
        lazy='select',
        doc='Access grants for sharing this installation with other users'
    )
    
    attachments = relationship(
        'FigmaAttachment',
        foreign_keys='FigmaAttachment.figma_installation_id',
        back_populates='installation',
        lazy='select',
        doc='Figma frame attachments using this installation'
    )
    
    # Indexes for query optimization
    # Additional indexes are defined as table args below
    __table_args__ = (
        Index(
            'idx_figma_installation_user',
            'user_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        Index(
            'idx_figma_installation_team',
            'team_id',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        Index(
            'idx_figma_installation_deleted',
            'deleted_at'
        ),
        Index(
            'idx_figma_installation_status',
            'status',
            postgresql_where=Column('deleted_at').is_(None)
        ),
        {
            'comment': 'Stores Figma integration installations with metadata. '
                       'PAT stored separately in Google Secret Manager.'
        }
    )
    
    def __repr__(self) -> str:
        """
        String representation of FigmaInstallation instance.
        
        Returns:
            Human-readable string showing key identifying information.
            NOTE: Does not include PAT or other sensitive data.
        """
        return (
            f"<FigmaInstallation("
            f"id={self.id}, "
            f"name='{self.name}', "
            f"user_id={self.user_id}, "
            f"status='{self.status}', "
            f"deleted={self.deleted_at is not None}"
            f")>"
        )
    
    def is_active(self) -> bool:
        """
        Check if the installation is active (not soft-deleted).
        
        Returns:
            True if deleted_at is None, False otherwise.
        """
        return self.deleted_at is None
    
    def get_secret_name(self) -> str:
        """
        Generate the Google Secret Manager secret name for this installation's PAT.
        
        This method constructs the secret name following the platform's naming
        convention: figma-secret-<installation_id>
        
        Returns:
            String in format 'figma-secret-{id}' for use with Secret Manager.
        
        Raises:
            ValueError: If installation ID is not set (not yet persisted).
        """
        if self.id is None:
            raise ValueError(
                "Cannot generate secret name for installation without ID. "
                "Save the installation to database first."
            )
        return f"figma-secret-{self.id}"
    
    def mark_as_deleted(self) -> None:
        """
        Soft delete this installation by setting deleted_at timestamp.
        
        This method should be called within a transaction context along with
        the corresponding Secret Manager secret deletion to maintain consistency.
        
        Note:
            The caller is responsible for committing the transaction and
            handling Secret Manager deletion.
        """
        self.deleted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def update_status(self, new_status: str) -> None:
        """
        Update the PAT status for this installation.
        
        Args:
            new_status: New status value ('active', 'expired', or 'disabled')
        
        Raises:
            ValueError: If new_status is not a valid status value.
        """
        valid_statuses = {'active', 'expired', 'disabled'}
        if new_status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{new_status}'. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )
        self.status = new_status
        self.updated_at = datetime.utcnow()


# Export the model class for easy imports
__all__ = ['FigmaInstallation', 'Base']
