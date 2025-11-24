"""
Pytest configuration and shared test fixtures for Figma integration tests.

This module provides centralized fixture definitions for testing the Figma integration
feature across the archie-service-admin service. Fixtures include fake repository
implementations, pre-configured test data constants, and service instances with
injected dependencies.

The fixtures follow pytest best practices with appropriate scopes and ensure test
isolation by providing fresh instances or resetting state between tests. All fixtures
are designed to work together, enabling comprehensive unit testing of FigmaService
and route handlers without requiring external dependencies (database, Secret Manager,
Figma API, or configuration files).

Test Data Constants:
    - VALID_PAT: Example valid Figma Personal Access Token
    - VALID_FRAME_URL: Example Figma frame URL for testing
    - ADMIN_USER_ID: User ID representing an admin role
    - SUPER_ADMIN_USER_ID: User ID representing a super admin role
    - REGULAR_USER_ID: User ID representing a regular user without admin privileges
    - PROJECT_ID: Example project ID for attachment testing

Fixture Functions:
    - figma_repo: FakeFigmaRepository instance with clean state
    - secret_repo: FakeSecretRepository instance with clean state
    - figma_api_repo: FakeFigmaAPIRepository instance with clean state
    - config_repo: FakeConfigRepository instance with test defaults
    - figma_service: FigmaService instance with all fake repositories injected

Usage in Tests:
    Tests can use these fixtures by declaring them as function parameters:

    ```python
    def test_create_installation(figma_service, VALID_PAT):
        # Service is pre-configured with fake repositories
        installation = figma_service.create_installation(
            user_id=ADMIN_USER_ID,
            name="Test Installation",
            pat=VALID_PAT
        )
        assert installation['name'] == "Test Installation"
    ```

    Individual repository fixtures can be used for more granular testing:

    ```python
    def test_repository_directly(figma_repo):
        # Use fake repository without service layer
        installation = figma_repo.create_installation(
            user_id=1,
            name="Test",
            description="Testing"
        )
        assert installation.id == 1
    ```

State Management:
    All repository fixtures use function scope (default) to ensure each test receives
    a fresh instance with clean state. This prevents test pollution and ensures
    deterministic test execution regardless of test order.

Integration with Test Modules:
    This conftest.py file is automatically loaded by pytest for all test modules in
    the tests/ directory and subdirectories. Test modules in tests/unit/ can use
    these fixtures without explicit imports.
"""

import pytest
from typing import Any, Dict, List, Optional

# Import fake repository implementations for test fixtures
from tests.fakes.fake_figma_repository import FakeFigmaRepository
from tests.fakes.fake_secret_repository import FakeSecretRepository
from tests.fakes.fake_figma_api_repository import FakeFigmaAPIRepository
from tests.fakes.fake_config_repository import FakeConfigRepository

# Import service class for service-level test fixtures
from src.services.figma_service import FigmaService


# ============================================================================
# Test Data Constants
# ============================================================================
# These constants provide standardized test data for use across all test modules.
# Using constants ensures consistency and makes tests more readable by avoiding
# magic values scattered throughout test code.

# Valid Figma Personal Access Token format for testing
# This follows the actual Figma PAT format: figd_ prefix followed by alphanumeric string
VALID_PAT = "figd_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"

# Valid Figma frame URL for testing attachment functionality
# This represents a typical Figma file URL with node-id parameter for a specific frame
VALID_FRAME_URL = "https://www.figma.com/file/ABC123/DesignFile?node-id=1:2"

# Alternative valid Figma frame URL for testing multiple attachments
VALID_FRAME_URL_2 = "https://www.figma.com/design/DEF456/AnotherFile?node-id=3:4"

# User IDs representing different roles for authorization testing
# These IDs should be configured in fake repositories to return appropriate roles
ADMIN_USER_ID = 1
SUPER_ADMIN_USER_ID = 2
REGULAR_USER_ID = 3

# Project and tech spec IDs for attachment testing
# These IDs represent valid entities in the database for foreign key relationships
PROJECT_ID = 100
TECH_SPEC_ID = 200


# ============================================================================
# Repository Fixtures
# ============================================================================
# These fixtures provide fresh instances of fake repository implementations for
# each test function. Each fake maintains in-memory state and provides helper
# methods for test assertions and state manipulation.


@pytest.fixture
def figma_repo() -> FakeFigmaRepository:
    """
    Provide a fresh FakeFigmaRepository instance for testing.

    This fixture creates a new in-memory fake repository that simulates database
    operations for Figma installations, access control, and attachments. The fake
    maintains stateful storage across method calls within a test, enabling realistic
    testing of CRUD operations and business logic.

    The repository starts with empty state (no installations, no access records,
    no attachments) and auto-generates IDs starting from 1. Each test receives
    a completely independent instance, ensuring test isolation.

    Fixture Scope:
        Function (default) - A new instance is created for each test function.

    Returns:
        FakeFigmaRepository: Fresh fake repository instance with clean state.

    Usage Example:
        ```python
        def test_create_installation(figma_repo):
            installation = figma_repo.create_installation(
                user_id=1,
                name="Test Installation",
                description="Test description"
            )
            assert installation.id == 1
            assert installation.name == "Test Installation"

            # Verify state
            all_installs = figma_repo.list_installations()
            assert len(all_installs) == 1
        ```

    State Isolation:
        Each test function receives its own repository instance, preventing state
        leakage between tests. No explicit cleanup or reset is needed.
    """
    return FakeFigmaRepository()


@pytest.fixture
def secret_repo() -> FakeSecretRepository:
    """
    Provide a fresh FakeSecretRepository instance for testing.

    This fixture creates a new in-memory fake repository that simulates Google
    Cloud Secret Manager operations without requiring actual GCP credentials or
    network calls. The fake supports both success scenarios and controlled failure
    injection for testing error handling and transaction rollback behavior.

    The repository starts with no secrets stored and all error injection flags
    disabled (fail_on_create, fail_on_update, fail_on_delete all False). Tests
    can enable error injection flags to simulate Secret Manager failures.

    Fixture Scope:
        Function (default) - A new instance is created for each test function.

    Returns:
        FakeSecretRepository: Fresh fake repository instance with clean state.

    Usage Example:
        ```python
        def test_secret_storage(secret_repo):
            # Test successful secret creation
            secret_repo.create_secret('figma-secret-1', 'token123')
            retrieved = secret_repo.get_secret('figma-secret-1')
            assert retrieved == 'token123'

            # Test error injection for rollback testing
            secret_repo.fail_on_create = True
            with pytest.raises(SecretManagerError):
                secret_repo.create_secret('figma-secret-2', 'token456')
        ```

    Error Injection:
        Tests can enable failure modes by setting attributes:
        - secret_repo.fail_on_create = True
        - secret_repo.fail_on_update = True
        - secret_repo.fail_on_delete = True
        - secret_repo.fail_on_get = True

    State Tracking:
        The fake tracks operation counts for assertion purposes:
        ```python
        counts = secret_repo.get_operation_counts()
        assert counts['create_count'] == 1
        ```
    """
    return FakeSecretRepository()


@pytest.fixture
def figma_api_repo() -> FakeFigmaAPIRepository:
    """
    Provide a fresh FakeFigmaAPIRepository instance for testing.

    This fixture creates a new in-memory fake repository that simulates Figma API
    operations without making actual HTTP calls. The fake provides configurable
    responses for PAT validation and frame access validation, enabling comprehensive
    testing of API integration logic.

    The repository starts with default behavior where all PATs are considered valid
    and all frame URLs are accessible. Tests can customize this behavior using
    configuration helper methods to simulate specific scenarios (expired PATs,
    inaccessible frames, API errors).

    Fixture Scope:
        Function (default) - A new instance is created for each test function.

    Returns:
        FakeFigmaAPIRepository: Fresh fake repository instance with clean state.

    Usage Example:
        ```python
        def test_pat_validation(figma_api_repo):
            # Configure specific PAT validity
            figma_api_repo.set_pat_valid("figd_valid", valid=True)
            figma_api_repo.set_pat_valid("figd_expired", valid=False)

            # Test PAT validation
            assert figma_api_repo.validate_pat("figd_valid") is True
            assert figma_api_repo.validate_pat("figd_expired") is False

        def test_frame_validation(figma_api_repo):
            # Configure frame-specific response
            frame_url = "https://www.figma.com/file/ABC/design?node-id=1:2"
            figma_api_repo.set_frame_response(
                frame_url,
                valid=True,
                title="Login Screen",
                message=""
            )

            # Test frame validation
            result = figma_api_repo.validate_frame_access("figd_token", frame_url)
            assert result['valid'] is True
            assert result['title'] == "Login Screen"
        ```

    Configuration Methods:
        - set_pat_valid(pat, valid): Mark PAT as valid or invalid
        - set_frame_response(url, valid, title, message): Configure frame response
        - configure_default_behavior(all_valid): Set default for unlisted items
        - raise_on_validate_pat: Enable to simulate API errors
        - raise_on_validate_frame: Enable to simulate API errors

    Call Tracking:
        The fake tracks method invocations for assertion purposes:
        ```python
        counts = figma_api_repo.get_call_counts()
        assert counts['validate_pat'] == 2
        ```
    """
    return FakeFigmaAPIRepository()


@pytest.fixture
def config_repo() -> FakeConfigRepository:
    """
    Provide a fresh FakeConfigRepository instance for testing.

    This fixture creates a new in-memory fake repository that simulates application
    configuration access without requiring environment variables or configuration
    files. The fake initializes with sensible defaults for Figma integration testing
    and provides helper methods for customizing configuration values.

    Default Configuration Values:
        - FIGMA_INTEGRATION_ENABLED: True (feature enabled)
        - GCP_PROJECT_ID: 'test-project-id' (valid test project)
        - SECRET_MANAGER_RETRY_COUNT: 3 (standard retry count)
        - DEBUG_MODE: False (production-like testing)

    Fixture Scope:
        Function (default) - A new instance is created for each test function.

    Returns:
        FakeConfigRepository: Fresh fake repository instance with test defaults.

    Usage Example:
        ```python
        def test_feature_enabled(config_repo):
            # Test with default (feature enabled)
            assert config_repo.get_bool('FIGMA_INTEGRATION_ENABLED') is True

            # Test with feature disabled
            config_repo.set('FIGMA_INTEGRATION_ENABLED', False)
            assert config_repo.get_bool('FIGMA_INTEGRATION_ENABLED') is False

        def test_project_id(config_repo):
            # Verify project ID available
            project_id = config_repo.get_project_id()
            assert project_id == 'test-project-id'

            # Override for specific test
            config_repo.set('GCP_PROJECT_ID', 'custom-project')
            assert config_repo.get_project_id() == 'custom-project'
        ```

    Configuration Methods:
        - set(key, value): Set individual configuration value
        - update(dict): Set multiple configuration values at once
        - set_feature_flag(key, enabled): Set boolean feature flag
        - get(key, default): Get raw value
        - get_bool(key, default): Get boolean value with type conversion
        - get_int(key, default): Get integer value with type conversion
        - get_project_id(): Get GCP project ID for Secret Manager

    State Management:
        Each test receives a fresh instance with default values. Tests can modify
        configuration using set/update methods without affecting other tests.
    """
    return FakeConfigRepository()


# ============================================================================
# Service Fixtures
# ============================================================================
# These fixtures provide fully configured service instances with fake repositories
# injected, enabling end-to-end testing of business logic without external dependencies.


@pytest.fixture
def figma_service(
    figma_repo: FakeFigmaRepository,
    secret_repo: FakeSecretRepository,
    figma_api_repo: FakeFigmaAPIRepository,
    config_repo: FakeConfigRepository,
) -> FigmaService:
    """
    Provide a FigmaService instance with all fake repositories injected.

    This fixture creates a fully functional FigmaService instance for testing
    business logic without external dependencies. All repository dependencies
    (database, Secret Manager, Figma API, configuration) are satisfied with
    fake implementations that maintain in-memory state.

    The service is pre-configured with clean fake repositories, ready for testing
    any service method. Tests can interact with the service naturally and verify
    behavior through the service's return values or by inspecting fake repository
    state directly.

    Fixture Scope:
        Function (default) - A new service with fresh repositories for each test.

    Dependencies:
        This fixture depends on all repository fixtures (figma_repo, secret_repo,
        figma_api_repo, config_repo), which are automatically provided by pytest's
        dependency injection. Each test receives fresh repository instances.

    Returns:
        FigmaService: Service instance with fake repositories injected.

    Usage Example:
        ```python
        def test_create_installation(figma_service, VALID_PAT):
            # Service is ready to use with fake dependencies
            installation = figma_service.create_installation(
                user_id=ADMIN_USER_ID,
                name="Test Installation",
                pat=VALID_PAT,
                description="Integration test"
            )

            # Verify response
            assert installation['id'] == 1
            assert installation['name'] == "Test Installation"
            assert 'pat' not in installation  # PAT never exposed

            # Verify using injected repository if needed
            stored = figma_service.figma_repo.get_installation(1)
            assert stored is not None
        ```

    Advanced Testing:
        Tests can manipulate the injected repositories to simulate specific scenarios:

        ```python
        def test_create_with_secret_failure(figma_service):
            # Configure secret repository to fail
            figma_service.secret_repo.fail_on_create = True

            # Service should handle failure and rollback
            with pytest.raises(Exception):
                figma_service.create_installation(
                    user_id=1,
                    name="Test",
                    pat="token"
                )

            # Verify rollback - no installation created
            installs = figma_service.figma_repo.list_installations()
            assert len(installs) == 0
        ```

    Repository Access:
        The service exposes its repository instances as public attributes:
        - figma_service.figma_repo: FakeFigmaRepository
        - figma_service.secret_repo: FakeSecretRepository
        - figma_service.figma_api_repo: FakeFigmaAPIRepository
        - figma_service.config_repo: FakeConfigRepository

        Tests can access these directly for state inspection or configuration.
    """
    return FigmaService(
        figma_repo=figma_repo,
        secret_repo=secret_repo,
        figma_api_repo=figma_api_repo,
        config_repo=config_repo,
    )
