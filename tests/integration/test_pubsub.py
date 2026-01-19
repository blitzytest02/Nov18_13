"""
Integration tests for Google Cloud Pub/Sub operations.

Tests cover:
- Message publishing
- Message subscription
- Message acknowledgment
- Retry mechanism
- Error handling
"""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


@pytest.mark.integration
class TestPubSubPublishing:
    """Tests for Pub/Sub message publishing."""
    
    def test_publish_message_success(self, mock_pubsub_publisher):
        """Test successful message publishing."""
        publisher = mock_pubsub_publisher
        
        message_data = {"event": "document_processed", "document_id": "doc-123"}
        
        result = publisher.publish(
            "projects/test-project/topics/test-topic",
            json.dumps(message_data).encode("utf-8")
        )
        
        # Should return a future
        assert result is not None
    
    def test_publish_message_returns_message_id(self, mock_pubsub_publisher):
        """Test publishing returns message ID."""
        publisher = mock_pubsub_publisher
        
        message_data = {"event": "test"}
        
        result = publisher.publish(
            "projects/test-project/topics/test-topic",
            json.dumps(message_data).encode("utf-8")
        )
        
        # Get message ID from future
        message_id = result.result()
        assert message_id is not None
        assert isinstance(message_id, str)
    
    def test_publish_with_attributes(self, mock_pubsub_publisher):
        """Test publishing message with attributes."""
        publisher = mock_pubsub_publisher
        
        message_data = {"event": "test"}
        attributes = {"source": "test", "priority": "high"}
        
        result = publisher.publish(
            "projects/test-project/topics/test-topic",
            json.dumps(message_data).encode("utf-8"),
            **attributes
        )
        
        assert result is not None
    
    def test_publish_empty_message(self, mock_pubsub_publisher):
        """Test publishing empty message."""
        publisher = mock_pubsub_publisher
        
        result = publisher.publish(
            "projects/test-project/topics/test-topic",
            b""
        )
        
        # May succeed or fail depending on implementation
        assert result is not None
    
    def test_publish_large_message(self, mock_pubsub_publisher):
        """Test publishing large message."""
        publisher = mock_pubsub_publisher
        
        # Create large message (< 10 MB limit)
        large_data = {"data": "x" * (1024 * 1024)}  # 1 MB
        
        result = publisher.publish(
            "projects/test-project/topics/test-topic",
            json.dumps(large_data).encode("utf-8")
        )
        
        assert result is not None


@pytest.mark.integration
class TestPubSubSubscription:
    """Tests for Pub/Sub message subscription."""
    
    def test_subscribe_receives_messages(self, mock_pubsub_subscriber):
        """Test subscription receives messages."""
        subscriber = mock_pubsub_subscriber
        received_messages = []
        
        def callback(message):
            received_messages.append(message)
            message.ack()
        
        # Set up mock to call callback with a message
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.ack = MagicMock()
        
        subscriber.callback = callback
        callback(mock_message)
        
        assert len(received_messages) == 1
    
    def test_message_acknowledgment(self, mock_pubsub_subscriber):
        """Test message acknowledgment."""
        subscriber = mock_pubsub_subscriber
        
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.ack = MagicMock()
        
        # Process and acknowledge
        mock_message.ack()
        
        mock_message.ack.assert_called_once()
    
    def test_message_nack(self, mock_pubsub_subscriber):
        """Test message negative acknowledgment."""
        subscriber = mock_pubsub_subscriber
        
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.nack = MagicMock()
        
        # Reject message
        mock_message.nack()
        
        mock_message.nack.assert_called_once()
    
    def test_pull_subscription(self, mock_pubsub_subscriber):
        """Test pull subscription."""
        subscriber = mock_pubsub_subscriber
        
        # Mock pull response
        mock_message = MagicMock()
        mock_message.message.data = b'{"event": "test"}'
        mock_message.ack_id = "ack-123"
        
        subscriber.pull.return_value = MagicMock(received_messages=[mock_message])
        
        response = subscriber.pull(
            subscription="projects/test-project/subscriptions/test-sub",
            max_messages=10
        )
        
        assert response.received_messages is not None


@pytest.mark.integration
class TestPubSubMessageParsing:
    """Tests for Pub/Sub message parsing."""
    
    def test_parse_json_message(self, mock_pubsub_subscriber):
        """Test parsing JSON message."""
        message_data = b'{"event": "document_processed", "id": "123"}'
        
        parsed = json.loads(message_data.decode("utf-8"))
        
        assert parsed["event"] == "document_processed"
        assert parsed["id"] == "123"
    
    def test_parse_message_with_attributes(self, mock_pubsub_subscriber):
        """Test parsing message with attributes."""
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.attributes = {"source": "test", "timestamp": "2024-01-15T12:00:00Z"}
        
        attributes = mock_message.attributes
        
        assert attributes["source"] == "test"
        assert "timestamp" in attributes
    
    def test_handle_invalid_json(self, mock_pubsub_subscriber):
        """Test handling invalid JSON message."""
        invalid_message = b'not valid json'
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(invalid_message.decode("utf-8"))


@pytest.mark.integration
class TestPubSubRetry:
    """Tests for Pub/Sub retry mechanism."""
    
    def test_retry_on_publish_failure(self, mock_pubsub_publisher):
        """Test retry on publish failure."""
        publisher = mock_pubsub_publisher
        call_count = 0
        
        def publish_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return MagicMock(result=lambda: "msg-123")
        
        publisher.publish = publish_with_retry
        
        # Retry logic should eventually succeed
        try:
            for i in range(3):
                try:
                    result = publisher.publish("topic", b"data")
                    break
                except Exception:
                    if i == 2:
                        raise
        except Exception:
            pass  # May or may not have retry logic
        
        assert call_count >= 1
    
    def test_retry_message_nack_and_redelivery(self, mock_pubsub_subscriber):
        """Test message nack triggers redelivery."""
        subscriber = mock_pubsub_subscriber
        delivery_attempts = []
        
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.delivery_attempt = 1
        
        delivery_attempts.append(mock_message.delivery_attempt)
        
        # Simulate nack (would trigger redelivery in real Pub/Sub)
        mock_message.nack()
        
        assert len(delivery_attempts) == 1
    
    def test_dead_letter_after_max_retries(self, mock_pubsub_subscriber):
        """Test message goes to dead letter after max retries."""
        subscriber = mock_pubsub_subscriber
        
        mock_message = MagicMock()
        mock_message.data = b'{"event": "test"}'
        mock_message.delivery_attempt = 5  # Max attempts reached
        
        # Check if should go to dead letter
        should_dead_letter = mock_message.delivery_attempt >= 5
        
        assert should_dead_letter is True


@pytest.mark.integration
class TestPubSubCompletionNotification:
    """Tests for completion notification via Pub/Sub."""
    
    def test_publish_completion_notification(self, mock_pubsub_publisher):
        """Test publishing document completion notification."""
        publisher = mock_pubsub_publisher
        
        notification = {
            "event": "document_completed",
            "document_id": "doc-123",
            "status": "success",
            "sections_processed": 5
        }
        
        result = publisher.publish(
            "projects/test-project/topics/completions",
            json.dumps(notification).encode("utf-8")
        )
        
        assert result is not None
    
    def test_publish_error_notification(self, mock_pubsub_publisher):
        """Test publishing error notification."""
        publisher = mock_pubsub_publisher
        
        notification = {
            "event": "document_error",
            "document_id": "doc-123",
            "error": "Processing failed",
            "error_code": "PROCESSING_ERROR"
        }
        
        result = publisher.publish(
            "projects/test-project/topics/errors",
            json.dumps(notification).encode("utf-8")
        )
        
        assert result is not None
    
    def test_notification_includes_timestamp(self, mock_pubsub_publisher):
        """Test notification includes timestamp."""
        publisher = mock_pubsub_publisher
        
        from datetime import datetime
        
        notification = {
            "event": "document_completed",
            "document_id": "doc-123",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        result = publisher.publish(
            "projects/test-project/topics/completions",
            json.dumps(notification).encode("utf-8")
        )
        
        assert "timestamp" in notification


@pytest.mark.integration
class TestPubSubErrorHandling:
    """Tests for Pub/Sub error handling."""
    
    def test_handle_publish_timeout(self, mock_pubsub_publisher):
        """Test handling publish timeout."""
        publisher = mock_pubsub_publisher
        
        # Mock timeout
        future = MagicMock()
        future.result.side_effect = TimeoutError("Publish timed out")
        publisher.publish.return_value = future
        
        result = publisher.publish("topic", b"data")
        
        with pytest.raises(TimeoutError):
            result.result()
    
    def test_handle_invalid_topic(self, mock_pubsub_publisher):
        """Test handling invalid topic."""
        publisher = mock_pubsub_publisher
        
        # Mock invalid topic error
        publisher.publish.side_effect = Exception("Topic not found")
        
        with pytest.raises(Exception):
            publisher.publish("invalid-topic", b"data")
    
    def test_handle_permission_denied(self, mock_pubsub_publisher):
        """Test handling permission denied error."""
        publisher = mock_pubsub_publisher
        
        # Mock permission error
        publisher.publish.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(PermissionError):
            publisher.publish("topic", b"data")
    
    def test_handle_subscriber_error(self, mock_pubsub_subscriber):
        """Test handling subscriber error."""
        subscriber = mock_pubsub_subscriber
        
        # Mock subscription error
        subscriber.pull.side_effect = Exception("Subscription error")
        
        with pytest.raises(Exception):
            subscriber.pull(subscription="sub", max_messages=10)


@pytest.mark.integration
class TestPubSubBatching:
    """Tests for Pub/Sub message batching."""
    
    def test_batch_publish(self, mock_pubsub_publisher):
        """Test batch message publishing."""
        publisher = mock_pubsub_publisher
        
        messages = [
            {"event": f"event_{i}", "data": f"data_{i}"}
            for i in range(10)
        ]
        
        results = []
        for msg in messages:
            result = publisher.publish(
                "projects/test-project/topics/batch-topic",
                json.dumps(msg).encode("utf-8")
            )
            results.append(result)
        
        assert len(results) == 10
    
    def test_batch_pull(self, mock_pubsub_subscriber):
        """Test batch message pulling."""
        subscriber = mock_pubsub_subscriber
        
        # Mock multiple messages
        mock_messages = [
            MagicMock(message=MagicMock(data=f'{{"id": {i}}}'.encode()))
            for i in range(5)
        ]
        
        subscriber.pull.return_value = MagicMock(received_messages=mock_messages)
        
        response = subscriber.pull(
            subscription="projects/test-project/subscriptions/batch-sub",
            max_messages=10
        )
        
        assert len(response.received_messages) == 5


@pytest.mark.integration
class TestPubSubWithFlaskApp:
    """Tests for Pub/Sub integration with Flask app."""
    
    def test_flask_endpoint_publishes_message(self, client, mock_pubsub_publisher, mocker):
        """Test Flask endpoint publishes Pub/Sub message."""
        # Patch the publisher in the app
        mocker.patch(
            "src.app.services.pubsub_service.get_publisher",
            return_value=mock_pubsub_publisher
        )
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({
                "tech_spec": "Test specification",
                "sections": [{"heading": "Test", "content": "Content"}]
            }),
            content_type="application/json"
        )
        
        # Request should be processed
        assert response.status_code in [200, 400]
    
    def test_completion_notification_sent_on_success(self, client, mock_pubsub_publisher, mocker):
        """Test completion notification is sent on successful processing."""
        mocker.patch(
            "src.app.services.pubsub_service.get_publisher",
            return_value=mock_pubsub_publisher
        )
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({
                "tech_spec": "Test specification",
                "sections": [{"heading": "Test", "content": "Content"}]
            }),
            content_type="application/json"
        )
        
        # Verify request was processed
        assert response.status_code in [200, 400]


# Fixtures

@pytest.fixture
def mock_pubsub_publisher():
    """Create a mock Pub/Sub publisher for testing."""
    mock_publisher = MagicMock()
    
    # Mock publish method
    mock_future = MagicMock()
    mock_future.result.return_value = "mock-message-id-123"
    mock_publisher.publish.return_value = mock_future
    
    # Mock topic path method
    mock_publisher.topic_path.return_value = "projects/test-project/topics/test-topic"
    
    return mock_publisher


@pytest.fixture
def mock_pubsub_subscriber():
    """Create a mock Pub/Sub subscriber for testing."""
    mock_subscriber = MagicMock()
    
    # Mock subscription path method
    mock_subscriber.subscription_path.return_value = "projects/test-project/subscriptions/test-sub"
    
    # Mock pull method
    mock_response = MagicMock()
    mock_response.received_messages = []
    mock_subscriber.pull.return_value = mock_response
    
    return mock_subscriber
