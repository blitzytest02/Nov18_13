"""
Pytest configuration file providing shared test fixtures for Figma integration testing.

This module provides reusable fixtures for testing archie-service-backend Figma
route handlers following archie-service-backend/docs/TEST.md guidelines. Fixtures
enable consistent test setup across all unit tests by providing:

- Fake admin service clients with configurable response patterns
- Configuration repositories for feature flag testing
- Authenticated user contexts for authorization testing
- Test data factories for installations and attachments
- Flask test clients with proper dependency injection

All fixtures use function scope by default to ensure test isolation, with
comprehensive docstrings explaining purpose and usage patterns.
"""

from typing import Any, Callable, Dict, Generator, List, Optional
from unittest.mock import patch

import pytest
from flask import Flask

from tests.fakes.fake_admin_client import FakeAdminClient
from tests.fakes.fake_config_repository import FakeConfigRepository


# Constants for test data - exported for use in tests
valid_frame_url: str = "https://www.figma.com/file/ABC123/DesignFile?node-id=1:2"
valid_pat: str = "figd_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"


@pytest.fixture(scope='function')
def fake_admin_client() -> FakeAdminClient:
    """
    Provide a configured FakeAdminClient instance for testing route handlers.

    Creates a fresh FakeAdminClient for each test function with default response
    patterns configured for all Figma endpoints. The fake client tracks all
    requests made during the test and can be reconfigured on-the-fly to return
    specific responses for testing success, error, and timeout scenarios.

    The fake client maintains in-memory state across method calls within a test
    but is reset between tests to ensure isolation. Use set_response(),
    set_success(), or set_error() methods to configure specific responses.

    :return: Fresh FakeAdminClient instance with default endpoint responses

    Example Usage:

        .. code-block:: python

            def test_create_installation_success(fake_admin_client, test_client):
                # Configure successful response
                fake_admin_client.set_success({
                    'id': 1,
                    'name': 'Test Installation',
                    'status': 'active'
                })

                # Make request through test client
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test Installation',
                    'pat': 'figd_test_token'
                })

                # Verify request was forwarded to admin service
                assert fake_admin_client.request_count == 1
                assert fake_admin_client.last_request[0] == 'POST'
    """
    return FakeAdminClient()


@pytest.fixture(scope='function')
def admin_client_success(fake_admin_client: FakeAdminClient) -> FakeAdminClient:
    """
    Provide FakeAdminClient preconfigured for successful responses.

    Returns the fake admin client with a 200 OK response configured for the next
    request. Useful for tests that need to verify success path behavior without
    manually configuring responses.

    :param fake_admin_client: Base fake admin client fixture
    :return: FakeAdminClient configured for success response

    Example Usage:

        .. code-block:: python

            def test_successful_operation(admin_client_success, test_client):
                # Next request will receive 200 OK with default data
                response = test_client.get('/v1/figma/installations/1')
                assert response.status_code == 200
    """
    fake_admin_client.set_success({
        'id': 1,
        'name': 'Test Installation',
        'status': 'active',
        'pat_status': 'Active'
    })
    return fake_admin_client


@pytest.fixture(scope='function')
def admin_client_error(fake_admin_client: FakeAdminClient) -> FakeAdminClient:
    """
    Provide FakeAdminClient preconfigured for error scenarios.

    Returns the fake admin client with a 500 Internal Server Error response
    configured for the next request. Useful for testing error handling and
    proper error response propagation.

    :param fake_admin_client: Base fake admin client fixture
    :return: FakeAdminClient configured for error response

    Example Usage:

        .. code-block:: python

            def test_admin_service_error(admin_client_error, test_client):
                # Next request will receive 500 error
                response = test_client.get('/v1/figma/installations/1')
                assert response.status_code == 500
                assert 'error' in response.json
    """
    fake_admin_client.set_error(500, 'Internal server error in admin service')
    return fake_admin_client


@pytest.fixture(scope='function')
def admin_client_timeout(fake_admin_client: FakeAdminClient) -> FakeAdminClient:
    """
    Provide FakeAdminClient that simulates service unavailability.

    Returns the fake admin client configured to raise a TimeoutError on the next
    request, simulating network timeouts or admin service being unreachable.
    Useful for testing timeout handling and retry logic.

    :param fake_admin_client: Base fake admin client fixture
    :return: FakeAdminClient configured to simulate timeout

    Example Usage:

        .. code-block:: python

            def test_timeout_handling(admin_client_timeout, test_client):
                # Next request will raise TimeoutError
                response = test_client.get('/v1/figma/installations/1')
                # Verify proper timeout error response
                assert response.status_code in (504, 500)
    """
    fake_admin_client.simulate_timeout()
    return fake_admin_client


@pytest.fixture(scope='function')
def fake_config_enabled() -> FakeConfigRepository:
    """
    Provide configuration repository with FIGMA_INTEGRATION_ENABLED=true.

    Creates a FakeConfigRepository instance with Figma integration feature flag
    enabled, allowing tests to verify normal request processing when the feature
    is active. This is the default configuration for most feature tests.

    :return: FakeConfigRepository with Figma integration enabled

    Example Usage:

        .. code-block:: python

            def test_create_installation(fake_config_enabled, test_client):
                # Feature flag is enabled, request should process normally
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test',
                    'pat': 'figd_token'
                })
                assert response.status_code != 404  # Not feature disabled
    """
    return FakeConfigRepository.with_figma_enabled()


@pytest.fixture(scope='function')
def fake_config_disabled() -> FakeConfigRepository:
    """
    Provide configuration repository with FIGMA_INTEGRATION_ENABLED=false.

    Creates a FakeConfigRepository instance with Figma integration feature flag
    disabled, enabling tests to verify that all endpoints properly reject requests
    when the feature is not enabled. All Figma endpoints should return 404 when
    this configuration is active.

    :return: FakeConfigRepository with Figma integration disabled

    Example Usage:

        .. code-block:: python

            def test_feature_flag_enforcement(fake_config_disabled, test_client):
                # Feature flag is disabled, all endpoints should reject
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test',
                    'pat': 'figd_token'
                })
                assert response.status_code == 404
                assert response.json['error']['code'] == 'FEATURE_DISABLED'
    """
    return FakeConfigRepository.with_figma_disabled()


@pytest.fixture(scope='function')
def test_config() -> FakeConfigRepository:
    """
    Provide general test configuration with default values.

    Creates a FakeConfigRepository instance with standard test configuration
    including GCP project ID, admin service URL, and feature flag enabled.
    This is suitable for tests that don't specifically need to test feature
    flag behavior but need access to configuration values.

    Configuration includes:
    - FIGMA_INTEGRATION_ENABLED: True
    - GCP_PROJECT_ID: 'test-project-id'
    - ADMIN_SERVICE_URL: 'http://localhost:8000'

    :return: FakeConfigRepository with standard test configuration

    Example Usage:

        .. code-block:: python

            def test_configuration_access(test_config):
                project_id = test_config.get_project_id()
                assert project_id == 'test-project-id'

                service_url = test_config.get('ADMIN_SERVICE_URL')
                assert service_url == 'http://localhost:8000'
    """
    return FakeConfigRepository()


@pytest.fixture(scope='function')
def flask_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    """
    Provide Flask application configured for testing.

    Creates a Flask app instance with the figma_bp blueprint registered and
    testing mode enabled. This fixture provides the base application that
    test_client fixtures build upon with dependency injection.

    The application is configured with:
    - Testing mode enabled
    - Secret key for session support
    - figma_bp blueprint registered at /v1/figma prefix

    :param monkeypatch: Pytest monkeypatch fixture for environment manipulation
    :return: Configured Flask application instance

    Example Usage:

        .. code-block:: python

            def test_app_configuration(flask_app):
                assert flask_app.config['TESTING'] is True
                # Blueprint endpoints are available
                assert any(rule.rule.startswith('/v1/figma') for rule in flask_app.url_map.iter_rules())
    """
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key-for-testing-only'

    # Import and register the figma blueprint
    from src.routes.figma_routes import figma_bp
    app.register_blueprint(figma_bp)

    return app


@pytest.fixture(scope='function')
def test_client(
    flask_app: Flask,
    fake_admin_client: FakeAdminClient,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest
) -> Generator:
    """
    Provide Flask test client with mocked dependencies and authentication.

    Creates a Flask test client with AdminClient patched to use the fake client,
    feature flag configured based on requested config fixture, and authentication
    mocked to return authenticated user context by default.

    The fixture automatically detects which configuration fixture (fake_config_enabled
    or fake_config_disabled) is requested and sets the environment variable
    accordingly. It also provides authenticated user context by default, but can
    be configured for unauthenticated scenarios.

    Test function naming convention:
    - Include "unauthenticated" or "authentication_required" in test name to skip
      authentication mocking and test authentication enforcement

    Dependencies automatically patched:
    - AdminClient instantiation returns fake_admin_client
    - FIGMA_INTEGRATION_ENABLED environment variable set from config fixture
    - get_user_context returns authenticated user (unless test name indicates otherwise)
    - verify_project_access returns appropriate value based on user fixture

    :param flask_app: Configured Flask application
    :param fake_admin_client: Fake admin client for request tracking
    :param monkeypatch: Pytest monkeypatch for environment variables
    :param request: Pytest request object to detect requested fixtures
    :return: Flask test client with mocked dependencies

    Example Usage:

        .. code-block:: python

            def test_create_installation(test_client, fake_config_enabled):
                # Authenticated user with feature enabled
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test Installation',
                    'pat': 'figd_token_12345'
                })
                assert response.status_code == 201

            def test_feature_disabled(test_client, fake_config_disabled):
                # Feature flag disabled, request rejected
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test Installation',
                    'pat': 'figd_token_12345'
                })
                assert response.status_code == 404

            def test_authentication_required(test_client):
                # Test name contains "authentication_required", no auth mocked
                response = test_client.post('/v1/figma/installations', json={
                    'name': 'Test',
                    'pat': 'token'
                })
                # Should fail authentication
                assert response.status_code == 401
    """
    # Detect which config fixture was requested (if any)
    feature_enabled = True  # Default to enabled

    if 'fake_config_disabled' in request.fixturenames:
        feature_enabled = False
    elif 'fake_config_enabled' in request.fixturenames:
        feature_enabled = True

    # Set environment variable for feature flag
    monkeypatch.setenv('FIGMA_INTEGRATION_ENABLED', str(feature_enabled).lower())

    # Determine if this test needs unauthenticated behavior
    test_function_name = request.node.name if hasattr(request.node, 'name') else ''
    needs_unauthenticated = (
        'unauthenticated' in test_function_name.lower() or
        'authentication_required' in test_function_name.lower()
    )

    # Determine project access authorization behavior
    has_no_project_access = 'authenticated_user_no_project_access' in request.fixturenames
    has_project_access = 'authenticated_user_with_project_access' in request.fixturenames

    # Determine the verify_project_access return value
    if has_no_project_access:
        project_access_result = False
    elif has_project_access:
        project_access_result = True
    else:
        project_access_result = True  # Default to allowing access

    # Patch AdminClient in the routes module
    with patch('src.routes.figma_routes.AdminClient', return_value=fake_admin_client):
        # Patch verify_project_access to return appropriate value
        with patch('src.routes.figma_routes.verify_project_access', return_value=project_access_result):
            if needs_unauthenticated:
                # For authentication tests, don't mock get_user_context
                # Let it raise ValueError naturally for unauthenticated requests
                with flask_app.test_client() as client:
                    yield client
            else:
                # For other tests, mock get_user_context to return authenticated user
                mock_user_context = {
                    'user_id': 1,
                    'auth_token': 'valid_token_12345',
                    'request_id': 'test-request-id',
                    'ip_address': '127.0.0.1'
                }
                with patch('src.routes.figma_routes.get_user_context', return_value=mock_user_context):
                    with flask_app.test_client() as client:
                        yield client


@pytest.fixture(scope='function')
def app_context(flask_app: Flask) -> Generator:
    """
    Provide Flask application context for testing.

    Creates and pushes an application context for tests that need to access
    Flask's application-level features outside of a request context. This is
    useful for testing utility functions or service layer code.

    :param flask_app: Configured Flask application
    :return: Application context (automatically cleaned up after test)

    Example Usage:

        .. code-block:: python

            def test_config_access(app_context, flask_app):
                # Can access app config within the context
                assert flask_app.config['TESTING'] is True
    """
    with flask_app.app_context() as ctx:
        yield ctx


@pytest.fixture(scope='function')
def authenticated_user() -> Dict[str, Any]:
    """
    Provide mock authenticated user context for testing.

    Returns a dictionary representing a valid authenticated user with standard
    permissions. This user context can be used with mocked authentication to
    test authenticated endpoints and authorization logic.

    User attributes:
    - user_id: 1
    - role: USER (standard permissions)
    - Valid authentication token

    :return: User context dictionary

    Example Usage:

        .. code-block:: python

            def test_user_operation(authenticated_user):
                user_id = authenticated_user['user_id']
                # Simulate operation as this user
                assert user_id == 1
                assert authenticated_user['role'] == 'USER'
    """
    return {
        'user_id': 1,
        'username': 'testuser',
        'email': 'testuser@example.com',
        'role': 'USER',
        'auth_token': 'valid_token_12345',
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture(scope='function')
def unauthenticated_request() -> Dict[str, Any]:
    """
    Provide request context without authentication.

    Returns an empty dictionary representing an unauthenticated request context.
    Used for testing authentication enforcement and proper rejection of requests
    without valid authentication tokens.

    :return: Empty user context dictionary

    Example Usage:

        .. code-block:: python

            def test_authentication_required(unauthenticated_request):
                # Simulate request without authentication
                assert 'user_id' not in unauthenticated_request
                # Test should verify 401 Unauthorized response
    """
    return {}


@pytest.fixture(scope='function')
def admin_user() -> Dict[str, Any]:
    """
    Provide mock admin user context for testing.

    Returns a dictionary representing an authenticated user with ADMIN role,
    enabling tests to verify functionality that requires elevated permissions
    such as sharing installations or managing access controls.

    User attributes:
    - user_id: 2
    - role: ADMIN (elevated permissions)
    - Valid authentication token

    :return: Admin user context dictionary

    Example Usage:

        .. code-block:: python

            def test_share_installation_as_admin(admin_user):
                # Admin users can share installations
                assert admin_user['role'] == 'ADMIN'
                # Test sharing operation with admin context
    """
    return {
        'user_id': 2,
        'username': 'adminuser',
        'email': 'admin@example.com',
        'role': 'ADMIN',
        'auth_token': 'admin_token_67890',
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture(scope='function')
def regular_user() -> Dict[str, Any]:
    """
    Provide mock regular user context for testing.

    Returns a dictionary representing an authenticated user with standard USER
    role, explicitly not having admin privileges. Useful for testing authorization
    failures when non-admin users attempt privileged operations.

    User attributes:
    - user_id: 3
    - role: USER (no admin privileges)
    - Valid authentication token

    :return: Regular user context dictionary

    Example Usage:

        .. code-block:: python

            def test_share_denied_for_regular_user(regular_user):
                # Regular users cannot share installations
                assert regular_user['role'] == 'USER'
                # Test that sharing operation is rejected (403 Forbidden)
    """
    return {
        'user_id': 3,
        'username': 'regularuser',
        'email': 'regular@example.com',
        'role': 'USER',
        'auth_token': 'user_token_abcde',
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture(scope='function')
def authenticated_user_with_project_access() -> Dict[str, Any]:
    """
    Provide authenticated user WITH project access for authorization testing.

    Returns a dictionary representing an authenticated user who has access to
    project_id=100 (the default test project). Used for testing successful
    authorization flows for project-scoped operations like frame attachments.

    User attributes:
    - user_id: 10
    - role: USER
    - has_project_access: True (marker for test fixture)

    :return: User context dictionary with project access marker

    Example Usage:

        .. code-block:: python

            def test_attach_frames_authorized(test_client, authenticated_user_with_project_access):
                # This user has access to project_id=100
                response = test_client.post('/v1/figma/attachments', json={
                    'project_id': 100,
                    'installation_id': 1,
                    'frames': [{'url': 'https://figma.com/...', 'description': 'Frame'}]
                })
                # Should succeed authorization check
                assert response.status_code != 403
    """
    return {
        'user_id': 10,
        'username': 'project_user',
        'email': 'projectuser@example.com',
        'role': 'USER',
        'token': 'project_access_token_xyz',
        'has_project_access': True,
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture(scope='function')
def authenticated_user_no_project_access() -> Dict[str, Any]:
    """
    Provide authenticated user WITHOUT project access for authorization testing.

    Returns a dictionary representing an authenticated user who does NOT have
    access to project_id=100 (the default test project). Used for testing
    authorization failures for project-scoped operations.

    User attributes:
    - user_id: 20
    - role: USER
    - has_project_access: False (marker for test fixture)

    :return: User context dictionary without project access marker

    Example Usage:

        .. code-block:: python

            def test_attach_frames_unauthorized(test_client, authenticated_user_no_project_access):
                # This user does NOT have access to project_id=100
                response = test_client.post('/v1/figma/attachments', json={
                    'project_id': 100,
                    'installation_id': 1,
                    'frames': [{'url': 'https://figma.com/...', 'description': 'Frame'}]
                })
                # Should fail authorization check
                assert response.status_code == 403
    """
    return {
        'user_id': 20,
        'username': 'no_project_user',
        'email': 'noprojectuser@example.com',
        'role': 'USER',
        'token': 'no_project_token_abc',
        'has_project_access': False,
        'created_at': '2024-01-01T00:00:00Z'
    }


@pytest.fixture(scope='function')
def installation_data() -> Callable[[Optional[str], Optional[str], Optional[str]], Dict[str, Any]]:
    """
    Provide factory for creating Figma installation test data.

    Returns a callable factory function that generates properly formatted data
    for creating Figma installations. The factory accepts optional parameters
    to customize the installation data, making it flexible for various test
    scenarios while providing sensible defaults.

    Factory parameters:
    - name: Installation name (default: "Test Installation")
    - description: Installation description (default: "Test description for Figma integration")
    - pat: Personal Access Token (default: global valid_pat constant)

    :return: Factory function that generates installation data dictionaries

    Example Usage:

        .. code-block:: python

            def test_create_installation(installation_data, test_client):
                # Use default data
                data = installation_data()
                response = test_client.post('/v1/figma/installations', json=data)
                assert response.status_code == 201

            def test_create_custom_installation(installation_data, test_client):
                # Customize the data
                data = installation_data(name="Custom Installation", pat="figd_custom_token")
                response = test_client.post('/v1/figma/installations', json=data)
                assert response.status_code == 201
                assert response.json['name'] == "Custom Installation"
    """
    def factory(
        name: Optional[str] = None,
        description: Optional[str] = None,
        pat: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Figma installation test data.

        :param name: Installation name (optional)
        :param description: Installation description (optional)
        :param pat: Personal Access Token (optional)
        :return: Installation data dictionary
        """
        return {
            'name': name or 'Test Installation',
            'description': description or 'Test description for Figma integration',
            'pat': pat or valid_pat,
            'team_id': None  # Optional team association
        }

    return factory


@pytest.fixture(scope='function')
def attachment_data() -> Callable[[Optional[int], Optional[int], Optional[List[Dict[str, str]]]], Dict[str, Any]]:
    """
    Provide factory for creating Figma frame attachment test data.

    Returns a callable factory function that generates properly formatted data
    for attaching Figma frames to projects. The factory accepts optional
    parameters to customize the attachment data while providing realistic
    defaults for common testing scenarios.

    Factory parameters:
    - project_id: Project to attach frames to (default: 100)
    - installation_id: Figma installation ID (default: 1)
    - frames: List of frame dictionaries with url and description (default: 2 sample frames)
    - tech_spec_id: Optional tech spec association (default: None)

    Each frame dictionary should contain:
    - url: Figma frame URL
    - description: Frame description

    :return: Factory function that generates attachment data dictionaries

    Example Usage:

        .. code-block:: python

            def test_attach_frames(attachment_data, test_client, fake_config_enabled):
                # Use default data with 2 sample frames
                data = attachment_data()
                response = test_client.post('/v1/figma/attachments', json=data)
                assert response.status_code == 201

            def test_attach_custom_frames(attachment_data, test_client):
                # Customize the frames
                custom_frames = [
                    {
                        'url': 'https://www.figma.com/file/XYZ/MyFile?node-id=5:6',
                        'description': 'Custom frame description'
                    }
                ]
                data = attachment_data(project_id=200, frames=custom_frames)
                response = test_client.post('/v1/figma/attachments', json=data)
                assert response.status_code == 201
                assert len(response.json['attachments']) == 1
    """
    def factory(
        project_id: Optional[int] = None,
        installation_id: Optional[int] = None,
        frames: Optional[List[Dict[str, str]]] = None,
        tech_spec_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate Figma frame attachment test data.

        :param project_id: Project ID to attach frames to (optional)
        :param installation_id: Figma installation ID (optional)
        :param frames: List of frame dictionaries with url and description (optional)
        :param tech_spec_id: Optional tech spec ID for association (optional)
        :return: Attachment data dictionary
        """
        default_frames = [
            {
                'url': valid_frame_url,
                'description': 'Main dashboard design frame'
            },
            {
                'url': 'https://www.figma.com/design/DEF456/AnotherFile?node-id=3:4',
                'description': 'User profile page frame'
            }
        ]

        data: Dict[str, Any] = {
            'project_id': project_id or 100,
            'installation_id': installation_id or 1,
            'frames': frames or default_frames
        }

        # Only include tech_spec_id if explicitly provided
        if tech_spec_id is not None:
            data['tech_spec_id'] = tech_spec_id

        return data

    return factory
