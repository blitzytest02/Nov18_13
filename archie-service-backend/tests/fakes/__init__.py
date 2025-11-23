"""
Fake implementations for Figma integration testing.

This package provides in-memory fake/mock implementations that simulate external
dependencies and service interactions, enabling comprehensive unit testing of
Figma integration features without requiring actual external systems.

Contents
--------
This package contains the following fake implementations:

- **FakeAdminClient**: Simulates HTTP communication with archie-service-admin,
  providing configurable response patterns for success, error, and timeout
  scenarios without requiring actual service-to-service connections.

- **FakeConfigRepository**: In-memory configuration repository enabling tests
  to control feature flags (particularly FIGMA_INTEGRATION_ENABLED) and other
  configuration values without external configuration files or environment
  variables.

Testing Philosophy
------------------
Following the testing strategy outlined in Section 0.6 of the Figma integration
technical specification, these fakes adhere to the repository pattern and
dependency injection architecture:

1. **State Maintenance**: Each fake maintains in-memory state that persists
   across method calls within a test, simulating real system behavior.

2. **Interface Compliance**: Fakes implement the same interfaces as production
   code, ensuring tests exercise the actual code paths used in production.

3. **Isolation**: Tests using these fakes have no external dependencies,
   enabling fast, reliable, and repeatable test execution.

4. **Reset Support**: All fakes provide reset mechanisms to ensure clean state
   between test methods.

5. **Configurability**: Fakes support configuring different scenarios (success,
   error, timeout) to test comprehensive error handling and edge cases.

Usage Examples
--------------
Basic usage in test files::

    from tests.fakes import FakeAdminClient, FakeConfigRepository

    def test_create_figma_installation():
        '''Test successful installation creation through backend service.'''
        # Setup fake dependencies
        fake_client = FakeAdminClient()
        fake_config = FakeConfigRepository.with_figma_enabled()
        
        # Configure successful response from admin service
        fake_client.set_success({
            'id': 1,
            'name': 'Test Installation',
            'status': 'active',
            'pat_status': 'Active',
            'created_at': '2024-01-01T00:00:00Z'
        })
        
        # Use in route handler or service
        response = fake_client.post('/v1/figma/installations', json={
            'name': 'Test Installation',
            'description': 'Test description',
            'pat': 'figd_test_token_12345'
        })
        
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Installation'
        
        # Verify request tracking
        assert fake_client.request_count == 1
        assert fake_client.last_request[0] == 'POST'

    def test_feature_flag_disabled():
        '''Test that endpoints reject requests when feature disabled.'''
        # Use factory method for specific configuration
        fake_config = FakeConfigRepository.with_figma_disabled()
        
        assert fake_config.get_bool('FIGMA_INTEGRATION_ENABLED') is False
        # Route handlers should check this flag and return appropriate error

    def test_admin_service_timeout():
        '''Test timeout handling when admin service is slow.'''
        fake_client = FakeAdminClient()
        fake_client.simulate_timeout()
        
        # Next request will raise TimeoutError
        try:
            response = fake_client.get('/v1/figma/installations/1')
            assert False, "Expected TimeoutError"
        except TimeoutError:
            pass  # Expected behavior

Using in test fixtures (conftest.py)::

    import pytest
    from tests.fakes import FakeAdminClient, FakeConfigRepository

    @pytest.fixture
    def fake_admin_client():
        '''Provide a fresh FakeAdminClient for each test.'''
        client = FakeAdminClient()
        yield client
        client.reset()  # Ensure clean state for next test

    @pytest.fixture
    def fake_config_enabled():
        '''Provide FakeConfigRepository with Figma enabled.'''
        return FakeConfigRepository.with_figma_enabled()

    @pytest.fixture
    def fake_config_disabled():
        '''Provide FakeConfigRepository with Figma disabled.'''
        return FakeConfigRepository.with_figma_disabled()

Architecture Integration
------------------------
These fakes integrate with the dependency injection pattern used throughout
the Figma integration implementation:

- Route handlers in archie-service-backend use FakeAdminClient instead of
  actual HTTP client for testing
- Services can accept fake repositories through constructor injection
- Tests control behavior by configuring fakes before exercising code under test
- Request tracking enables verification of service-to-service communication

For detailed information about specific fake implementations, see the
individual module documentation:

- :class:`tests.fakes.fake_admin_client.FakeAdminClient`
- :class:`tests.fakes.fake_config_repository.FakeConfigRepository`
"""

# Import fake implementations from submodules
from .fake_admin_client import FakeAdminClient
from .fake_config_repository import FakeConfigRepository

# Define explicit public API for package
# This enables clean imports: from tests.fakes import FakeAdminClient
__all__ = [
    'FakeAdminClient',
    'FakeConfigRepository',
]
