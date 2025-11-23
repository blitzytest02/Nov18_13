"""
Repository interface for Figma integration database operations.

This module defines the IFigmaRepository abstract base class that specifies the contract
for all database interactions related to Figma installations, access control, and
frame attachments. The interface enables clean separation between business logic and
data persistence, supporting the dependency injection pattern and facilitating testing
with fake implementations.

The interface encompasses three primary entity domains:
1. Figma Installations - Core integration records with metadata
2. Installation Access - Role-based access control for sharing integrations
3. Frame Attachments - Lightweight references to Figma design frames

All operations support soft deletion via deleted_at timestamps, ensuring historical
records are preserved while allowing logical removal of entities. Implementations must
properly filter soft-deleted records in query operations unless explicitly retrieving
historical data.

Transaction Support:
    Implementations must provide transaction contexts that enable atomic operations
    across database writes and external Secret Manager operations. When Secret Manager
    operations fail, database transactions must be rolled back to maintain consistency
    between the two systems. See create_installation and soft_delete_installation for
    critical transaction boundary examples.

Soft Delete Pattern:
    All delete operations use soft deletion by setting deleted_at timestamps rather
    than physically removing records. Query methods must filter WHERE deleted_at IS NULL
    unless the operation specifically requires historical data. This pattern maintains
    referential integrity, supports audit trails, and enables recovery from accidental
    deletions.

Idempotent Attachments:
    The create_attachment method implements idempotent behavior where providing the
    same frame_url for the same project_id will update the existing attachment rather
    than failing with a uniqueness constraint violation. This "last write wins" approach
    supports additive workflows where attachments can be called multiple times without
    error handling complexity.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, List

# Conditional imports for type checking to avoid circular dependencies
# These models are only imported during static type analysis (mypy, pyright)
# but not at runtime, preventing circular import errors while enabling
# proper type hints for interface method signatures
if TYPE_CHECKING:
    from ...models.figma_installation import FigmaInstallation
    from ...models.figma_installation_access import FigmaInstallationAccess
    from ...models.figma_attachment import FigmaAttachment


class IFigmaRepository(ABC):
    """
    Abstract repository interface for Figma integration database operations.

    Defines the complete contract for persisting and retrieving Figma integration
    data across three entity types: installations, access control grants, and frame
    attachments. Concrete implementations (e.g., FigmaRepository) must provide all
    methods, while test implementations (e.g., FakeFigmaRepository) can use in-memory
    data structures to simulate database behavior.

    Design Principles:
        - Repository pattern abstracts all database access behind interfaces
        - Dependency injection allows swapping implementations for testing
        - Soft deletes preserve data integrity and support audit requirements
        - Transaction support enables rollback on external system failures
        - Type hints provide static analysis and IDE assistance

    Usage Example:
        ```python
        # Service layer uses injected repository
        class FigmaService:
            def __init__(self, figma_repo: IFigmaRepository):
                self.figma_repo = figma_repo

            def create_with_transaction(self, data, pat):
                with transaction():
                    installation = self.figma_repo.create_installation(...)
                    # If Secret Manager fails, transaction rolls back
                ```

    Implementation Requirements:
        - All query methods must filter soft-deleted records (deleted_at IS NULL)
        - Create methods must return newly created entities with generated IDs
        - Update methods must refresh updated_at timestamps automatically
        - List methods must support optional filtering without complex query builders
        - Soft delete methods must only set deleted_at, never physically delete rows
    """

    # ============================================================================
    # Figma Installation Operations
    # ============================================================================

    @abstractmethod
    def create_installation(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        team_id: Optional[int] = None
    ) -> "FigmaInstallation":
        """
        Create a new Figma installation record.

        This method creates the database record for a Figma installation owned by a
        user and optionally associated with a team. The actual Personal Access Token
        (PAT) is stored separately in Google Secret Manager using the pattern
        'figma-secret-<installation_id>', so this method only handles metadata.

        Critical Transaction Context:
            This method is typically called within a transaction that also stores the
            PAT in Secret Manager. If Secret Manager operations fail after this method
            succeeds, the calling code must roll back the database transaction to
            maintain consistency between the DB and Secret Manager.

        The status field defaults to 'active' and will be updated later based on
        PAT validation results. The created_at and updated_at timestamps are set
        automatically by the database or ORM.

        :param user_id: ID of the user who owns this installation (required)
        :type user_id: int
        :param name: Display name for the installation, shown in UI (required)
        :type name: str
        :param description: Optional detailed description of the installation's purpose
        :type description: Optional[str]
        :param team_id: Optional team ID if installation is team-scoped
        :type team_id: Optional[int]

        :return: Newly created FigmaInstallation entity with generated ID
        :rtype: FigmaInstallation

        :raises ValueError: If user_id is invalid or name is empty/too long
        :raises IntegrityError: If foreign key constraints fail (invalid user_id/team_id)
        :raises DatabaseError: If database operation fails

        Usage Example:
            ```python
            installation = figma_repo.create_installation(
                user_id=123,
                name="Design System Tokens",
                description="PAT for accessing design system Figma files",
                team_id=456
            )
            print(f"Created installation {installation.id}")
            ```
        """
        pass

    @abstractmethod
    def get_installation(self, installation_id: int) -> Optional["FigmaInstallation"]:
        """
        Retrieve a single Figma installation by ID, excluding soft-deleted records.

        Returns the installation metadata if it exists and has not been soft-deleted
        (deleted_at IS NULL). This method is used for GET operations, update operations,
        and authorization checks where only active installations should be visible.

        Soft Delete Filtering:
            Implementations must filter WHERE deleted_at IS NULL to exclude soft-deleted
            installations. If historical data access is needed, a separate method should
            be added (e.g., get_installation_including_deleted).

        :param installation_id: Primary key ID of the installation to retrieve
        :type installation_id: int

        :return: FigmaInstallation entity if found and active, None if not found or deleted
        :rtype: Optional[FigmaInstallation]

        :raises DatabaseError: If database query fails

        Usage Example:
            ```python
            installation = figma_repo.get_installation(123)
            if installation:
                print(f"Found: {installation.name}")
            else:
                print("Installation not found or deleted")
            ```
        """
        pass

    @abstractmethod
    def update_installation(
        self,
        installation_id: int,
        **kwargs
    ) -> "FigmaInstallation":
        """
        Update fields on an existing Figma installation.

        Accepts arbitrary keyword arguments corresponding to model fields that should
        be updated. The updated_at timestamp is automatically refreshed. This method
        is used for operations like updating the installation name, description, or
        status field (e.g., changing from 'active' to 'expired' after PAT validation).

        Implementations should validate that the installation exists and is not
        soft-deleted before applying updates. The method returns the updated entity
        with refreshed field values.

        Supported Update Fields:
            - name: str - Display name
            - description: Optional[str] - Description text
            - status: str - Status value ('active', 'expired', 'disabled')
            - team_id: Optional[int] - Team association

        Transaction Boundary:
            When used in conjunction with Secret Manager updates (e.g., update_pat),
            this method should be called within a transaction that can roll back if
            Secret Manager operations fail.

        :param installation_id: Primary key ID of installation to update (required)
        :type installation_id: int
        :param kwargs: Field names and new values to update
        :type kwargs: dict

        :return: Updated FigmaInstallation entity with refreshed fields
        :rtype: FigmaInstallation

        :raises ValueError: If installation_id is invalid or kwargs contain invalid fields
        :raises NotFoundError: If installation does not exist or is soft-deleted
        :raises DatabaseError: If database update fails

        Usage Example:
            ```python
            # Update status after PAT validation
            installation = figma_repo.update_installation(
                installation_id=123,
                status='expired'
            )

            # Update multiple fields
            installation = figma_repo.update_installation(
                installation_id=123,
                name="New Name",
                description="Updated description"
            )
            ```
        """
        pass

    @abstractmethod
    def soft_delete_installation(self, installation_id: int) -> bool:
        """
        Soft delete a Figma installation by setting deleted_at timestamp.

        Marks the installation as deleted without physically removing the database row.
        This preserves referential integrity with related records (access grants,
        attachments) and maintains audit history. Soft-deleted installations are
        excluded from normal queries via deleted_at IS NULL filtering.

        Critical Transaction Context:
            This method is typically called within a transaction that also deletes the
            corresponding secret from Google Secret Manager. If Secret Manager deletion
            fails after this method succeeds, the transaction must roll back to prevent
            orphaned secrets that cannot be accessed (no DB record) but still exist in
            Secret Manager consuming resources.

        The method sets deleted_at to the current timestamp (typically CURRENT_TIMESTAMP
        in SQL or datetime.utcnow() in Python). The installation record remains in the
        database but becomes invisible to queries that filter on deleted_at IS NULL.

        Cascade Implications:
            Implementations should consider whether to also soft-delete related records
            (access grants, attachments) or leave them orphaned. The current design
            leaves related records intact, allowing them to be independently managed.

        :param installation_id: Primary key ID of installation to soft delete
        :type installation_id: int

        :return: True if soft delete succeeded, False if installation not found
        :rtype: bool

        :raises DatabaseError: If database update fails

        Usage Example:
            ```python
            success = figma_repo.soft_delete_installation(123)
            if success:
                print("Installation soft-deleted successfully")
            else:
                print("Installation not found")
            ```
        """
        pass

    @abstractmethod
    def list_installations(
        self,
        user_id: Optional[int] = None,
        team_id: Optional[int] = None
    ) -> List["FigmaInstallation"]:
        """
        List Figma installations with optional filtering by user or team.

        Returns all active (not soft-deleted) installations, optionally filtered by
        ownership (user_id) or team association (team_id). When both filters are
        provided, implementations may choose to combine them with AND logic (installations
        owned by user AND in team) or OR logic (owned by user OR in team). The OR
        approach is recommended for flexibility.

        This method is used for:
        - Listing installations available to a user (via ownership or team membership)
        - Displaying installation selection dropdowns in the UI
        - Administrative views showing all installations for a team

        Soft Delete Filtering:
            Implementations must filter WHERE deleted_at IS NULL to show only active
            installations. Historical data should be accessed via separate methods if needed.

        Performance Considerations:
            The user_id and team_id fields are indexed, so filtering by these fields
            should be efficient even with large installation tables. Consider limiting
            results or adding pagination for very large datasets.

        :param user_id: Optional filter for installations owned by specific user
        :type user_id: Optional[int]
        :param team_id: Optional filter for installations associated with specific team
        :type team_id: Optional[int]

        :return: List of matching FigmaInstallation entities (empty list if none found)
        :rtype: List[FigmaInstallation]

        :raises DatabaseError: If database query fails

        Usage Example:
            ```python
            # List all installations owned by user
            user_installations = figma_repo.list_installations(user_id=123)

            # List all installations for a team
            team_installations = figma_repo.list_installations(team_id=456)

            # List all installations (no filters)
            all_installations = figma_repo.list_installations()
            ```
        """
        pass

    # ============================================================================
    # Figma Installation Access Control Operations
    # ============================================================================

    @abstractmethod
    def grant_access(
        self,
        installation_id: int,
        user_id: int,
        granted_by: int,
        access_level: str = "viewer"
    ) -> "FigmaInstallationAccess":
        """
        Grant a user access to a Figma installation with specified access level.

        Creates a new access control record allowing the specified user to use the
        Figma installation's PAT for API operations. This enables sharing integrations
        across team members without exposing the actual PAT value. The granted_by
        parameter records which admin user authorized the access for audit purposes.

        Authorization Context:
            This method should only be called after verifying that the requesting user
            (granted_by) has ADMIN or SUPER_ADMIN role. The authorization check is
            performed in the service layer by querying teams and teammembers tables.
            This repository method performs no authorization - it trusts the caller.

        Access Levels:
            - 'viewer': Read-only, can view frames using the installation
            - 'editor': Can attach/detach frames to projects
            - 'admin': Full control including granting/revoking access

        Duplicate Prevention:
            The unique constraint (figma_installation_id, user_id, deleted_at) prevents
            duplicate active access grants. If a previous grant was soft-deleted and
            access is being re-granted, implementations should create a new record
            rather than un-deleting the old one to preserve audit history.

        :param installation_id: ID of installation to grant access to (required)
        :type installation_id: int
        :param user_id: ID of user receiving access (required)
        :type user_id: int
        :param granted_by: ID of admin user granting access (required)
        :type granted_by: int
        :param access_level: Permission level ('viewer', 'editor', 'admin'), defaults to 'viewer'
        :type access_level: str

        :return: Newly created FigmaInstallationAccess entity
        :rtype: FigmaInstallationAccess

        :raises ValueError: If IDs are invalid or access_level is not recognized
        :raises IntegrityError: If unique constraint violated (duplicate active grant)
        :raises DatabaseError: If database operation fails

        Usage Example:
            ```python
            access = figma_repo.grant_access(
                installation_id=123,
                user_id=456,
                granted_by=789,
                access_level='editor'
            )
            print(f"Access granted: {access.id}")
            ```
        """
        pass

    @abstractmethod
    def revoke_access(self, installation_id: int, user_id: int) -> bool:
        """
        Revoke a user's access to a Figma installation by soft deleting the access record.

        Removes access by setting the deleted_at timestamp on the matching
        FigmaInstallationAccess record. The user will no longer be able to use the
        installation's PAT after revocation. The historical record is preserved for
        audit purposes.

        Authorization Context:
            Similar to grant_access, this method should only be called after verifying
            that the requesting user has ADMIN or SUPER_ADMIN role. Authorization is
            the responsibility of the service layer, not this repository method.

        If multiple active access records exist for the same installation_id and user_id
        (which should be prevented by unique constraints but may occur in edge cases),
        implementations should soft-delete all matching records.

        :param installation_id: ID of installation to revoke access from (required)
        :type installation_id: int
        :param user_id: ID of user whose access should be revoked (required)
        :type user_id: int

        :return: True if access was revoked, False if no active access record found
        :rtype: bool

        :raises DatabaseError: If database update fails

        Usage Example:
            ```python
            revoked = figma_repo.revoke_access(
                installation_id=123,
                user_id=456
            )
            if revoked:
                print("Access revoked successfully")
            else:
                print("No active access found to revoke")
            ```
        """
        pass

    @abstractmethod
    def list_access(self, installation_id: int) -> List["FigmaInstallationAccess"]:
        """
        List all users with active access to a Figma installation.

        Returns all active (not soft-deleted) access grants for the specified installation,
        showing which users have permission to use the installation and at what access
        level. This method is used for:
        - Displaying the "Shared with" list in the UI
        - Verifying user permissions before allowing operations
        - Administrative audit of access grants

        Soft Delete Filtering:
            Implementations must filter WHERE deleted_at IS NULL to show only active
            access grants. Revoked access (deleted_at IS NOT NULL) should not appear
            in the results unless a separate historical query method is implemented.

        The results typically include relationship data (user, installation, granted_by_user)
        for display purposes. Implementations may use eager loading (e.g., SQLAlchemy
        joinedload) to avoid N+1 query problems when accessing relationships.

        :param installation_id: ID of installation to list access for (required)
        :type installation_id: int

        :return: List of active FigmaInstallationAccess entities (empty list if none)
        :rtype: List[FigmaInstallationAccess]

        :raises DatabaseError: If database query fails

        Usage Example:
            ```python
            access_grants = figma_repo.list_access(installation_id=123)
            for grant in access_grants:
                print(f"User {grant.user_id} has {grant.access_level} access")
            ```
        """
        pass

    # ============================================================================
    # Figma Attachment Operations
    # ============================================================================

    @abstractmethod
    def create_attachment(
        self,
        project_id: int,
        installation_id: int,
        frame_url: str,
        created_by: int,
        frame_title: Optional[str] = None,
        description: Optional[str] = None,
        tech_spec_id: Optional[int] = None
    ) -> "FigmaAttachment":
        """
        Create or update a Figma frame attachment to a project with idempotent behavior.

        Attaches a Figma frame URL to a project (and optionally a tech spec) for
        reference during development. The frame_title is retrieved from the Figma API
        during validation before calling this method. This operation is idempotent:
        if the same frame_url already exists for the project_id, the existing attachment
        is updated rather than creating a duplicate or raising an error.

        Idempotent Behavior ("Last Write Wins"):
            The unique constraint (project_id, frame_url, deleted_at) ensures only one
            active attachment per frame URL per project. Implementations should:
            1. Check if an active attachment exists with the same project_id and frame_url
            2. If exists: Update the existing record's fields and updated_at timestamp
            3. If not exists: Create a new attachment record
            This approach supports additive workflows where attach_frames can be called
            multiple times without complex error handling or deduplication logic.

        No File Downloads:
            This method stores only metadata (URL, title, description). No Figma files
            are downloaded or uploaded to GCS. The frame remains accessible via the URL
            using the PAT from the associated installation.

        Validation Context:
            Before calling this method, the service layer should validate frame access
            using the Figma API to ensure the PAT can access the frame_url. This method
            trusts that validation has occurred and does not re-validate.

        :param project_id: ID of project to attach frame to (required)
        :type project_id: int
        :param installation_id: ID of installation providing PAT for frame access (required)
        :type installation_id: int
        :param frame_url: Full Figma frame URL (required, must be unique per project)
        :type frame_url: str
        :param created_by: ID of user creating the attachment (required)
        :type created_by: int
        :param frame_title: Frame title from Figma API (optional, max 500 chars)
        :type frame_title: Optional[str]
        :param description: User-provided description of frame's purpose (optional)
        :type description: Optional[str]
        :param tech_spec_id: Optional tech spec to associate frame with (optional)
        :type tech_spec_id: Optional[int]

        :return: Created or updated FigmaAttachment entity
        :rtype: FigmaAttachment

        :raises ValueError: If required IDs are invalid or frame_url is malformed
        :raises IntegrityError: If foreign key constraints fail
        :raises DatabaseError: If database operation fails

        Usage Example:
            ```python
            # First attachment of frame to project
            attachment = figma_repo.create_attachment(
                project_id=100,
                installation_id=123,
                frame_url="https://figma.com/file/ABC?node-id=1:2",
                created_by=456,
                frame_title="Login Screen",
                description="Main login interface design"
            )

            # Calling again with same frame_url updates the existing attachment
            updated = figma_repo.create_attachment(
                project_id=100,
                installation_id=123,
                frame_url="https://figma.com/file/ABC?node-id=1:2",
                created_by=456,
                description="Updated description"  # Updates existing record
            )
            assert attachment.id == updated.id  # Same record, not duplicate
            ```
        """
        pass

    @abstractmethod
    def get_attachment(self, attachment_id: int) -> Optional["FigmaAttachment"]:
        """
        Retrieve a single Figma attachment by ID, excluding soft-deleted records.

        Returns the attachment metadata if it exists and has not been soft-deleted
        (deleted_at IS NULL). Used for GET operations to display attachment details
        and verify attachment existence before updates or deletes.

        Soft Delete Filtering:
            Implementations must filter WHERE deleted_at IS NULL to exclude soft-deleted
            attachments. Historical attachments should be accessed via separate methods
            if audit access is required.

        :param attachment_id: Primary key ID of attachment to retrieve (required)
        :type attachment_id: int

        :return: FigmaAttachment entity if found and active, None if not found or deleted
        :rtype: Optional[FigmaAttachment]

        :raises DatabaseError: If database query fails

        Usage Example:
            ```python
            attachment = figma_repo.get_attachment(789)
            if attachment:
                print(f"Frame: {attachment.frame_title}")
                print(f"URL: {attachment.frame_url}")
            else:
                print("Attachment not found or deleted")
            ```
        """
        pass

    @abstractmethod
    def list_attachments(
        self,
        project_id: int,
        tech_spec_id: Optional[int] = None
    ) -> List["FigmaAttachment"]:
        """
        List Figma attachments for a project, optionally filtered by tech spec.

        Returns all active (not soft-deleted) frame attachments for the specified project.
        When tech_spec_id is provided, further filters to only attachments associated
        with that specific tech spec. This method is used for:
        - Displaying attached frames in project views
        - Showing frames related to specific tech specs
        - Validating frame references during project operations

        Soft Delete Filtering:
            Implementations must filter WHERE deleted_at IS NULL to show only active
            attachments. Deleted attachments should not appear unless accessed via
            separate historical query methods.

        Filtering Logic:
            - If tech_spec_id is None: Return all attachments for project_id
            - If tech_spec_id is provided: Return only attachments matching both
              project_id AND tech_spec_id
            - Always exclude soft-deleted records

        Performance Considerations:
            The project_id and tech_spec_id fields are indexed for efficient querying.
            Consider eager loading relationships (installation, project, creator) to
            avoid N+1 query problems when displaying attachment lists.

        :param project_id: ID of project to list attachments for (required)
        :type project_id: int
        :param tech_spec_id: Optional filter for attachments linked to specific tech spec
        :type tech_spec_id: Optional[int]

        :return: List of matching FigmaAttachment entities (empty list if none found)
        :rtype: List[FigmaAttachment]

        :raises DatabaseError: If database query fails

        Usage Example:
            ```python
            # List all frames attached to project
            all_frames = figma_repo.list_attachments(project_id=100)

            # List frames attached to specific tech spec
            spec_frames = figma_repo.list_attachments(
                project_id=100,
                tech_spec_id=200
            )

            for frame in all_frames:
                print(f"{frame.frame_title}: {frame.frame_url}")
            ```
        """
        pass

    @abstractmethod
    def soft_delete_attachment(self, attachment_id: int) -> bool:
        """
        Soft delete a Figma attachment by setting deleted_at timestamp.

        Marks the attachment as deleted without physically removing the database row.
        This preserves referential integrity and maintains audit history showing which
        frames were previously attached to projects. Soft-deleted attachments are
        excluded from normal queries via deleted_at IS NULL filtering.

        The method sets deleted_at to the current timestamp (typically CURRENT_TIMESTAMP
        in SQL or datetime.utcnow() in Python). The attachment record remains in the
        database but becomes invisible to standard queries.

        No File Cleanup:
            Since attachments store only URLs without downloading files, there are no
            files to clean up from GCS. The frame remains accessible via Figma if the
            URL is known and the PAT is still valid.

        Referential Integrity:
            Soft-deleting an attachment does not cascade to the installation or project.
        The attachment simply becomes invisible while maintaining foreign key relationships
            for audit purposes.

        :param attachment_id: Primary key ID of attachment to soft delete (required)
        :type attachment_id: int

        :return: True if soft delete succeeded, False if attachment not found
        :rtype: bool

        :raises DatabaseError: If database update fails

        Usage Example:
            ```python
            success = figma_repo.soft_delete_attachment(789)
            if success:
                print("Attachment soft-deleted successfully")
            else:
                print("Attachment not found")
            ```
        """
        pass
