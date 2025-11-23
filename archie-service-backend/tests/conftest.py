"""
Pytest fixtures for archie-service-backend testing.

This module provides shared fixtures for testing backend service route handlers,
including Flask test client setup, fake dependencies (AdminClient, ConfigRepository),
and test data for common scenarios.

Fixtures are organized by scope:
- Session fixtures: Created once per test session
- Function fixtures: Created fresh for each test function (default)
"""

import os
import pytest
from typing import Any, Dict, Generator
from unittest.mock import patch, MagicMock

from flask import Flask

from tests.fakes.fake_admin_client import FakeAdminClient
from tests.fakes.fake_config_repository import FakeConfigRepository


@pytest.fixture(scope='function')
def fake_admin_client() -> FakeAdminClient:
    """
    Provide a FakeAdminClient instance for testing.
    
    This fixture creates a fresh FakeAdminClient for each test function,
    ensuring tests don't interfere with each other through shared state.
    The fake client tracks all requests made and can be configured to
    return specific responses for testing various scenarios.
    
    :return: Fresh FakeAdminClient instance
    
    Example:
        def test_endpoint(fake_admin_client):
            fake_admin_client.set_success({'id': 1})
            # test code here
            assert fake_admin_client.request_count == 1
    """
    return FakeAdminClient()


@pytest.fixture(scope='function')
def fake_config_disabled() -> FakeConfigRepository:
    """
    Provide config repository with Figma integration DISABLED.
    
    Creates a FakeConfigRepository with FIGMA_INTEGRATION_ENABLED=false
    to test that all endpoints properly reject requests when the feature
    flag is disabled.
    
    :return: FakeConfigRepository with feature disabled
    """
    config = FakeConfigRepository.with_figma_disabled()
    return config


@pytest.fixture(scope='function')
def fake_config_enabled() -> FakeConfigRepository:
    """
    Provide config repository with Figma integration ENABLED.
    
    Creates a FakeConfigRepository with FIGMA_INTEGRATION_ENABLED=true
    to test normal request processing when the feature is enabled.
    
    :return: FakeConfigRepository with feature enabled
    """
    config = FakeConfigRepository.with_figma_enabled()
    return config


@pytest.fixture(scope='function')
def flask_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    """
    Provide Flask application configured for testing.
    
    Creates a Flask app with:
    - figma_bp blueprint registered
    - Testing mode enabled
    - Secret key set for session support
    
    :param monkeypatch: Pytest monkeypatch fixture for environment variables
    :return: Configured Flask application
    """
    # Create Flask app
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key-for-testing'
    
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
) -> Any:
    """
    Provide Flask test client with mocked dependencies and authenticated user.
    
    Creates a Flask test client and patches the AdminClient, feature flag,
    and authentication to use fake implementations. This fixture provides an
    AUTHENTICATED test client by default.
    
    For UNAUTHENTICATED tests, the test should NOT mock get_user_context and
    instead let it raise ValueError naturally. Tests that need unauthenticated
    behavior should use a different approach or not request this fixture with
    authentication enabled.
    
    The fixture automatically detects if fake_config_enabled or fake_config_disabled
    is also requested by the test and sets the feature flag accordingly.
    
    The fixture automatically patches:
    - AdminClient instantiation to return fake_admin_client
    - Environment variable FIGMA_INTEGRATION_ENABLED based on requested config
    - get_user_context to return authenticated user (can be skipped for unauth tests)
    - verify_project_access based on user fixture (with/without project access)
    
    :param flask_app: Configured Flask application
    :param fake_admin_client: Fake admin client for request tracking
    :param monkeypatch: Pytest monkeypatch for environment variables
    :param request: Pytest request object to detect requested fixtures
    :return: Flask test client
    
    Example:
        def test_endpoint(test_client, fake_config_disabled):
            response = test_client.post('/v1/figma/installations', json={...})
            assert response.status_code == 404  # feature disabled
    """
    # Detect which config fixture was requested (if any)
    # Default to disabled if neither is explicitly requested
    feature_enabled = False
    
    # Check if fake_config_enabled was requested
    if 'fake_config_enabled' in request.fixturenames:
        feature_enabled = True
    # Check if fake_config_disabled was requested  
    elif 'fake_config_disabled' in request.fixturenames:
        feature_enabled = False
    
    # Set environment variable for feature flag
    monkeypatch.setenv('FIGMA_INTEGRATION_ENABLED', str(feature_enabled).lower())
    
    # Determine if this test needs authenticated or unauthenticated behavior
    # Check if test function name contains "unauthenticated" or "authentication_required"
    test_function_name = request.node.name if hasattr(request.node, 'name') else ''
    needs_unauthenticated = ('unauthenticated' in test_function_name.lower() or 
                            'authentication_required' in test_function_name.lower())
    
    # Determine project access authorization behavior
    # Check if test uses authenticated_user_no_project_access fixture
    has_no_project_access = 'authenticated_user_no_project_access' in request.fixturenames
    has_project_access = 'authenticated_user_with_project_access' in request.fixturenames
    
    # Determine the verify_project_access return value
    # - If authenticated_user_no_project_access is used: return False
    # - If authenticated_user_with_project_access is used: return True
    # - Otherwise: return True (default allow for non-authorization tests)
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
def test_client_feature_enabled(
    flask_app: Flask,
    fake_admin_client: FakeAdminClient,
    fake_config_enabled: FakeConfigRepository,
    monkeypatch: pytest.MonkeyPatch
) -> Any:
    """
    Provide Flask test client with Figma integration ENABLED.
    
    Similar to test_client fixture but with FIGMA_INTEGRATION_ENABLED=true,
    allowing tests to verify behavior when the feature is enabled.
    
    :param flask_app: Configured Flask application
    :param fake_admin_client: Fake admin client for request tracking
    :param fake_config_enabled: Fake config with feature enabled
    :param monkeypatch: Pytest monkeypatch for environment variables
    :return: Flask test client with feature enabled
    """
    # Set environment variable for feature flag (enabled)
    feature_enabled = fake_config_enabled.get_bool('FIGMA_INTEGRATION_ENABLED', True)
    monkeypatch.setenv('FIGMA_INTEGRATION_ENABLED', str(feature_enabled).lower())
    
    # Patch AdminClient in the routes module
    with patch('src.routes.figma_routes.AdminClient', return_value=fake_admin_client):
        # Yield the test client for use in tests
        with flask_app.test_client() as client:
            yield client


@pytest.fixture(scope='function')
def authenticated_user() -> Dict[str, Any]:
    """
    Provide authenticated user context for testing.
    
    Returns a dictionary representing a valid authenticated user with
    standard permissions for testing authenticated endpoints.
    
    :return: User context dictionary
    """
    return {
        'user_id': 1,
        'username': 'testuser',
        'email': 'testuser@example.com',
        'role': 'USER',
        'auth_token': 'valid_token_12345'
    }


@pytest.fixture(scope='function')
def admin_user() -> Dict[str, Any]:
    """
    Provide admin user context for testing.
    
    Returns a dictionary representing an authenticated admin user for
    testing endpoints that require ADMIN or SUPER_ADMIN roles.
    
    :return: Admin user context dictionary
    """
    return {
        'user_id': 2,
        'username': 'adminuser',
        'email': 'admin@example.com',
        'role': 'ADMIN',
        'auth_token': 'admin_token_67890'
    }


@pytest.fixture(scope='function')
def regular_user() -> Dict[str, Any]:
    """
    Provide regular (non-admin) user context for testing.
    
    Returns a dictionary representing a regular authenticated user without
    admin privileges, for testing authorization checks.
    
    :return: Regular user context dictionary
    """
    return {
        'user_id': 3,
        'username': 'regularuser',
        'email': 'regular@example.com',
        'role': 'USER',
        'auth_token': 'user_token_abcde'
    }


@pytest.fixture(scope='function')
def valid_installation_data() -> Dict[str, Any]:
    """
    Provide valid Figma installation data for testing.
    
    Returns a dictionary with properly formatted data for creating
    a Figma installation, useful for testing POST endpoints.
    
    :return: Valid installation data
    """
    return {
        'name': 'Test Installation',
        'description': 'Test description for Figma integration',
        'pat': 'figd_test_token_12345abcdef'
    }


@pytest.fixture(scope='function')
def valid_frame_data() -> Dict[str, Any]:
    """
    Provide valid Figma frame attachment data for testing.
    
    Returns a dictionary with properly formatted data for attaching
    Figma frames to projects.
    
    :return: Valid frame attachment data
    """
    return {
        'project_id': 100,
        'installation_id': 1,
        'frames': [
            {
                'url': 'https://www.figma.com/file/ABC123/DesignFile?node-id=1:2',
                'description': 'Main dashboard frame'
            },
            {
                'url': 'https://www.figma.com/design/DEF456/AnotherFile?node-id=3:4',
                'description': 'User profile frame'
            }
        ]
    }


@pytest.fixture(scope='function')
def authenticated_user_with_project_access() -> Dict[str, Any]:
    """
    Provide authenticated user WITH project access for testing.
    
    Returns a dictionary representing an authenticated user who HAS access
    to project_id=100. Used for testing successful authorization flows.
    
    :return: User context dictionary with project access
    """
    return {
        'user_id': 10,
        'username': 'project_user',
        'email': 'projectuser@example.com',
        'role': 'USER',
        'token': 'project_access_token_xyz',
        'has_project_access': True
    }


@pytest.fixture(scope='function')
def authenticated_user_no_project_access() -> Dict[str, Any]:
    """
    Provide authenticated user WITHOUT project access for testing.
    
    Returns a dictionary representing an authenticated user who does NOT
    have access to project_id=100. Used for testing authorization failures.
    
    :return: User context dictionary without project access
    """
    return {
        'user_id': 20,
        'username': 'no_project_user',
        'email': 'noprojectuser@example.com',
        'role': 'USER',
        'token': 'no_project_token_abc',
        'has_project_access': False
    }


@pytest.fixture(scope='function')
def valid_auth_headers(authenticated_user: Dict[str, Any]) -> Dict[str, str]:
    """
    Provide valid authentication headers for testing.
    
    Returns HTTP headers including a Bearer token for authenticated requests.
    
    :param authenticated_user: Authenticated user fixture
    :return: Headers dictionary with Authorization header
    """
    return {
        'Authorization': f"Bearer {authenticated_user['auth_token']}",
        'Content-Type': 'application/json'
    }
