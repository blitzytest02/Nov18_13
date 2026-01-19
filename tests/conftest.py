"""
Shared pytest fixtures and configuration for Flask application testing.

This module provides:
- Flask application factory fixture
- Test client fixture for route testing
- Mock fixtures for external services (GCS, Pub/Sub, LLM)
- Common test utilities and helpers

Usage:
    Fixtures are automatically available to all test files.
    Import from tests.fixtures for additional test data factories.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.app import create_app
from src.app.config import TestingConfig
from src.app.models.document import DocumentSection, DocumentSectionStatus
from src.app.services.state_manager import ReverseDocumentState, get_state
from src.app.services.document_helper import ReverseDocumentHelper

from tests.mocks.mock_cloud_clients import (
    MockStorageClient,
    MockPublisherClient,
    MockSubscriberClient,
    create_mock_storage_client,
    create_mock_publisher,
    create_mock_subscriber,
)
from tests.mocks.mock_llm import (
    MockLLMChain,
    MockChatModel,
    MockCodeGraphBuilder,
    create_mock_llm_chain,
    create_mock_chat_model,
    create_mock_code_graph_builder,
)


@pytest.fixture
def app():
    """
    Create Flask application for testing.
    
    The application is configured with TESTING=True for test isolation.
    """
    app = create_app({"TESTING": True})
    
    # Set up application context
    ctx = app.app_context()
    ctx.push()
    
    yield app
    
    # Clean up
    ctx.pop()


@pytest.fixture
def client(app):
    """
    Flask test client fixture.
    
    Provides a test client for making HTTP requests without running a server.
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    Flask CLI test runner fixture.
    
    Provides a CLI runner for testing Flask CLI commands.
    """
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
    mock_blob.exists.return_value = True
    
    return mock_client


@pytest.fixture
def mock_storage_client_instance():
    """
    Mock Storage client instance fixture.
    
    Returns an actual MockStorageClient instance for more detailed testing.
    """
    return create_mock_storage_client()


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
    mock_publisher.return_value.topic_path.return_value = "projects/test/topics/test-topic"
    
    return mock_publisher


@pytest.fixture
def mock_pubsub_publisher_instance():
    """
    Mock Pub/Sub publisher instance fixture.
    
    Returns an actual MockPublisherClient instance for more detailed testing.
    """
    return create_mock_publisher()


@pytest.fixture
def mock_pubsub_subscriber(mocker):
    """
    Mock Google Cloud Pub/Sub subscriber client fixture.
    
    Provides a mocked Pub/Sub subscriber for testing message consumption
    without making actual cloud API calls.
    """
    mock_subscriber = mocker.patch("google.cloud.pubsub_v1.SubscriberClient")
    mock_subscriber.return_value.subscription_path.return_value = (
        "projects/test/subscriptions/test-subscription"
    )
    return mock_subscriber


@pytest.fixture
def mock_pubsub_subscriber_instance():
    """
    Mock Pub/Sub subscriber instance fixture.
    
    Returns an actual MockSubscriberClient instance for more detailed testing.
    """
    return create_mock_subscriber()


@pytest.fixture
def mock_llm_chain():
    """
    Mock LLM chain fixture.
    
    Provides a mock LLM chain for testing LLM interactions.
    """
    return create_mock_llm_chain()


@pytest.fixture
def mock_chat_model():
    """
    Mock chat model fixture.
    
    Provides a mock chat model for testing.
    """
    return create_mock_chat_model()


@pytest.fixture
def mock_code_graph_builder():
    """
    Mock code graph builder fixture.
    
    Provides a mock CodeGraphBuilder for testing graph operations.
    """
    return create_mock_code_graph_builder()


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
def sample_changed_document_data():
    """
    Sample document data with CHANGED status.
    """
    return {
        "heading": "Changed Section",
        "content": "Modified content",
        "status": "CHANGED",
        "changes": ["Updated heading", "Added new paragraph"]
    }


@pytest.fixture
def sample_section():
    """
    Sample DocumentSection instance for testing.
    """
    return DocumentSection(
        heading="Test Section",
        content="Test content",
        status=DocumentSectionStatus.UNCHANGED
    )


@pytest.fixture
def sample_changed_section():
    """
    Sample DocumentSection with CHANGED status.
    """
    return DocumentSection(
        heading="Changed Section",
        content="Modified content",
        status=DocumentSectionStatus.CHANGED,
        changes=["Change 1", "Change 2"]
    )


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
        "completed": False,
        "error": None,
        "metadata": {}
    }


@pytest.fixture
def sample_state():
    """
    Sample ReverseDocumentState for testing.
    """
    return get_state(
        tech_spec="Sample tech spec content",
        document_sections=[],
        current_section_index=0,
        completed=False
    )


@pytest.fixture
def sample_state_with_sections():
    """
    Sample ReverseDocumentState with document sections.
    """
    sections = [
        {
            "heading": "Section 1",
            "content": "Content 1",
            "status": "UNCHANGED",
            "changes": []
        },
        {
            "heading": "Section 2",
            "content": "Content 2",
            "status": "CHANGED",
            "changes": ["Modified"]
        }
    ]
    return get_state(
        tech_spec="Tech spec with sections",
        document_sections=sections,
        current_section_index=0,
        completed=False
    )


@pytest.fixture
def document_helper():
    """
    ReverseDocumentHelper instance for testing.
    """
    return ReverseDocumentHelper(tech_spec="Test tech spec")


@pytest.fixture
def document_helper_with_tools():
    """
    ReverseDocumentHelper with mock tools for testing.
    """
    tools = {
        "test_tool": lambda x: f"Processed: {x}",
        "another_tool": lambda x, y: f"Combined: {x} + {y}"
    }
    return ReverseDocumentHelper(tech_spec="Test spec", tools=tools)


# Test markers configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: marks test as unit test")
    config.addinivalue_line("markers", "functional: marks test as functional test")
    config.addinivalue_line("markers", "integration: marks test as integration test")
    config.addinivalue_line("markers", "slow: marks test as slow running")


# Autouse fixture to ensure test isolation
@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset any global state between tests."""
    yield
    # Cleanup after test
