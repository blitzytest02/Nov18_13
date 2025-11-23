"""
SQLAlchemy ORM model for Figma Integration installations.

This module defines the FigmaInstallation model representing Figma integration
installations owned by users or teams. Each installation represents a connection
to Figma using a Personal Access Token (PAT) stored securely in Google Secret Manager.

The model supports soft deletion via the deleted_at timestamp field, allowing
installations to be marked as deleted without removing historical records. The status
field tracks the validity state of the associated PAT (active/expired/disabled).

Table: figma_installation
Indexes: user_id, team_id, deleted_at for efficient querying
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

# Import the shared declarative base from the models package
# In a typical multi-model project, Base is defined in models/__init__.py or models/base.py
try:
    from . import Base
except ImportError:
    # Fallback: if Base is not available in package __init__, try base module
    try:
        from .base import Base
    except ImportError:
        # Last resort: create a local declarative base
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()


class FigmaInstallation(Base):
    """
    Represents a Figma integration installation owned by a user or team.
    
    A Figma installation connects the Blitzy platform to Figma's API using a
    Personal Access Token (PAT). The PAT itself is stored securely in Google
    Secret Manager with the naming pattern 'figma-secret-<installation_id>',
    while this model stores the installation metadata and status.
    
    The installation can be shared with other users through the
    FigmaInstallationAccess model, enabling team-based collaboration on
    Figma design resources. Installations support soft deletion to maintain
    historical records and referential integrity.
    
    :ivar id: Primary key, unique identifier for the installation
    :type id: int
    :ivar user_id: Owner user ID, references users.id (required)
    :type user_id: int
    :ivar team_id: Optional team association, references teams.id
    :type team_id: Optional[int]
    :ivar name: Display name for the installation (max 255 characters)
    :type name: str
    :ivar description: Optional detailed description of the installation
    :type description: Optional[str]
    :ivar status: Current status - 'active', 'expired', or 'disabled'
    :type status: str
    :ivar created_at: Timestamp when installation was created
    :type created_at: datetime
    :ivar updated_at: Timestamp when installation was last modified
    :type updated_at: datetime
    :ivar deleted_at: Soft delete timestamp, NULL indicates active installation
    :type deleted_at: Optional[datetime]
    
    :ivar owner: Relationship to User model (installation owner)
    :ivar team: Relationship to Team model (optional team association)
    :ivar access_records: Relationship to FigmaInstallationAccess (shared access)
    :ivar attachments: Relationship to FigmaAttachment (linked design frames)
    """
    
    __tablename__ = 'figma_installation'
    
    # Primary Key
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        nullable=False,
        comment='Unique identifier for the Figma installation'
    )
    
    # Foreign Keys
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment='Owner user ID, references users table'
    )
    
    team_id = Column(
        BigInteger,
        ForeignKey('teams.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
        comment='Optional team association, references teams table'
    )
    
    # Data Fields
    name = Column(
        String(255),
        nullable=False,
        comment='Display name for the Figma installation'
    )
    
    description = Column(
        Text,
        nullable=True,
        comment='Detailed description of the installation purpose and scope'
    )
    
    status = Column(
        String(50),
        nullable=False,
        default='active',
        comment='Installation status: active, expired, or disabled'
    )
    
    # Timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment='Timestamp when installation was created'
    )
    
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment='Timestamp when installation was last modified'
    )
    
    # Soft Delete Support
    deleted_at = Column(
        DateTime,
        nullable=True,
        index=True,
        comment='Soft delete timestamp, NULL indicates active installation'
    )
    
    # Relationships
    owner = relationship(
        'User',
        foreign_keys=[user_id],
        backref='figma_installations',
        lazy='joined',
        doc='The user who owns this Figma installation'
    )
    
    team = relationship(
        'Team',
        foreign_keys=[team_id],
        backref='figma_installations',
        lazy='joined',
        doc='Optional team associated with this installation'
    )
    
    access_records = relationship(
        'FigmaInstallationAccess',
        back_populates='installation',
        lazy='dynamic',
        cascade='all, delete-orphan',
        doc='Access grants allowing other users to use this installation'
    )
    
    attachments = relationship(
        'FigmaAttachment',
        back_populates='installation',
        lazy='dynamic',
        cascade='all, delete-orphan',
        doc='Figma frames attached to projects using this installation'
    )
    
    def __repr__(self) -> str:
        """
        Return a string representation of the FigmaInstallation instance.
        
        :return: String representation including id, name, and status
        :rtype: str
        """
        return (
            f"<FigmaInstallation(id={self.id}, name='{self.name}', "
            f"status='{self.status}', user_id={self.user_id})>"
        )
    
    def is_active(self) -> bool:
        """
        Check if the installation is currently active (not soft-deleted).
        
        An installation is considered active if its deleted_at field is NULL.
        This method provides a convenient way to filter out soft-deleted records
        in business logic without directly checking the deleted_at timestamp.
        
        :return: True if installation is active (not deleted), False otherwise
        :rtype: bool
        """
        return self.deleted_at is None
    
    def is_expired(self) -> bool:
        """
        Check if the installation's PAT status is marked as expired.
        
        The status field is updated by the FigmaService when PAT validation
        against the Figma API fails. This method provides a semantic way to
        check expiration status in business logic.
        
        :return: True if status is 'expired', False otherwise
        :rtype: bool
        """
        return self.status == 'expired'
    
    def get_secret_name(self) -> str:
        """
        Generate the Google Secret Manager secret name for this installation's PAT.
        
        The secret naming follows the pattern 'figma-secret-<installation_id>'
        as specified in the Agent Action Plan. This ensures consistent naming
        across secret creation, retrieval, update, and deletion operations.
        
        :return: Secret Manager secret name for this installation's PAT
        :rtype: str
        """
        return f"figma-secret-{self.id}"


# Create indexes for efficient querying
# These indexes support common query patterns: filtering by owner, team, and active status
Index('idx_figma_installation_user', FigmaInstallation.user_id)
Index('idx_figma_installation_team', FigmaInstallation.team_id)
Index('idx_figma_installation_deleted', FigmaInstallation.deleted_at)
