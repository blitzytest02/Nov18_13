"""
Mock implementations for Google Cloud service clients.

This module provides mock classes for GCS and Pub/Sub clients to enable
testing without making actual cloud API calls.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from tests.fixtures.cloud_responses import (
    GCS_BLOB_RESPONSE,
    GCS_BUCKET_RESPONSE,
    GCS_DOWNLOAD_CONTENT,
    GCS_UPLOAD_RESPONSE,
    PUBSUB_ACKNOWLEDGE_RESPONSE,
    PUBSUB_COMPLETION_PAYLOAD,
    PUBSUB_PUBLISH_RESPONSE,
    PUBSUB_PULL_RESPONSE,
    create_pubsub_message,
)


class MockBlob:
    """
    Mock implementation of google.cloud.storage.Blob.
    
    Simulates blob operations without actual GCS calls.
    """
    
    def __init__(
        self,
        name: str,
        bucket: "MockBucket" = None,
        content: bytes = GCS_DOWNLOAD_CONTENT
    ):
        self.name = name
        self.bucket = bucket
        self._content = content
        self._exists = True
        self.upload_calls: List[Dict[str, Any]] = []
        self.download_calls: int = 0
    
    def upload_from_string(
        self,
        data: bytes,
        content_type: str = "application/octet-stream"
    ) -> None:
        """Mock upload from string."""
        self._content = data
        self.upload_calls.append({
            "data": data,
            "content_type": content_type
        })
    
    def upload_from_file(
        self,
        file_obj: Any,
        content_type: str = "application/octet-stream"
    ) -> None:
        """Mock upload from file object."""
        self._content = file_obj.read()
        self.upload_calls.append({
            "file": file_obj,
            "content_type": content_type
        })
    
    def download_as_string(self) -> bytes:
        """Mock download as string."""
        self.download_calls += 1
        if not self._exists:
            raise Exception("Blob does not exist")
        return self._content
    
    def download_as_bytes(self) -> bytes:
        """Mock download as bytes."""
        return self.download_as_string()
    
    def download_to_file(self, file_obj: Any) -> None:
        """Mock download to file object."""
        content = self.download_as_string()
        file_obj.write(content)
    
    def exists(self) -> bool:
        """Check if blob exists."""
        return self._exists
    
    def delete(self) -> None:
        """Mock delete blob."""
        self._exists = False
    
    def set_exists(self, exists: bool) -> None:
        """Helper to set existence state for testing."""
        self._exists = exists
    
    def set_content(self, content: bytes) -> None:
        """Helper to set content for testing."""
        self._content = content


class MockBucket:
    """
    Mock implementation of google.cloud.storage.Bucket.
    
    Simulates bucket operations without actual GCS calls.
    """
    
    def __init__(self, name: str = "test-bucket"):
        self.name = name
        self._blobs: Dict[str, MockBlob] = {}
    
    def blob(self, blob_name: str) -> MockBlob:
        """Get or create a mock blob."""
        if blob_name not in self._blobs:
            self._blobs[blob_name] = MockBlob(blob_name, self)
        return self._blobs[blob_name]
    
    def list_blobs(
        self,
        prefix: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[MockBlob]:
        """List blobs in the bucket."""
        blobs = list(self._blobs.values())
        if prefix:
            blobs = [b for b in blobs if b.name.startswith(prefix)]
        if max_results:
            blobs = blobs[:max_results]
        return blobs
    
    def delete_blob(self, blob_name: str) -> None:
        """Delete a blob from the bucket."""
        if blob_name in self._blobs:
            self._blobs[blob_name].delete()
            del self._blobs[blob_name]
    
    def exists(self) -> bool:
        """Check if bucket exists."""
        return True


class MockStorageClient:
    """
    Mock implementation of google.cloud.storage.Client.
    
    Simulates GCS client operations without actual API calls.
    """
    
    def __init__(self, project: str = "test-project"):
        self.project = project
        self._buckets: Dict[str, MockBucket] = {}
    
    def bucket(self, bucket_name: str) -> MockBucket:
        """Get or create a mock bucket."""
        if bucket_name not in self._buckets:
            self._buckets[bucket_name] = MockBucket(bucket_name)
        return self._buckets[bucket_name]
    
    def create_bucket(self, bucket_name: str) -> MockBucket:
        """Create a new bucket."""
        bucket = MockBucket(bucket_name)
        self._buckets[bucket_name] = bucket
        return bucket
    
    def list_buckets(self) -> List[MockBucket]:
        """List all buckets."""
        return list(self._buckets.values())


class MockFuture:
    """
    Mock implementation of google.cloud.pubsub_v1.publisher.futures.Future.
    
    Simulates Pub/Sub publish future without actual API calls.
    """
    
    def __init__(self, message_id: str = "mock-message-id"):
        self._message_id = message_id
        self._done = True
        self._exception = None
    
    def result(self, timeout: Optional[float] = None) -> str:
        """Get the result (message ID)."""
        if self._exception:
            raise self._exception
        return self._message_id
    
    def done(self) -> bool:
        """Check if the future is done."""
        return self._done
    
    def exception(self) -> Optional[Exception]:
        """Get any exception that occurred."""
        return self._exception
    
    def set_exception(self, exc: Exception) -> None:
        """Set an exception for testing error scenarios."""
        self._exception = exc


class MockPublisherClient:
    """
    Mock implementation of google.cloud.pubsub_v1.PublisherClient.
    
    Simulates Pub/Sub publisher without actual API calls.
    """
    
    def __init__(self):
        self.published_messages: List[Dict[str, Any]] = []
        self._next_message_id = 1
    
    def publish(
        self,
        topic: str,
        data: bytes,
        **attrs: str
    ) -> MockFuture:
        """Mock publish a message."""
        message_id = f"msg-{self._next_message_id}"
        self._next_message_id += 1
        
        self.published_messages.append({
            "topic": topic,
            "data": data,
            "attributes": attrs,
            "message_id": message_id
        })
        
        return MockFuture(message_id)
    
    def topic_path(self, project: str, topic: str) -> str:
        """Get the topic path."""
        return f"projects/{project}/topics/{topic}"
    
    def clear_messages(self) -> None:
        """Clear published messages (for test cleanup)."""
        self.published_messages = []


class MockReceivedMessage:
    """
    Mock implementation of a received Pub/Sub message.
    """
    
    def __init__(
        self,
        data: bytes,
        attributes: Dict[str, str] = None,
        message_id: str = "mock-msg-id",
        ack_id: str = "mock-ack-id"
    ):
        self.data = data
        self.attributes = attributes or {}
        self.message_id = message_id
        self.ack_id = ack_id
        self._acked = False
        self._nacked = False
    
    def ack(self) -> None:
        """Acknowledge the message."""
        self._acked = True
    
    def nack(self) -> None:
        """Negative acknowledge the message."""
        self._nacked = True


class MockSubscriberClient:
    """
    Mock implementation of google.cloud.pubsub_v1.SubscriberClient.
    
    Simulates Pub/Sub subscriber without actual API calls.
    """
    
    def __init__(self):
        self._messages: List[MockReceivedMessage] = []
        self.acknowledged_ids: List[str] = []
    
    def subscription_path(self, project: str, subscription: str) -> str:
        """Get the subscription path."""
        return f"projects/{project}/subscriptions/{subscription}"
    
    def pull(
        self,
        subscription: str,
        max_messages: int = 10,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Mock pull messages from subscription."""
        messages = self._messages[:max_messages]
        return {
            "received_messages": [
                {
                    "ack_id": msg.ack_id,
                    "message": {
                        "data": msg.data,
                        "attributes": msg.attributes,
                        "message_id": msg.message_id
                    }
                }
                for msg in messages
            ]
        }
    
    def acknowledge(self, subscription: str, ack_ids: List[str]) -> None:
        """Acknowledge messages."""
        self.acknowledged_ids.extend(ack_ids)
        self._messages = [m for m in self._messages if m.ack_id not in ack_ids]
    
    def add_message(
        self,
        data: bytes,
        attributes: Dict[str, str] = None,
        message_id: str = None,
        ack_id: str = None
    ) -> None:
        """Add a message for testing."""
        msg = MockReceivedMessage(
            data=data,
            attributes=attributes,
            message_id=message_id or f"msg-{len(self._messages)}",
            ack_id=ack_id or f"ack-{len(self._messages)}"
        )
        self._messages.append(msg)
    
    def clear_messages(self) -> None:
        """Clear all messages (for test cleanup)."""
        self._messages = []
        self.acknowledged_ids = []


def create_mock_storage_client() -> MockStorageClient:
    """
    Create a configured mock storage client.
    
    Returns:
        MockStorageClient instance
    """
    return MockStorageClient()


def create_mock_publisher() -> MockPublisherClient:
    """
    Create a configured mock publisher client.
    
    Returns:
        MockPublisherClient instance
    """
    return MockPublisherClient()


def create_mock_subscriber(
    messages: Optional[List[Dict[str, Any]]] = None
) -> MockSubscriberClient:
    """
    Create a configured mock subscriber client.
    
    Args:
        messages: Optional list of messages to pre-populate
        
    Returns:
        MockSubscriberClient instance
    """
    client = MockSubscriberClient()
    if messages:
        for msg in messages:
            client.add_message(
                data=msg.get("data", b""),
                attributes=msg.get("attributes"),
                message_id=msg.get("message_id"),
                ack_id=msg.get("ack_id")
            )
    return client
