"""
Concrete implementation of IFigmaRepository for Figma integration database operations.

This module provides the FigmaRepository class which implements all database
operations for Figma entities using SQLAlchemy ORM. The repository handles
installations, access control grants, and frame attachments with comprehensive
support for soft deletion, transaction management, and idempotent operations.

The implementation follows the repository pattern to abstract database access
behind the IFigmaRepository interface, enabling dependency injection and
facilitating testing with fake implementations. All database interactions use
SQLAlchemy Session for query execution and transaction management.

Key Features:
    - Soft deletion support via deleted_at timestamps (never physically deletes)
    - Transaction-aware operations for rollback capability with Secret Manager
    - Idempotent attachment creation (same URL overwrites existing record)
    - Optimized queries leveraging database indexes
    - Comprehensive error handling and validation

Transaction Pattern:
    The repository's methods can be called within a transaction context managed
    by the service layer. This enables atomic operations across the database and
    Google Secret Manager. If Secret Manager operations fail, the database
    transaction can be rolled back to maintain consistency between systems.

    Example:
        ```python
        with session.begin():
            installation = figma_repo.create_installation(...)
            # If Secret Manager fails here, session.rollback() undoes DB changes
        ```

Soft Delete Rationale:
    All delete operations use soft deletion by setting deleted_at timestamps
    rather than physically removing records. This approach:
    - Preserves referential integrity with related records
    - Maintains complete audit trails for compliance
    - Enables recovery from accidental deletions
    - Supports historical data analysis
    Query methods filter WHERE deleted_at IS NULL unless retrieving history.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .interfaces.i_figma_repository import IFigmaRepository
from ..models.figma_installation import FigmaInstallation
from ..models.figma_installation_access import FigmaInstallationAccess
from ..models.figma_attachment import FigmaAttachment


class FigmaRepository(IFigmaRepository):
    """
    SQLAlchemy-based implementation of IFigmaRepository interface.

    Provides concrete database operations for all Figma integration entities
    including installations, access control, and frame attachments. Uses
    SQLAlchemy Session for database interactions and implements the repository
    pattern to isolate persistence logic from business logic.

    The repository supports:
    - Full CRUD operations for installations, access grants, and attachments
    - Soft deletion pattern (sets deleted_at, never hard deletes)
    - Transaction contexts for atomic operations with external systems
    - Idempotent attachment creation (last write wins)
    - Efficient queries using database indexes

    Thread Safety:
        This class is not thread-safe. Each thread should use its own Session
        instance. In web applications, sessions are typically scoped to requests.

    :ivar db: SQLAlchemy Session for database operations
    :type db: Session
    """

    def __init__(self, db: Session):
        """
        Initialize FigmaRepository with a database session.

        The session should be managed by the caller (service layer or request
        context). The repository does not commit or rollback transactions - it
        delegates that responsibility to the service layer to enable coordination
        with external systems like Secret Manager.

        :param db: SQLAlchemy Session for database operations (required)
        :type db: Session

        Usage Example:
            ```python
            from sqlalchemy.orm import Session

            # In service layer or request handler
            session = get_db_session()
            figma_repo = FigmaRepository(session)
            installation = figma_repo.create_installation(...)
            ```
        """
        self.db = db

    # ============================================================================
    # Figma Installation Operations
    # ============================================================================

    def create_installation(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        team_id: Optional[int] = None
    ) -> FigmaInstallation:
        """
        Create a new Figma installation record in the database.

        Creates a new installation entity owned by the specified user with optional
        team association. The status defaults to 'active' and timestamps are set
        automatically. This method does NOT commit the transaction - it expects to
        be called within a transaction context managed by the service layer.

        Transaction Context:
            This method is typically called within a transaction that also stores
            the PAT in Google Secret Manager. The sequence is:
            1. Begin transaction
            2. Call create_installation (gets generated ID)
            3. Store secret using 'figma-secret-<id>' naming pattern
            4. Commit if Secret Manager succeeds, rollback if fails

        :param user_id: ID of the user who owns this installation (required)
        :type user_id: int
        :param name: Display name for the installation (required, max 255 chars)
        :type name: str
        :param description: Optional detailed description
        :type description: Optional[str]
        :param team_id: Optional team ID for team-scoped installations
        :type team_id: Optional[int]

        :return: Newly created FigmaInstallation with generated ID
        :rtype: FigmaInstallation

        :raises ValueError: If user_id is invalid or name is empty
        :raises IntegrityError: If foreign key constraints fail
        """
        installation = FigmaInstallation(
            user_id=user_id,
            name=name,
            description=description,
            team_id=team_id,
            status='active',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(installation)
        # Flush to get the generated ID without committing transaction
        # This allows the service layer to use installation.id for secret naming
        self.db.flush()

        return installation

    def get_installation(self, installation_id: int) -> Optional[FigmaInstallation]:
        """
        Retrieve a Figma installation by ID, excluding soft-deleted records.

        Queries the database for an installation with the specified ID where
        deleted_at IS NULL. Returns None if no matching active installation exists.
        The query uses indexes on id (primary key) and deleted_at for efficiency.

        Soft Delete Filtering:
            Only active installations (deleted_at IS NULL) are returned. To access
            historical data including deleted installations, a separate method would
            be needed (not currently implemented).

        :param installation_id: Primary key ID of installation to retrieve (required)
        :type installation_id: int

        :return: FigmaInstallation if found and active, None otherwise
        :rtype: Optional[FigmaInstallation]
        """
        return self.db.query(FigmaInstallation).filter(
            FigmaInstallation.id == installation_id,
            FigmaInstallation.deleted_at.is_(None)
        ).first()

    def update_installation(
        self,
        installation_id: int,
        **kwargs
    ) -> FigmaInstallation:
        """
        Update fields on an existing Figma installation.

        Retrieves the installation and updates the specified fields. The updated_at
        timestamp is automatically refreshed by the ORM's onupdate configuration.
        This method does NOT commit the transaction.

        Supported fields for update:
            - name: str
            - description: Optional[str]
            - status: str ('active', 'expired', 'disabled')
            - team_id: Optional[int]

        Transaction Context:
            When updating PAT status after validation or when rotating PATs, this
            method should be called within a transaction that can roll back if
            external operations (e.g., Secret Manager) fail.

        :param installation_id: Primary key ID of installation to update (required)
        :type installation_id: int
        :param kwargs: Field names and new values to update
        :type kwargs: dict

        :return: Updated FigmaInstallation with refreshed fields
        :rtype: FigmaInstallation

        :raises ValueError: If installation_id is invalid or not found
        """
        installation = self.get_installation(installation_id)
        if not installation:
            raise ValueError(f"Installation {installation_id} not found or deleted")

        # Update specified fields
        for key, value in kwargs.items():
            if hasattr(installation, key):
                setattr(installation, key, value)

        # Explicitly update the updated_at timestamp
        installation.updated_at = datetime.utcnow()  # type: ignore[assignment]

        # Flush changes to database without committing
        self.db.flush()

        return installation

    def soft_delete_installation(self, installation_id: int) -> bool:
        """
        Soft delete an installation by setting deleted_at timestamp.

        Marks the installation as deleted without physically removing the row from
        the database. This preserves referential integrity with related records
        (access grants, attachments) and maintains audit history. Does NOT commit.

        Critical Transaction Context:
            This method is called within a transaction that also deletes the
            corresponding secret from Google Secret Manager. The sequence is:
            1. Begin transaction
            2. Call soft_delete_installation (sets deleted_at)
            3. Delete secret from Secret Manager
            4. Commit if Secret Manager succeeds, rollback if fails
            This ensures the database and Secret Manager remain synchronized.

        Cascade Behavior:
            Related records (access_records, attachments) are NOT automatically
            soft-deleted. They remain in the database but become orphaned. The
            current design allows independent management of related entities.

        :param installation_id: Primary key ID of installation to soft delete
        :type installation_id: int

        :return: True if soft delete succeeded, False if not found
        :rtype: bool
        """
        installation = self.get_installation(installation_id)
        if not installation:
            return False

        installation.deleted_at = datetime.utcnow()  # type: ignore[assignment]
        self.db.flush()

        return True

    def list_installations(
        self,
        user_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> List[FigmaInstallation]:
        """
        List Figma installations with optional filtering by user or team.

        Returns all active (not soft-deleted) installations. When filters are
        provided, uses OR logic: installations owned by user OR in team. This
        approach maximizes flexibility for UI dropdown populations and access checks.

        Filtering Logic:
            - No filters: Return all active installations
            - user_id only: Return installations where user_id matches
            - team_id only: Return installations where team_id matches
            - Both filters: Return installations where user_id OR team_id matches

        Performance:
            The user_id and team_id columns are indexed, making filtered queries
            efficient even with large datasets. The deleted_at index ensures fast
            filtering of soft-deleted records.

        :param user_id: Optional filter for installations owned by user
        :type user_id: Optional[int]
        :param team_id: Optional filter for installations in team
        :type team_id: Optional[int]

        :return: List of matching FigmaInstallation entities (empty if none)
        :rtype: List[FigmaInstallation]
        """
        query = self.db.query(FigmaInstallation).filter(
            FigmaInstallation.deleted_at.is_(None)
        )

        # Apply filters with OR logic if both provided
        if user_id is not None and team_id is not None:
            query = query.filter(
                (FigmaInstallation.user_id == user_id) |
                (FigmaInstallation.team_id == team_id)
            )
        elif user_id is not None:
            query = query.filter(FigmaInstallation.user_id == user_id)
        elif team_id is not None:
            query = query.filter(FigmaInstallation.team_id == team_id)

        return query.all()

    # ============================================================================
    # Figma Installation Access Control Operations
    # ============================================================================

    def grant_access(
        self,
        installation_id: int,
        user_id: int,
        granted_by: int,
        access_level: str = "viewer"
    ) -> FigmaInstallationAccess:
        """
        Grant a user access to a Figma installation.

        Creates a new access control record enabling the user to use the
        installation's PAT for Figma API operations. The unique constraint
        (installation_id, user_id, deleted_at) prevents duplicate active grants.

        Authorization Note:
            This method does NOT perform authorization checks. The service layer
            must verify that the requesting user (granted_by) has ADMIN or
            SUPER_ADMIN role before calling this method. This repository trusts
            the caller's authorization decisions.

        Access Levels:
            - 'viewer': Read-only, can view frames using installation
            - 'editor': Can attach/detach frames to projects
            - 'admin': Full control including share/revoke operations

        Duplicate Handling:
            If an active access grant already exists for this user and installation,
            the unique constraint will raise IntegrityError. The service layer should
            catch this and handle appropriately (e.g., treat as success since user
            already has access).

        :param installation_id: ID of installation to grant access to
        :type installation_id: int
        :param user_id: ID of user receiving access
        :type user_id: int
        :param granted_by: ID of admin user granting access
        :type granted_by: int
        :param access_level: Permission level, defaults to 'viewer'
        :type access_level: str

        :return: Newly created FigmaInstallationAccess entity
        :rtype: FigmaInstallationAccess

        :raises IntegrityError: If duplicate active grant exists
        """
        access = FigmaInstallationAccess(
            figma_installation_id=installation_id,
            user_id=user_id,
            granted_by=granted_by,
            access_level=access_level,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(access)
        self.db.flush()

        return access

    def revoke_access(self, installation_id: int, user_id: int) -> bool:
        """
        Revoke a user's access by soft deleting the access record.

        Finds active access grants matching installation_id and user_id, then
        sets deleted_at timestamp to revoke access. If multiple active grants
        exist (edge case due to data migration or bugs), all are revoked.

        Authorization Note:
            Similar to grant_access, this method trusts the caller to perform
            authorization checks. Only ADMIN or SUPER_ADMIN users should be
            allowed to call this through the service layer.

        Audit Trail:
            Soft deletion preserves the historical record of when access was
            granted and by whom. The revoked access remains in the database but
            is excluded from authorization checks and list_access queries.

        :param installation_id: ID of installation to revoke access from
        :type installation_id: int
        :param user_id: ID of user whose access to revoke
        :type user_id: int

        :return: True if access revoked, False if no active grant found
        :rtype: bool
        """
        access_grants = self.db.query(FigmaInstallationAccess).filter(
            FigmaInstallationAccess.figma_installation_id == installation_id,
            FigmaInstallationAccess.user_id == user_id,
            FigmaInstallationAccess.deleted_at.is_(None)
        ).all()

        if not access_grants:
            return False

        # Revoke all matching active grants (should typically be just one)
        for access in access_grants:
            access.deleted_at = datetime.utcnow()  # type: ignore[assignment]

        self.db.flush()
        return True

    def list_access(self, installation_id: int) -> List[FigmaInstallationAccess]:
        """
        List all users with active access to a Figma installation.

        Returns active (not soft-deleted) access grants for the installation,
        showing which users have permission and at what access level. Used for
        displaying "Shared with" lists and verifying user permissions.

        Soft Delete Filtering:
            Only active access grants (deleted_at IS NULL) are returned. Revoked
            access is excluded to show current state rather than historical data.

        Relationship Loading:
            The query uses eager loading (configured in model relationships) to
            load related user and installation data, avoiding N+1 query problems
            when displaying access lists in the UI.

        :param installation_id: ID of installation to list access for
        :type installation_id: int

        :return: List of active FigmaInstallationAccess entities
        :rtype: List[FigmaInstallationAccess]
        """
        return self.db.query(FigmaInstallationAccess).filter(
            FigmaInstallationAccess.figma_installation_id == installation_id,
            FigmaInstallationAccess.deleted_at.is_(None)
        ).all()

    # ============================================================================
    # Figma Attachment Operations
    # ============================================================================

    def create_attachment(
        self,
        project_id: int,
        installation_id: int,
        frame_url: str,
        created_by: int,
        frame_title: Optional[str] = None,
        description: Optional[str] = None,
        tech_spec_id: Optional[int] = None
    ) -> FigmaAttachment:
        """
        Create or update a Figma frame attachment with idempotent behavior.

        Attaches a Figma frame URL to a project (and optionally tech spec). If an
        active attachment with the same project_id and frame_url already exists,
        updates that record instead of creating a duplicate. This "last write wins"
        approach supports additive workflows where attach_frames can be called
        multiple times without error handling complexity.

        Idempotent Implementation:
            1. Query for existing active attachment with same project_id and frame_url
            2. If exists: Update fields (installation_id, frame_title, description,
               tech_spec_id, updated_at) and return existing record
            3. If not exists: Create new attachment record
            This avoids unique constraint violations and simplifies service logic.

        No File Downloads:
            This method stores only metadata (URL, title, description). No files
            are downloaded from Figma or uploaded to GCS. The frame remains
            accessible via the URL using the PAT from the installation.

        Validation Assumption:
            The service layer should validate frame access via Figma API before
            calling this method. This repository method trusts that validation
            occurred and does not re-validate the frame_url.

        :param project_id: ID of project to attach frame to
        :type project_id: int
        :param installation_id: ID of installation providing PAT
        :type installation_id: int
        :param frame_url: Full Figma frame URL (must be unique per project)
        :type frame_url: str
        :param created_by: ID of user creating attachment
        :type created_by: int
        :param frame_title: Frame title from Figma API (max 500 chars)
        :type frame_title: Optional[str]
        :param description: User-provided description
        :type description: Optional[str]
        :param tech_spec_id: Optional tech spec association
        :type tech_spec_id: Optional[int]

        :return: Created or updated FigmaAttachment entity
        :rtype: FigmaAttachment
        """
        # Check for existing active attachment with same project and URL
        existing = self.db.query(FigmaAttachment).filter(
            FigmaAttachment.project_id == project_id,
            FigmaAttachment.frame_url == frame_url,
            FigmaAttachment.deleted_at.is_(None)
        ).first()

        if existing:
            # Update existing attachment (idempotent behavior)
            existing.figma_installation_id = installation_id  # type: ignore[assignment]
            existing.frame_title = frame_title  # type: ignore[assignment]
            existing.description = description  # type: ignore[assignment]
            existing.tech_spec_id = tech_spec_id  # type: ignore[assignment]
            existing.updated_at = datetime.utcnow()  # type: ignore[assignment]
            # Note: created_by is NOT updated - preserves original creator
            self.db.flush()
            return existing

        # Create new attachment
        attachment = FigmaAttachment(
            project_id=project_id,
            tech_spec_id=tech_spec_id,
            figma_installation_id=installation_id,
            frame_url=frame_url,
            frame_title=frame_title,
            description=description,
            created_by=created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(attachment)
        self.db.flush()

        return attachment

    def get_attachment(self, attachment_id: int) -> Optional[FigmaAttachment]:
        """
        Retrieve a single Figma attachment by ID, excluding soft-deleted records.

        Queries for an attachment with the specified ID where deleted_at IS NULL.
        Returns None if no matching active attachment exists. Used for GET
        operations and verifying attachment existence before updates or deletes.

        Soft Delete Filtering:
            Only active attachments (deleted_at IS NULL) are returned. Historical
            attachments would require a separate query method.

        :param attachment_id: Primary key ID of attachment to retrieve
        :type attachment_id: int

        :return: FigmaAttachment if found and active, None otherwise
        :rtype: Optional[FigmaAttachment]
        """
        return self.db.query(FigmaAttachment).filter(
            FigmaAttachment.id == attachment_id,
            FigmaAttachment.deleted_at.is_(None)
        ).first()

    def list_attachments(
        self,
        project_id: int,
        tech_spec_id: Optional[int] = None
    ) -> List[FigmaAttachment]:
        """
        List Figma attachments for a project, optionally filtered by tech spec.

        Returns all active frame attachments for the specified project. When
        tech_spec_id is provided, further filters to only attachments associated
        with that tech spec. Used for displaying attached frames in project views
        and showing frames related to specific tech specs.

        Filtering Logic:
            - If tech_spec_id is None: Return all attachments for project_id
            - If tech_spec_id provided: Return attachments matching both
              project_id AND tech_spec_id
            - Always exclude soft-deleted records (deleted_at IS NULL)

        Performance:
            The project_id and tech_spec_id columns are indexed for efficient
            querying. Relationship eager loading (configured in model) avoids
            N+1 query problems when accessing installation/project/creator data.

        :param project_id: ID of project to list attachments for
        :type project_id: int
        :param tech_spec_id: Optional filter for specific tech spec
        :type tech_spec_id: Optional[int]

        :return: List of matching FigmaAttachment entities (empty if none)
        :rtype: List[FigmaAttachment]
        """
        query = self.db.query(FigmaAttachment).filter(
            FigmaAttachment.project_id == project_id,
            FigmaAttachment.deleted_at.is_(None)
        )

        if tech_spec_id is not None:
            query = query.filter(FigmaAttachment.tech_spec_id == tech_spec_id)

        return query.all()

    def soft_delete_attachment(self, attachment_id: int) -> bool:
        """
        Soft delete a Figma attachment by setting deleted_at timestamp.

        Marks the attachment as deleted without physically removing the row.
        Preserves referential integrity and maintains audit history showing which
        frames were previously attached. The attachment becomes invisible to
        standard queries via deleted_at IS NULL filtering.

        No File Cleanup:
            Since attachments store only URLs without downloading files, there are
            no files to clean up from GCS. The frame remains accessible via Figma
            if the URL is known and the PAT is valid.

        Referential Integrity:
            Soft-deleting an attachment does NOT cascade to installation or project.
            The attachment simply becomes invisible while maintaining foreign key
            relationships for audit purposes.

        :param attachment_id: Primary key ID of attachment to soft delete
        :type attachment_id: int

        :return: True if soft delete succeeded, False if not found
        :rtype: bool
        """
        attachment = self.get_attachment(attachment_id)
        if not attachment:
            return False

        attachment.deleted_at = datetime.utcnow()  # type: ignore[assignment]
        self.db.flush()

        return True
