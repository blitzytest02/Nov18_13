"""
In-memory fake implementation of IFigmaRepository for unit testing.

This module provides a test fake that simulates database operations for Figma
integrations without requiring an actual database connection. The fake maintains
stateful in-memory storage using Python dictionaries, enabling comprehensive testing
of FigmaService business logic in complete isolation.

The fake implements the complete IFigmaRepository interface contract with realistic
behavior including:
- Auto-incrementing primary key IDs
- Soft delete filtering (deleted_at timestamps)
- Unique constraint enforcement
- Idempotent attachment creation (last write wins)
- Automatic timestamp management (created_at, updated_at)

Usage in Tests:
    ```python
    def test_create_installation():
        # Create fake repository instance
        fake_repo = FakeFigmaRepository()

        # Use in service with dependency injection
        service = FigmaService(figma_repo=fake_repo)

        # Test business logic
        installation = service.create_installation(
            user_id=1,
            name="Test Installation",
            pat="test_pat_value"
        )

        # Verify using fake's helper methods
        all_installs = fake_repo.get_all_installations()
        assert len(all_installs) == 1

        # Reset state between tests
        fake_repo.reset()
    ```

State Isolation:
    Each FakeFigmaRepository instance maintains independent state. Create a new
    instance for each test or call reset() to clear state between test cases.
    The reset() method reinitializes all internal dictionaries and ID counters.

Entity Representation:
    The fake uses dictionaries to represent database entities (FigmaInstallation,
    FigmaInstallationAccess, FigmaAttachment) since actual model classes may not
    be available in the test environment. Dictionary keys match model field names
    for compatibility with service layer expectations.

Deep Copying:
    All returned entities are deep copied to prevent test code from inadvertently
    modifying internal fake state. This ensures proper isolation between repository
    operations and test assertions.

Transaction Simulation:
    While this fake doesn't implement explicit transaction boundaries (BEGIN/COMMIT/
    ROLLBACK), tests can verify transactional behavior by checking state before and
    after service operations that should be atomic. For transaction testing with
    Secret Manager rollback scenarios, inject this fake alongside FakeSecretRepository.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from copy import deepcopy

from src.repositories.interfaces.i_figma_repository import IFigmaRepository


class FakeFigmaRepository(IFigmaRepository):
    """
    In-memory fake repository for testing Figma integration database operations.

    Simulates complete CRUD operations for installations, access control, and
    attachments without requiring actual database infrastructure. Maintains stateful
    storage across method calls within a test while supporting easy state reset
    between tests.

    Internal Storage Structure:
        - _installations: Dict[int, Dict] - Installation records keyed by ID
        - _access_records: Dict[int, Dict] - Access grant records keyed by ID
        - _attachments: Dict[int, Dict] - Attachment records keyed by ID
        - _next_installation_id: int - Auto-increment counter for installations
        - _next_access_id: int - Auto-increment counter for access records
        - _next_attachment_id: int - Auto-increment counter for attachments

    Soft Delete Implementation:
        All query methods filter WHERE deleted_at IS NULL by checking if the
        deleted_at field is None. Soft delete operations set deleted_at to
        datetime.utcnow() without removing records from internal storage.

    Constraint Enforcement:
        - Unique constraint on (installation_id, user_id) for active access grants
        - Unique constraint on (project_id, frame_url) for active attachments
        - Idempotent attachment creation updates existing instead of raising errors
    """

    def __init__(self):
        """
        Initialize fake repository with empty in-memory storage.

        Creates empty dictionaries for all entity types and initializes
        auto-increment counters to 1. Each instance maintains independent
        state, so create new instances or call reset() for test isolation.
        """
        self._installations: Dict[int, Dict[str, Any]] = {}
        self._access_records: Dict[int, Dict[str, Any]] = {}
        self._attachments: Dict[int, Dict[str, Any]] = {}

        self._next_installation_id = 1
        self._next_access_id = 1
        self._next_attachment_id = 1

    # ============================================================================
    # Figma Installation Operations
    # ============================================================================

    def create_installation(  # type: ignore[override]
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        team_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a new Figma installation record in memory.

        Simulates database INSERT by adding a new installation dictionary to
        internal storage with auto-generated ID and timestamps. The status
        defaults to 'active' per database schema specification.

        :param user_id: Owner user ID (required)
        :param name: Installation display name (required)
        :param description: Optional description text
        :param team_id: Optional team association
        :return: Created installation dict with all fields including generated ID
        """
        installation_id = self._next_installation_id
        self._next_installation_id += 1

        now = datetime.utcnow()
        installation = {
            "id": installation_id,
            "user_id": user_id,
            "team_id": team_id,
            "name": name,
            "description": description,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }

        self._installations[installation_id] = installation
        return deepcopy(installation)

    def get_installation(self, installation_id: int) -> Optional[Dict[str, Any]]:  # type: ignore[override]
        """
        Retrieve installation by ID, excluding soft-deleted records.

        Simulates database SELECT with WHERE id = ? AND deleted_at IS NULL.
        Returns None if installation doesn't exist or has been soft-deleted.

        :param installation_id: Primary key ID to retrieve
        :return: Installation dict if found and active, None otherwise
        """
        installation = self._installations.get(installation_id)

        if installation is None or installation["deleted_at"] is not None:
            return None

        return deepcopy(installation)

    def update_installation(  # type: ignore[override]
        self, installation_id: int, **kwargs
    ) -> Dict[str, Any]:
        """
        Update fields on existing installation.

        Simulates database UPDATE by modifying specified fields in the stored
        installation dictionary. Automatically refreshes updated_at timestamp.
        Raises ValueError if installation doesn't exist or is soft-deleted.

        Supported update fields: name, description, status, team_id

        :param installation_id: ID of installation to update
        :param kwargs: Field names and new values
        :return: Updated installation dict
        :raises ValueError: If installation not found or soft-deleted
        """
        installation = self._installations.get(installation_id)

        if installation is None or installation["deleted_at"] is not None:
            raise ValueError(
                f"Installation {installation_id} not found or deleted"
            )

        # Update provided fields
        for key, value in kwargs.items():
            if key in installation and key not in [
                "id",
                "created_at",
                "deleted_at",
            ]:
                installation[key] = value

        # Always refresh updated_at timestamp
        installation["updated_at"] = datetime.utcnow()

        return deepcopy(installation)

    def soft_delete_installation(self, installation_id: int) -> bool:
        """
        Soft delete installation by setting deleted_at timestamp.

        Simulates database UPDATE SET deleted_at = NOW() WHERE id = ?.
        Does not physically remove the record from storage, preserving it
        for audit history. Soft-deleted installations are excluded from
        query results that filter on deleted_at IS NULL.

        :param installation_id: ID of installation to soft delete
        :return: True if deleted, False if not found or already deleted
        """
        installation = self._installations.get(installation_id)

        if installation is None or installation["deleted_at"] is not None:
            return False

        installation["deleted_at"] = datetime.utcnow()
        return True

    def list_installations(  # type: ignore[override]
        self, user_id: Optional[int] = None, team_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List installations with optional filtering by user or team.

        Simulates database SELECT with WHERE deleted_at IS NULL and optional
        additional filters. Uses OR logic when both user_id and team_id are
        provided: (user_id = ? OR team_id = ?).

        :param user_id: Optional filter for installations owned by user
        :param team_id: Optional filter for installations in team
        :return: List of matching installation dicts (empty if none found)
        """
        results = []

        for installation in self._installations.values():
            # Skip soft-deleted installations
            if installation["deleted_at"] is not None:
                continue

            # Apply filters
            if user_id is not None and team_id is not None:
                # OR logic: match either user_id or team_id
                if (
                    installation["user_id"] == user_id
                    or installation["team_id"] == team_id
                ):
                    results.append(deepcopy(installation))
            elif user_id is not None:
                if installation["user_id"] == user_id:
                    results.append(deepcopy(installation))
            elif team_id is not None:
                if installation["team_id"] == team_id:
                    results.append(deepcopy(installation))
            else:
                # No filters - return all active installations
                results.append(deepcopy(installation))

        return results

    # ============================================================================
    # Figma Installation Access Control Operations
    # ============================================================================

    def grant_access(  # type: ignore[override]
        self,
        installation_id: int,
        user_id: int,
        granted_by: int,
        access_level: str = "viewer",
    ) -> Dict[str, Any]:
        """
        Grant user access to installation with specified access level.

        Simulates database INSERT for access control records. Enforces unique
        constraint: only one active access grant per (installation_id, user_id)
        combination. Raises ValueError if duplicate active grant exists.

        :param installation_id: Installation to grant access to
        :param user_id: User receiving access
        :param granted_by: Admin user granting access
        :param access_level: Permission level (viewer/editor/admin)
        :return: Created access record dict
        :raises ValueError: If duplicate active access grant exists
        """
        # Check for existing active access grant (unique constraint)
        for access in self._access_records.values():
            if (
                access["figma_installation_id"] == installation_id
                and access["user_id"] == user_id
                and access["deleted_at"] is None
            ):
                raise ValueError(
                    f"Active access already exists for user {user_id} "
                    f"on installation {installation_id}"
                )

        access_id = self._next_access_id
        self._next_access_id += 1

        now = datetime.utcnow()
        access_record = {
            "id": access_id,
            "figma_installation_id": installation_id,
            "user_id": user_id,
            "access_level": access_level,
            "granted_by": granted_by,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }

        self._access_records[access_id] = access_record
        return deepcopy(access_record)

    def revoke_access(self, installation_id: int, user_id: int) -> bool:
        """
        Revoke user access by soft deleting access record.

        Simulates database UPDATE SET deleted_at = NOW() WHERE
        installation_id = ? AND user_id = ? AND deleted_at IS NULL.
        If multiple active records exist (edge case), soft-deletes all of them.

        :param installation_id: Installation to revoke access from
        :param user_id: User whose access is being revoked
        :return: True if access revoked, False if no active access found
        """
        revoked = False
        now = datetime.utcnow()

        for access in self._access_records.values():
            if (
                access["figma_installation_id"] == installation_id
                and access["user_id"] == user_id
                and access["deleted_at"] is None
            ):
                access["deleted_at"] = now
                revoked = True

        return revoked

    def list_access(self, installation_id: int) -> List[Dict[str, Any]]:  # type: ignore[override]
        """
        List all active access grants for installation.

        Simulates database SELECT WHERE installation_id = ? AND deleted_at IS NULL.
        Returns all users with active access to the specified installation.

        :param installation_id: Installation to list access for
        :return: List of active access record dicts (empty if none)
        """
        results = []

        for access in self._access_records.values():
            if (
                access["figma_installation_id"] == installation_id
                and access["deleted_at"] is None
            ):
                results.append(deepcopy(access))

        return results

    # ============================================================================
    # Figma Attachment Operations
    # ============================================================================

    def create_attachment(  # type: ignore[override]
        self,
        project_id: int,
        installation_id: int,
        frame_url: str,
        created_by: int,
        frame_title: Optional[str] = None,
        description: Optional[str] = None,
        tech_spec_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create or update frame attachment with idempotent behavior.

        Simulates database INSERT with ON CONFLICT UPDATE behavior. The unique
        constraint (project_id, frame_url, deleted_at) ensures only one active
        attachment per frame URL per project. If attachment already exists,
        updates the existing record ("last write wins"). If not exists, creates
        new attachment.

        This idempotent approach supports additive workflows where the same
        frame can be attached multiple times without errors.

        :param project_id: Project to attach frame to
        :param installation_id: Installation providing PAT for access
        :param frame_url: Figma frame URL (unique per project)
        :param created_by: User creating the attachment
        :param frame_title: Frame title from Figma API
        :param description: User-provided description
        :param tech_spec_id: Optional tech spec association
        :return: Created or updated attachment dict
        """
        # Check for existing active attachment (idempotent behavior)
        existing_attachment = None
        for attachment in self._attachments.values():
            if (
                attachment["project_id"] == project_id
                and attachment["frame_url"] == frame_url
                and attachment["deleted_at"] is None
            ):
                existing_attachment = attachment
                break

        if existing_attachment is not None:
            # Update existing attachment (last write wins)
            existing_attachment["installation_id"] = installation_id
            existing_attachment["frame_title"] = frame_title
            existing_attachment["description"] = description
            existing_attachment["tech_spec_id"] = tech_spec_id
            # Note: created_by is NOT updated - preserves original creator
            existing_attachment["updated_at"] = datetime.utcnow()
            return deepcopy(existing_attachment)
        else:
            # Create new attachment
            attachment_id = self._next_attachment_id
            self._next_attachment_id += 1

            now = datetime.utcnow()
            attachment = {
                "id": attachment_id,
                "project_id": project_id,
                "tech_spec_id": tech_spec_id,
                "figma_installation_id": installation_id,
                "frame_url": frame_url,
                "frame_title": frame_title,
                "description": description,
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }

            self._attachments[attachment_id] = attachment
            return deepcopy(attachment)

    def get_attachment(self, attachment_id: int) -> Optional[Dict[str, Any]]:  # type: ignore[override]
        """
        Retrieve attachment by ID, excluding soft-deleted records.

        Simulates database SELECT WHERE id = ? AND deleted_at IS NULL.
        Returns None if attachment doesn't exist or has been soft-deleted.

        :param attachment_id: Primary key ID to retrieve
        :return: Attachment dict if found and active, None otherwise
        """
        attachment = self._attachments.get(attachment_id)

        if attachment is None or attachment["deleted_at"] is not None:
            return None

        return deepcopy(attachment)

    def list_attachments(  # type: ignore[override]
        self, project_id: int, tech_spec_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List attachments for project, optionally filtered by tech spec.

        Simulates database SELECT WHERE project_id = ? AND deleted_at IS NULL
        with optional AND tech_spec_id = ? filter. Returns all active frame
        attachments matching the criteria.

        :param project_id: Project to list attachments for (required)
        :param tech_spec_id: Optional filter for specific tech spec
        :return: List of matching attachment dicts (empty if none)
        """
        results = []

        for attachment in self._attachments.values():
            # Skip soft-deleted attachments
            if attachment["deleted_at"] is not None:
                continue

            # Must match project_id
            if attachment["project_id"] != project_id:
                continue

            # If tech_spec_id filter provided, must match
            if (
                tech_spec_id is not None
                and attachment["tech_spec_id"] != tech_spec_id
            ):
                continue

            results.append(deepcopy(attachment))

        return results

    def soft_delete_attachment(self, attachment_id: int) -> bool:
        """
        Soft delete attachment by setting deleted_at timestamp.

        Simulates database UPDATE SET deleted_at = NOW() WHERE id = ?.
        Does not physically remove the record, preserving audit history.
        Soft-deleted attachments are excluded from query results.

        :param attachment_id: ID of attachment to soft delete
        :return: True if deleted, False if not found or already deleted
        """
        attachment = self._attachments.get(attachment_id)

        if attachment is None or attachment["deleted_at"] is not None:
            return False

        attachment["deleted_at"] = datetime.utcnow()
        return True

    # ============================================================================
    # Test Helper Methods
    # ============================================================================

    def reset(self) -> None:
        """
        Reset all internal state to empty.

        Clears all stored installations, access records, and attachments, then
        resets auto-increment counters to 1. Use this method to isolate tests
        and prevent state leakage between test cases.

        Usage in test fixtures:
            ```python
            @pytest.fixture
            def fake_figma_repo():
                repo = FakeFigmaRepository()
                yield repo
                repo.reset()  # Clean up after test
            ```
        """
        self._installations.clear()
        self._access_records.clear()
        self._attachments.clear()

        self._next_installation_id = 1
        self._next_access_id = 1
        self._next_attachment_id = 1

    def get_all_installations(
        self, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all installations including soft-deleted ones for test debugging.

        Unlike list_installations, this method returns ALL installations in
        storage regardless of deleted_at status. Useful for verifying soft
        delete behavior and inspecting complete state in test assertions.

        :param include_deleted: If False, filters out soft-deleted records
        :return: List of all installation dicts
        """
        if include_deleted:
            return [deepcopy(inst) for inst in self._installations.values()]
        else:
            return [
                deepcopy(inst)
                for inst in self._installations.values()
                if inst["deleted_at"] is None
            ]

    def get_all_access_records(
        self, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all access records including soft-deleted ones for test debugging.

        Returns ALL access records regardless of deleted_at status, useful for
        verifying access grant/revoke operations and soft delete behavior.

        :param include_deleted: If False, filters out soft-deleted records
        :return: List of all access record dicts
        """
        if include_deleted:
            return [deepcopy(acc) for acc in self._access_records.values()]
        else:
            return [
                deepcopy(acc)
                for acc in self._access_records.values()
                if acc["deleted_at"] is None
            ]

    def get_all_attachments(
        self, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all attachments including soft-deleted ones for test debugging.

        Returns ALL attachments regardless of deleted_at status, useful for
        verifying attachment creation and soft delete behavior.

        :param include_deleted: If False, filters out soft-deleted records
        :return: List of all attachment dicts
        """
        if include_deleted:
            return [deepcopy(att) for att in self._attachments.values()]
        else:
            return [
                deepcopy(att)
                for att in self._attachments.values()
                if att["deleted_at"] is None
            ]
