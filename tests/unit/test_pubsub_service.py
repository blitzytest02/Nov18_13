"""
Unit tests for the Pub/Sub service module.

Tests cover:
- PubSubService initialization
- Topic and subscription path construction
- Message publishing
- Completion and error notifications
- Message subscription and acknowledgment
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any, Dict


class TestPubSubServiceInit:
    """Tests for PubSubService initialization."""
    
    def test_init_with_project_id(self):
        """Test PubSubService initializes with project ID."""
        from src.app.services.pubsub_service import PubSubService
        
        service = PubSubService(project_id="test-project")
        
        assert service.project_id == "test-project"
        assert service._publisher is None
        assert service._subscriber is None
    
    def test_init_with_custom_clients(self):
        """Test PubSubService accepts pre-configured clients."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_subscriber = MagicMock()
        
        service = PubSubService(
            project_id="test-project",
            publisher=mock_publisher,
            subscriber=mock_subscriber
        )
        
        assert service._publisher is mock_publisher
        assert service._subscriber is mock_subscriber
    
    def test_init_without_arguments(self):
        """Test PubSubService can be created without arguments."""
        from src.app.services.pubsub_service import PubSubService
        
        service = PubSubService()
        
        assert service.project_id is None
        assert service._publisher is None


class TestPubSubServicePaths:
    """Tests for path construction methods."""
    
    def test_get_topic_path_with_publisher(self):
        """Test topic path generation with publisher."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_publisher.topic_path.return_value = "projects/test-project/topics/test-topic"
        
        service = PubSubService(
            project_id="test-project",
            publisher=mock_publisher
        )
        
        path = service.get_topic_path("test-topic")
        
        assert path == "projects/test-project/topics/test-topic"
        mock_publisher.topic_path.assert_called_once_with("test-project", "test-topic")
    
    def test_get_topic_path_fallback(self):
        """Test topic path fallback when no publisher."""
        from src.app.services.pubsub_service import PubSubService
        
        service = PubSubService(project_id="test-project")
        
        path = service.get_topic_path("test-topic")
        
        assert path == "projects/test-project/topics/test-topic"
    
    def test_get_subscription_path_with_subscriber(self):
        """Test subscription path generation with subscriber."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_subscriber = MagicMock()
        mock_subscriber.subscription_path.return_value = "projects/test-project/subscriptions/test-sub"
        
        service = PubSubService(
            project_id="test-project",
            subscriber=mock_subscriber
        )
        
        path = service.get_subscription_path("test-sub")
        
        assert path == "projects/test-project/subscriptions/test-sub"
        mock_subscriber.subscription_path.assert_called_once_with("test-project", "test-sub")
    
    def test_get_subscription_path_fallback(self):
        """Test subscription path fallback when no subscriber."""
        from src.app.services.pubsub_service import PubSubService
        
        service = PubSubService(project_id="test-project")
        
        path = service.get_subscription_path("test-sub")
        
        assert path == "projects/test-project/subscriptions/test-sub"


class TestPubSubServicePublish:
    """Tests for message publishing."""
    
    def test_publish_success(self):
        """Test successful message publishing."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "message-id-123"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/test/topics/topic1"
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        result = service.publish("topic1", {"key": "value"})
        
        assert result == "message-id-123"
        mock_publisher.publish.assert_called_once()
    
    def test_publish_with_full_topic_path(self):
        """Test publishing with full topic path."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "msg-456"
        mock_publisher.publish.return_value = mock_future
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        full_path = "projects/test/topics/full-topic"
        result = service.publish(full_path, {"data": "test"})
        
        assert result == "msg-456"
        # Verify the full path was used directly
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == full_path
    
    def test_publish_with_attributes(self):
        """Test publishing with message attributes."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "msg-789"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/test/topics/topic"
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        result = service.publish(
            "topic",
            {"message": "test"},
            attr1="value1",
            attr2="value2"
        )
        
        assert result == "msg-789"
        call_kwargs = mock_publisher.publish.call_args[1]
        assert call_kwargs.get("attr1") == "value1"
        assert call_kwargs.get("attr2") == "value2"
    
    def test_publish_without_publisher_returns_none(self, mocker):
        """Test publish returns None when no publisher available."""
        from src.app.services.pubsub_service import PubSubService
        
        # Patch PUBSUB_AVAILABLE to False so no real client is created
        mocker.patch('src.app.services.pubsub_service.PUBSUB_AVAILABLE', False)
        
        service = PubSubService(project_id="test")
        
        result = service.publish("topic", {"data": "test"})
        
        assert result is None
    
    def test_publish_raises_on_error(self):
        """Test publish raises exception on failure."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_publisher.publish.side_effect = Exception("Publish failed")
        mock_publisher.topic_path.return_value = "projects/test/topics/topic"
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        with pytest.raises(Exception, match="Publish failed"):
            service.publish("topic", {"data": "test"})


class TestPubSubServiceNotifications:
    """Tests for notification methods."""
    
    def test_publish_completion_notification(self):
        """Test publishing completion notification."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "completion-msg"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/test/topics/completions"
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        result = service.publish_completion_notification(
            document_id="doc-123",
            status="success",
            sections_processed=5
        )
        
        assert result == "completion-msg"
        
        # Verify the message content
        call_args = mock_publisher.publish.call_args
        message_bytes = call_args[0][1]
        message_data = json.loads(message_bytes.decode("utf-8"))
        
        assert message_data["event"] == "document_completed"
        assert message_data["document_id"] == "doc-123"
        assert message_data["status"] == "success"
        assert message_data["sections_processed"] == 5
        assert "timestamp" in message_data
    
    def test_publish_error_notification(self):
        """Test publishing error notification."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "error-msg"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/test/topics/errors"
        
        service = PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        
        result = service.publish_error_notification(
            document_id="doc-456",
            error="Processing failed",
            error_code="PROC_ERROR"
        )
        
        assert result == "error-msg"
        
        # Verify the message content
        call_args = mock_publisher.publish.call_args
        message_bytes = call_args[0][1]
        message_data = json.loads(message_bytes.decode("utf-8"))
        
        assert message_data["event"] == "document_error"
        assert message_data["document_id"] == "doc-456"
        assert message_data["error"] == "Processing failed"
        assert message_data["error_code"] == "PROC_ERROR"


class TestPubSubServiceSubscribe:
    """Tests for subscription methods."""
    
    def test_subscribe_success(self):
        """Test successful subscription."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_subscriber = MagicMock()
        mock_future = MagicMock()
        mock_subscriber.subscribe.return_value = mock_future
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/sub1"
        
        service = PubSubService(
            project_id="test",
            subscriber=mock_subscriber
        )
        
        callback = MagicMock()
        result = service.subscribe("sub1", callback)
        
        assert result is mock_future
        mock_subscriber.subscribe.assert_called_once()
    
    def test_subscribe_with_timeout(self):
        """Test subscription with timeout."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_subscriber = MagicMock()
        mock_future = MagicMock()
        mock_subscriber.subscribe.return_value = mock_future
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/sub1"
        
        service = PubSubService(
            project_id="test",
            subscriber=mock_subscriber
        )
        
        callback = MagicMock()
        service.subscribe("sub1", callback, timeout=30)
        
        mock_future.result.assert_called_once_with(timeout=30)
    
    def test_subscribe_without_subscriber(self, mocker):
        """Test subscribe returns None when no subscriber available."""
        from src.app.services.pubsub_service import PubSubService
        
        # Patch PUBSUB_AVAILABLE to False
        mocker.patch('src.app.services.pubsub_service.PUBSUB_AVAILABLE', False)
        
        service = PubSubService(project_id="test")
        
        result = service.subscribe("sub1", MagicMock())
        
        assert result is None
    
    def test_pull_messages(self):
        """Test pulling messages from subscription."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_subscriber = MagicMock()
        mock_response = MagicMock()
        mock_response.received_messages = [
            MagicMock(ack_id="ack1"),
            MagicMock(ack_id="ack2")
        ]
        mock_subscriber.pull.return_value = mock_response
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/sub1"
        
        service = PubSubService(
            project_id="test",
            subscriber=mock_subscriber
        )
        
        messages = service.pull("sub1", max_messages=10)
        
        assert len(messages) == 2
        mock_subscriber.pull.assert_called_once()
    
    def test_pull_without_subscriber(self, mocker):
        """Test pull returns empty list when no subscriber available."""
        from src.app.services.pubsub_service import PubSubService
        
        # Patch PUBSUB_AVAILABLE to False
        mocker.patch('src.app.services.pubsub_service.PUBSUB_AVAILABLE', False)
        
        service = PubSubService(project_id="test")
        
        result = service.pull("sub1")
        
        assert result == []
    
    def test_acknowledge_messages(self):
        """Test acknowledging messages."""
        from src.app.services.pubsub_service import PubSubService
        
        mock_subscriber = MagicMock()
        mock_subscriber.subscription_path.return_value = "projects/test/subscriptions/sub1"
        
        service = PubSubService(
            project_id="test",
            subscriber=mock_subscriber
        )
        
        service.acknowledge("sub1", ["ack1", "ack2", "ack3"])
        
        mock_subscriber.acknowledge.assert_called_once()
        call_kwargs = mock_subscriber.acknowledge.call_args[1]
        assert call_kwargs["ack_ids"] == ["ack1", "ack2", "ack3"]
    
    def test_acknowledge_without_subscriber(self, mocker):
        """Test acknowledge does nothing when no subscriber available."""
        from src.app.services.pubsub_service import PubSubService
        
        # Patch PUBSUB_AVAILABLE to False
        mocker.patch('src.app.services.pubsub_service.PUBSUB_AVAILABLE', False)
        
        service = PubSubService(project_id="test")
        
        # Should not raise
        service.acknowledge("sub1", ["ack1"])


class TestPubSubServiceHelpers:
    """Tests for helper functions."""
    
    def test_get_pubsub_service(self):
        """Test getting global Pub/Sub service instance."""
        from src.app.services.pubsub_service import get_pubsub_service, _pubsub_service
        import src.app.services.pubsub_service as pubsub_module
        
        # Reset global state
        pubsub_module._pubsub_service = None
        
        service = get_pubsub_service(project_id="test-project")
        
        assert service is not None
        assert service.project_id == "test-project"
        
        # Should return same instance
        service2 = get_pubsub_service()
        assert service is service2
        
        # Cleanup
        pubsub_module._pubsub_service = None
    
    def test_get_publisher(self):
        """Test getting publisher client."""
        from src.app.services.pubsub_service import get_publisher, get_pubsub_service
        import src.app.services.pubsub_service as pubsub_module
        
        # Reset global state
        pubsub_module._pubsub_service = None
        
        mock_publisher = MagicMock()
        service = pubsub_module.PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        pubsub_module._pubsub_service = service
        
        publisher = get_publisher()
        
        assert publisher is mock_publisher
        
        # Cleanup
        pubsub_module._pubsub_service = None
    
    def test_get_subscriber(self):
        """Test getting subscriber client."""
        from src.app.services.pubsub_service import get_subscriber
        import src.app.services.pubsub_service as pubsub_module
        
        # Reset global state
        pubsub_module._pubsub_service = None
        
        mock_subscriber = MagicMock()
        service = pubsub_module.PubSubService(
            project_id="test",
            subscriber=mock_subscriber
        )
        pubsub_module._pubsub_service = service
        
        subscriber = get_subscriber()
        
        assert subscriber is mock_subscriber
        
        # Cleanup
        pubsub_module._pubsub_service = None
    
    def test_publish_message_convenience_function(self):
        """Test publish_message convenience function."""
        from src.app.services.pubsub_service import publish_message
        import src.app.services.pubsub_service as pubsub_module
        
        # Reset global state
        pubsub_module._pubsub_service = None
        
        mock_publisher = MagicMock()
        mock_future = MagicMock()
        mock_future.result.return_value = "msg-id"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/test/topics/topic"
        
        service = pubsub_module.PubSubService(
            project_id="test",
            publisher=mock_publisher
        )
        pubsub_module._pubsub_service = service
        
        result = publish_message("topic", {"data": "test"}, attr="value")
        
        assert result == "msg-id"
        
        # Cleanup
        pubsub_module._pubsub_service = None
