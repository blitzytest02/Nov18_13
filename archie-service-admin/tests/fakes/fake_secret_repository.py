"""
In-memory fake implementation of ISecretRepository for unit testing.

This module provides a test double that simulates Google Cloud Secret Manager operations
without requiring actual GCP credentials, network calls, or a live Secret Manager instance.
The fake maintains stateful in-memory storage and supports controlled failure injection
for testing transaction rollback and error handling scenarios.

Purpose:
    - Enable fast, isolated unit tests without external dependencies
    - Simulate Secret Manager behavior including success and failure cases
    - Support testing of transactional consistency between database and Secret Manager
    - Provide visibility into operation counts and stored values for assertions

Testing Patterns:
    The fake supports multiple testing patterns through its configurable behavior:

    Pattern 1: Happy Path Testing
        fake_secret = FakeSecretRepository()
        fake_secret.create_secret('figma-secret-42', 'figd_token123')
        pat = fake_secret.get_secret('figma-secret-42')
        assert pat == 'figd_token123'

    Pattern 2: Error Injection Testing
        fake_secret = FakeSecretRepository()
        fake_secret.fail_on_create = True
        with pytest.raises(SecretManagerError):
            fake_secret.create_secret('figma-secret-42', 'figd_token123')

    Pattern 3: Transaction Rollback Testing
        fake_secret = FakeSecretRepository()
        fake_figma = FakeFigmaRepository()
        service = FigmaService(figma_repo=fake_figma, secret_repo=fake_secret)

        fake_secret.fail_on_create = True
        with pytest.raises(Exception):
            service.create_installation(user_id=1, name='Test', pat='token')

        # Verify no secret was stored due to rollback
        assert len(fake_secret.expose_secrets()) == 0

    Pattern 4: Operation Tracking
        fake_secret = FakeSecretRepository()
        fake_secret.create_secret('figma-secret-1', 'token1')
        fake_secret.update_secret('figma-secret-1', 'token2')

        counts = fake_secret.get_operation_counts()
        assert counts['create_count'] == 1
        assert counts['update_count'] == 1

State Management:
    The fake maintains state across method calls within a test, but should be reset
    between tests using the reset() method or by creating a new instance. Use pytest
    fixtures to ensure clean state:

    @pytest.fixture
    def secret_repo():
        fake = FakeSecretRepository()
        yield fake
        fake.reset()

Thread Safety:
    This fake is NOT thread-safe. It is designed for single-threaded unit tests only.
    Do not use in concurrent or integration testing scenarios.
"""

from typing import Dict, Optional
from src.repositories.interfaces.i_secret_repository import ISecretRepository


class SecretManagerError(Exception):
    """
    Exception raised to simulate Google Cloud Secret Manager failures.

    This exception is raised by FakeSecretRepository when error injection flags
    are enabled, allowing tests to verify proper error handling and transaction
    rollback behavior in the service layer.

    Usage:
        Catch this exception in tests to verify that failures are properly handled:

        fake_secret.fail_on_create = True
        with pytest.raises(SecretManagerError) as exc_info:
            service.create_installation(user_id=1, name='Test', pat='token')
        assert 'Failed to create secret' in str(exc_info.value)
    """
    pass


class FakeSecretRepository(ISecretRepository):
    """
    In-memory fake implementation of ISecretRepository for unit testing.

    This test double simulates Google Cloud Secret Manager operations without requiring
    actual GCP infrastructure. It maintains an in-memory dictionary of secrets and provides
    configurable failure injection for testing error scenarios.

    Attributes:
        _secrets (Dict[str, str]): In-memory storage mapping secret names to secret values
        _create_count (int): Counter tracking number of create_secret calls
        _update_count (int): Counter tracking number of update_secret calls
        _delete_count (int): Counter tracking number of delete_secret calls
        _get_count (int): Counter tracking number of get_secret calls
        fail_on_create (bool): When True, create_secret raises SecretManagerError
        fail_on_update (bool): When True, update_secret raises SecretManagerError
        fail_on_delete (bool): When True, delete_secret raises SecretManagerError
        fail_on_get (bool): When True, get_secret raises SecretManagerError

    Design Decisions:
        - Uses simple dict rather than mock Google SDK objects for clarity
        - Simulates retry_count parameter but doesn't actually retry (tests verify behavior)
        - Idempotent delete returns True even if secret doesn't exist (matches interface spec)
        - Operation counters enable verification of business logic flow
        - Failure flags support testing of rollback and error handling paths

    Example:
        # Basic usage in a service test
        def test_create_installation_success():
            fake_secret = FakeSecretRepository()
            fake_figma = FakeFigmaRepository()
            service = FigmaService(figma_repo=fake_figma, secret_repo=fake_secret)

            result = service.create_installation(
                user_id=1,
                name='My Installation',
                pat='figd_test_token_12345'
            )

            # Verify secret was stored with correct name
            secrets = fake_secret.expose_secrets()
            assert f'figma-secret-{result["id"]}' in secrets
            assert fake_secret.get_operation_counts()['create_count'] == 1

        # Error scenario testing
        def test_create_installation_rollback_on_secret_failure():
            fake_secret = FakeSecretRepository()
            fake_secret.fail_on_create = True
            fake_figma = FakeFigmaRepository()
            service = FigmaService(figma_repo=fake_figma, secret_repo=fake_secret)

            with pytest.raises(SecretManagerError):
                service.create_installation(
                    user_id=1,
                    name='My Installation',
                    pat='figd_test_token_12345'
                )

            # Verify no secrets stored due to transaction rollback
            assert len(fake_secret.expose_secrets()) == 0
            # Verify no installations created due to rollback
            assert len(fake_figma.list_installations()) == 0
    """

    def __init__(self):
        """
        Initialize the fake repository with empty state.

        Sets up in-memory storage and initializes all counters to zero.
        Failure flags are disabled by default, allowing happy path testing
        unless explicitly enabled.
        """
        # In-memory secret storage
        self._secrets: Dict[str, str] = {}

        # Operation counters for test assertions
        self._create_count: int = 0
        self._update_count: int = 0
        self._delete_count: int = 0
        self._get_count: int = 0

        # Error injection flags for testing failure scenarios
        self.fail_on_create: bool = False
        self.fail_on_update: bool = False
        self.fail_on_delete: bool = False
        self.fail_on_get: bool = False

    def create_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Simulate creating a new secret in Secret Manager.

        Stores the secret in the in-memory dictionary if the failure flag is not set.
        Increments the create counter for test verification. Validates secret name
        and value before storage.

        Error Simulation:
            When fail_on_create is True, raises SecretManagerError to simulate
            Secret Manager failure. This enables testing of transaction rollback
            behavior in the service layer.

        Idempotency:
            Unlike real Secret Manager (which rejects duplicate secret names),
            this fake allows overwriting for test simplicity. Tests can call
            reset() between test cases to ensure clean state.

        :param secret_name: Name of secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: The sensitive value to store (e.g., Figma PAT)
        :type secret_value: str
        :param retry_count: Simulated retry count (not actually used in fake)
        :type retry_count: int
        :return: True if secret created successfully
        :rtype: bool
        :raises SecretManagerError: When fail_on_create flag is True
        :raises ValueError: If secret_name or secret_value is empty
        """
        # Increment operation counter before validation for accurate tracking
        self._create_count += 1

        # Validate inputs
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")
        if not secret_value or not secret_value.strip():
            raise ValueError("secret_value cannot be empty")

        # Simulate failure scenario for testing
        if self.fail_on_create:
            raise SecretManagerError(
                f"Failed to create secret '{secret_name}' after {retry_count} retries"
            )

        # Store secret in memory
        self._secrets[secret_name] = secret_value
        return True

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve secret value from in-memory storage.

        Returns the secret value if it exists, or None if not found. Increments
        the get counter for test verification.

        Error Simulation:
            When fail_on_get is True, raises SecretManagerError to simulate
            Secret Manager access failures (e.g., permission denied, network error).

        Security Note:
            In tests, the returned value is visible and can be asserted against.
            Production code should never log or expose these values.

        :param secret_name: Name of secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :return: Secret value (string) or None if secret not found
        :rtype: Optional[str]
        :raises SecretManagerError: When fail_on_get flag is True
        :raises ValueError: If secret_name is empty
        """
        # Increment operation counter
        self._get_count += 1

        # Validate input
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")

        # Simulate failure scenario for testing
        if self.fail_on_get:
            raise SecretManagerError(
                f"Failed to retrieve secret '{secret_name}': Access denied"
            )

        # Return secret value or None if not found
        return self._secrets.get(secret_name)

    def update_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Simulate updating an existing secret by creating a new version.

        Validates that the secret exists before updating, matching the behavior
        of real Secret Manager. Updates the value in the in-memory dictionary
        to simulate creating a new version.

        Error Simulation:
            When fail_on_update is True, raises SecretManagerError to simulate
            Secret Manager update failures. Useful for testing PAT rotation
            rollback scenarios.

        Version Simulation:
            The fake doesn't maintain version history; it simply overwrites the
            value. This is sufficient for unit testing service layer logic without
            the complexity of version tracking.

        :param secret_name: Name of secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: New secret value to store as latest version
        :type secret_value: str
        :param retry_count: Simulated retry count (not actually used in fake)
        :type retry_count: int
        :return: True if secret updated successfully
        :rtype: bool
        :raises SecretManagerError: When fail_on_update is True or secret not found
        :raises ValueError: If secret_name or secret_value is empty
        """
        # Increment operation counter
        self._update_count += 1

        # Validate inputs
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")
        if not secret_value or not secret_value.strip():
            raise ValueError("secret_value cannot be empty")

        # Verify secret exists (matches real Secret Manager behavior)
        if secret_name not in self._secrets:
            raise SecretManagerError(
                f"Cannot update secret '{secret_name}': Secret does not exist"
            )

        # Simulate failure scenario for testing
        if self.fail_on_update:
            raise SecretManagerError(
                f"Failed to update secret '{secret_name}' after {retry_count} retries"
            )

        # Update secret value (simulates creating new version)
        self._secrets[secret_name] = secret_value
        return True

    def delete_secret(
        self,
        secret_name: str,
        retry_count: int = 3
    ) -> bool:
        """
        Simulate deleting a secret from Secret Manager.

        Removes the secret from in-memory storage. Implements idempotent deletion:
        returns True even if the secret doesn't exist, matching the interface
        specification for safe retry of deletion operations.

        Error Simulation:
            When fail_on_delete is True, raises SecretManagerError to simulate
            Secret Manager deletion failures. Critical for testing that installation
            soft-delete is rolled back when secret deletion fails.

        Consistency Testing:
            Use this in tests to verify transaction rollback:

            fake_secret.set_secret('figma-secret-42', 'token')
            fake_secret.fail_on_delete = True

            with pytest.raises(SecretManagerError):
                service.delete_installation(installation_id=42)

            # Verify installation NOT marked as deleted due to rollback
            installation = fake_figma.get_installation(42)
            assert installation['deleted_at'] is None

        :param secret_name: Name of secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param retry_count: Simulated retry count (not actually used in fake)
        :type retry_count: int
        :return: True if secret deleted successfully or does not exist
        :rtype: bool
        :raises SecretManagerError: When fail_on_delete flag is True
        :raises ValueError: If secret_name is empty
        """
        # Increment operation counter
        self._delete_count += 1

        # Validate input
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")

        # Simulate failure scenario for testing
        if self.fail_on_delete:
            raise SecretManagerError(
                f"Failed to delete secret '{secret_name}' after {retry_count} retries"
            )

        # Idempotent deletion: succeed even if secret doesn't exist
        if secret_name in self._secrets:
            del self._secrets[secret_name]

        return True

    def reset(self) -> None:
        """
        Reset all state to initial empty values.

        Clears all stored secrets and resets operation counters to zero.
        Resets failure flags to False. Use this method in test teardown
        or between test cases to ensure clean state.

        Usage Pattern:
            @pytest.fixture
            def secret_repo():
                fake = FakeSecretRepository()
                yield fake
                fake.reset()  # Clean up after test

        :return: None
        :rtype: None
        """
        self._secrets.clear()
        self._create_count = 0
        self._update_count = 0
        self._delete_count = 0
        self._get_count = 0
        self.fail_on_create = False
        self.fail_on_update = False
        self.fail_on_delete = False
        self.fail_on_get = False

    def expose_secrets(self) -> Dict[str, str]:
        """
        Return a copy of the internal secrets dictionary for test assertions.

        Provides visibility into stored secrets for verification in tests.
        Returns a copy to prevent tests from accidentally modifying internal state.

        Security Note:
            This method exists only for testing. Production implementations of
            ISecretRepository should NEVER provide bulk access to secrets.

        Usage:
            fake_secret.create_secret('figma-secret-42', 'figd_token123')
            secrets = fake_secret.expose_secrets()
            assert 'figma-secret-42' in secrets
            assert secrets['figma-secret-42'] == 'figd_token123'

        :return: Copy of secrets dictionary mapping secret names to values
        :rtype: Dict[str, str]
        """
        return self._secrets.copy()

    def set_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Directly set a secret value without incrementing counters.

        Use this method to pre-populate secrets for test setup scenarios where
        you want to test read operations or updates without counting the setup
        as an operation.

        Difference from create_secret:
            - Does not increment create_count
            - Does not check fail_on_create flag
            - Does not validate naming pattern (accepts any name)
            - Intended for test data setup only

        Usage:
            def test_update_existing_secret():
                fake_secret = FakeSecretRepository()
                # Setup: pre-populate without counting as create operation
                fake_secret.set_secret('figma-secret-42', 'old_token')

                # Test: verify update operation
                result = service.update_pat(installation_id=42, new_pat='new_token')

                assert fake_secret.get_secret('figma-secret-42') == 'new_token'
                assert fake_secret.get_operation_counts()['update_count'] == 1
                assert fake_secret.get_operation_counts()['create_count'] == 0

        :param secret_name: Name of secret (any string, no validation)
        :type secret_name: str
        :param secret_value: Secret value to store
        :type secret_value: str
        :return: None
        :rtype: None
        """
        self._secrets[secret_name] = secret_value

    def get_operation_counts(self) -> Dict[str, int]:
        """
        Return dictionary of operation counters for test assertions.

        Provides visibility into how many times each operation was called,
        enabling tests to verify that business logic follows expected flow.

        Returned Keys:
            - create_count: Number of create_secret calls
            - get_count: Number of get_secret calls
            - update_count: Number of update_secret calls
            - delete_count: Number of delete_secret calls

        Usage:
            def test_service_creates_secret_once():
                fake_secret = FakeSecretRepository()
                service = FigmaService(secret_repo=fake_secret)

                service.create_installation(user_id=1, name='Test', pat='token')

                counts = fake_secret.get_operation_counts()
                assert counts['create_count'] == 1
                assert counts['get_count'] == 0  # PAT not retrieved during create

        :return: Dictionary mapping operation names to call counts
        :rtype: Dict[str, int]
        """
        return {
            'create_count': self._create_count,
            'get_count': self._get_count,
            'update_count': self._update_count,
            'delete_count': self._delete_count
        }

    def clear(self) -> None:
        """
        Alias for reset() method for convenience.

        Some tests may prefer clear() terminology. Both methods do the same thing:
        reset all state to initial empty values.

        :return: None
        :rtype: None
        """
        self.reset()

    def validate_secret_name(self, secret_name: str) -> bool:
        """
        Validate that secret name follows required pattern 'figma-secret-<installation_id>'.

        Helps tests verify that service layer constructs secret names correctly.
        Returns True if name matches pattern, False otherwise.

        Pattern Requirements:
            - Must start with 'figma-secret-'
            - Must end with numeric installation ID
            - Examples: 'figma-secret-1', 'figma-secret-42', 'figma-secret-1000'

        Usage:
            def test_service_uses_correct_secret_naming():
                fake_secret = FakeSecretRepository()
                service = FigmaService(secret_repo=fake_secret)

                result = service.create_installation(
                    user_id=1,
                    name='Test',
                    pat='token'
                )

                # Verify service constructed name correctly
                secrets = fake_secret.expose_secrets()
                for secret_name in secrets.keys():
                    assert fake_secret.validate_secret_name(secret_name)

        :param secret_name: Secret name to validate
        :type secret_name: str
        :return: True if name matches pattern, False otherwise
        :rtype: bool
        """
        if not secret_name:
            return False

        # Check prefix
        if not secret_name.startswith('figma-secret-'):
            return False

        # Extract suffix after prefix
        suffix = secret_name[len('figma-secret-'):]

        # Verify suffix is numeric (installation ID)
        if not suffix:
            return False

        try:
            int(suffix)
            return True
        except ValueError:
            return False
