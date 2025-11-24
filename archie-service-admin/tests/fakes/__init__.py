"""
Test fake implementations for Figma integration repository interfaces.

This package provides in-memory fake implementations of all repository
interfaces used by the Figma integration feature. These fakes enable fast,
deterministic unit testing without requiring database connections, Google
Secret Manager access, or external API calls.

Architecture:
    The fakes follow the Test Double pattern as documented in
    archie-service-backend/docs/TEST.md, implementing repository interfaces
    defined in src/repositories/interfaces/. Each fake maintains internal
    state using Python dictionaries and lists, simulating the behavior of
    external systems without actual dependencies.

Purpose:
    - Enable isolated unit testing of FigmaService business logic
    - Test transaction consistency and rollback behavior
    - Simulate error conditions and edge cases
    - Verify correct usage of repository interfaces
    - Eliminate test flakiness from external service dependencies

Available Fakes:
    FakeFigmaRepository: Simulates database operations for Figma
        installations, access control records, and frame attachments.
        Supports soft deletes, unique constraints, and idempotent operations.

    FakeSecretRepository: Simulates Google Cloud Secret Manager operations
        for PAT storage and retrieval. Supports error injection for testing
        transaction rollback scenarios.

    FakeFigmaAPIRepository: Simulates Figma API calls for PAT validation and
        frame access checking. Allows pre-configuration of responses for
        deterministic testing.

    FakeConfigRepository: Simulates application configuration access.
        Enables testing of feature flag behavior and configuration-dependent
        logic without environment variables.

Usage Example:
    ```python
    from tests.fakes import (
        FakeFigmaRepository,
        FakeSecretRepository,
        FakeFigmaAPIRepository,
        FakeConfigRepository
    )

    def test_create_installation_success():
        # Initialize fakes
        figma_repo = FakeFigmaRepository()
        secret_repo = FakeSecretRepository()
        api_repo = FakeFigmaAPIRepository()
        config_repo = FakeConfigRepository()

        # Configure test scenario
        config_repo.set('FIGMA_INTEGRATION_ENABLED', True)
        api_repo.set_pat_valid('test_pat', valid=True)

        # Inject fakes into service
        service = FigmaService(
            figma_repo=figma_repo,
            secret_repo=secret_repo,
            figma_api_repo=api_repo,
            config_repo=config_repo
        )

        # Execute test
        result = service.create_installation(
            user_id=1,
            name='Test Installation',
            pat='test_pat'
        )

        # Verify using fake methods
        assert result['id'] == 1
        assert secret_repo.get_secret('figma-secret-1') == 'test_pat'

        # Reset state for next test
        figma_repo.reset()
        secret_repo.reset()
    ```

Testing Rollback Behavior:
    ```python
    def test_create_installation_rollback_on_secret_failure():
        figma_repo = FakeFigmaRepository()
        secret_repo = FakeSecretRepository()

        # Configure secret repo to fail
        secret_repo.fail_on_create = True

        service = FigmaService(
            figma_repo=figma_repo,
            secret_repo=secret_repo
        )

        # Attempt to create installation
        with pytest.raises(Exception):
            service.create_installation(
                user_id=1,
                name='Test',
                pat='token'
            )

        # Verify rollback - no installation should exist
        installations = figma_repo.get_all_installations()
        assert len(installations) == 0
    ```

State Management:
    All fakes maintain internal state across method calls within a test case.
    Each fake provides a reset() method to clear state between tests. For
    maximum isolation, create new fake instances for each test or use pytest
    fixtures with function scope.

Thread Safety:
    These fakes are NOT thread-safe and should only be used in
    single-threaded test environments. Each test should create its own fake
    instances or properly isolate state to avoid interference between
    parallel tests.

See Also:
    - Individual fake class docstrings for detailed API documentation
    - archie-service-backend/docs/TEST.md for testing patterns and guidelines
    - Section 0.6 and 0.7 of Agent Action Plan for testing strategy
"""

from .fake_figma_repository import FakeFigmaRepository
from .fake_secret_repository import FakeSecretRepository
from .fake_figma_api_repository import FakeFigmaAPIRepository
from .fake_config_repository import FakeConfigRepository

__all__ = [
    "FakeFigmaRepository",
    "FakeSecretRepository",
    "FakeFigmaAPIRepository",
    "FakeConfigRepository",
]
