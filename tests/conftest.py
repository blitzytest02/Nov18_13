"""
Shared pytest fixtures and configuration for Flask application testing.

This module provides:
- Flask application factory fixture
- Test client fixture for route testing
- Mock fixtures for external services (GCS, Pub/Sub)
- Common test utilities and helpers

Usage:
    Fixtures are automatically available to all test files.
    Import from tests.fixtures for additional test data factories.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src to path for imports (when src/app exists)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def app():
    """
    Create Flask application for testing.
    
    The application is configured with TESTING=True for test isolation.
    This fixture will be updated when the Flask app is created.
    """
    # Placeholder - will be updated when Flask app is created
    # from src.app import create_app
    # app = create_app({"TESTING": True})
    # yield app
    yield None


@pytest.fixture
def client(app):
    """
    Flask test client fixture.
    
    Provides a test client for making HTTP requests without running a server.
    """
    if app is None:
        pytest.skip("Flask app not yet created")
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    Flask CLI test runner fixture.
    
    Provides a CLI runner for testing Flask CLI commands.
    """
    if app is None:
        pytest.skip("Flask app not yet created")
    return app.test_cli_runner()


@pytest.fixture
def mock_storage_client(mocker):
    """
    Mock Google Cloud Storage client fixture.
    
    Provides a mocked GCS client for testing storage operations
    without making actual cloud API calls.
    """
    mock_client = mocker.patch("google.cloud.storage.Client")
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    
    mock_client.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.upload_from_string.return_value = None
    mock_blob.download_as_string.return_value = b"test content"
    
    return mock_client


@pytest.fixture
def mock_pubsub_publisher(mocker):
    """
    Mock Google Cloud Pub/Sub publisher client fixture.
    
    Provides a mocked Pub/Sub publisher for testing message publishing
    without making actual cloud API calls.
    """
    mock_publisher = mocker.patch("google.cloud.pubsub_v1.PublisherClient")
    mock_future = MagicMock()
    mock_future.result.return_value = "test-message-id"
    mock_publisher.return_value.publish.return_value = mock_future
    
    return mock_publisher


@pytest.fixture
def mock_pubsub_subscriber(mocker):
    """
    Mock Google Cloud Pub/Sub subscriber client fixture.
    
    Provides a mocked Pub/Sub subscriber for testing message consumption
    without making actual cloud API calls.
    """
    mock_subscriber = mocker.patch("google.cloud.pubsub_v1.SubscriberClient")
    return mock_subscriber


@pytest.fixture
def sample_document_data():
    """
    Sample document data for testing.
    
    Returns a dictionary with typical document section data.
    """
    return {
        "heading": "Test Section",
        "content": "Test content for the section",
        "status": "UNCHANGED",
        "changes": []
    }


@pytest.fixture
def sample_state_data():
    """
    Sample state data for testing.
    
    Returns a dictionary with typical reverse document state data.
    """
    return {
        "tech_spec": "Sample tech spec content",
        "document_sections": [],
        "current_section_index": 0,
        "completed": False
    }
