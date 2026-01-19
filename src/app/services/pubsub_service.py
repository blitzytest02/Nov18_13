"""
Google Cloud Pub/Sub service for the reverse document generator.

This module provides functionality for publishing messages to and
subscribing from Google Cloud Pub/Sub topics.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Optional import for Google Cloud Pub/Sub
try:
    from google.cloud import pubsub_v1
    from google.cloud.pubsub_v1.publisher.futures import Future
    PUBSUB_AVAILABLE = True
except ImportError:
    PUBSUB_AVAILABLE = False
    pubsub_v1 = None
    Future = None


class PubSubService:
    """
    Service class for Google Cloud Pub/Sub operations.
    
    This class provides methods for publishing messages and
    managing subscriptions.
    
    Attributes:
        project_id: Google Cloud project ID
        publisher: Pub/Sub publisher client
        subscriber: Pub/Sub subscriber client
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        publisher: Optional[Any] = None,
        subscriber: Optional[Any] = None
    ):
        """
        Initialize the Pub/Sub service.
        
        Args:
            project_id: Google Cloud project ID
            publisher: Optional pre-configured publisher client
            subscriber: Optional pre-configured subscriber client
        """
        self.project_id = project_id
        self._publisher = publisher
        self._subscriber = subscriber
    
    @property
    def publisher(self) -> Any:
        """
        Get or create the Pub/Sub publisher client.
        
        Returns:
            Publisher client instance
        """
        if self._publisher is None and PUBSUB_AVAILABLE:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher
    
    @property
    def subscriber(self) -> Any:
        """
        Get or create the Pub/Sub subscriber client.
        
        Returns:
            Subscriber client instance
        """
        if self._subscriber is None and PUBSUB_AVAILABLE:
            self._subscriber = pubsub_v1.SubscriberClient()
        return self._subscriber
    
    def get_topic_path(self, topic_id: str) -> str:
        """
        Get the full topic path.
        
        Args:
            topic_id: Topic identifier
            
        Returns:
            Full topic path string
        """
        if self.publisher and hasattr(self.publisher, 'topic_path'):
            return self.publisher.topic_path(self.project_id, topic_id)
        return f"projects/{self.project_id}/topics/{topic_id}"
    
    def get_subscription_path(self, subscription_id: str) -> str:
        """
        Get the full subscription path.
        
        Args:
            subscription_id: Subscription identifier
            
        Returns:
            Full subscription path string
        """
        if self.subscriber and hasattr(self.subscriber, 'subscription_path'):
            return self.subscriber.subscription_path(self.project_id, subscription_id)
        return f"projects/{self.project_id}/subscriptions/{subscription_id}"
    
    def publish(
        self,
        topic_id: str,
        data: Dict[str, Any],
        **attributes: str
    ) -> Optional[str]:
        """
        Publish a message to a Pub/Sub topic.
        
        Args:
            topic_id: Topic identifier or full topic path
            data: Message data as dictionary
            **attributes: Optional message attributes
            
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.publisher:
            logger.warning("Pub/Sub publisher not available")
            return None
        
        try:
            # Encode the data
            message_bytes = json.dumps(data).encode("utf-8")
            
            # Determine topic path
            if topic_id.startswith("projects/"):
                topic_path = topic_id
            else:
                topic_path = self.get_topic_path(topic_id)
            
            # Publish the message
            future = self.publisher.publish(
                topic_path,
                message_bytes,
                **attributes
            )
            
            # Wait for the result
            message_id = future.result()
            logger.info(f"Published message {message_id} to {topic_path}")
            
            return message_id
            
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise
    
    def publish_completion_notification(
        self,
        document_id: str,
        status: str = "success",
        sections_processed: int = 0,
        topic_id: str = "completions"
    ) -> Optional[str]:
        """
        Publish a document completion notification.
        
        Args:
            document_id: Document identifier
            status: Completion status
            sections_processed: Number of sections processed
            topic_id: Topic identifier
            
        Returns:
            Message ID if successful
        """
        from datetime import datetime
        
        notification = {
            "event": "document_completed",
            "document_id": document_id,
            "status": status,
            "sections_processed": sections_processed,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return self.publish(topic_id, notification, event_type="completion")
    
    def publish_error_notification(
        self,
        document_id: str,
        error: str,
        error_code: str = "PROCESSING_ERROR",
        topic_id: str = "errors"
    ) -> Optional[str]:
        """
        Publish an error notification.
        
        Args:
            document_id: Document identifier
            error: Error message
            error_code: Error code
            topic_id: Topic identifier
            
        Returns:
            Message ID if successful
        """
        from datetime import datetime
        
        notification = {
            "event": "document_error",
            "document_id": document_id,
            "error": error,
            "error_code": error_code,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return self.publish(topic_id, notification, event_type="error")
    
    def subscribe(
        self,
        subscription_id: str,
        callback: Callable[[Any], None],
        timeout: Optional[float] = None
    ) -> Optional[Any]:
        """
        Subscribe to a Pub/Sub subscription.
        
        Args:
            subscription_id: Subscription identifier
            callback: Callback function for received messages
            timeout: Optional timeout in seconds
            
        Returns:
            Streaming pull future if successful
        """
        if not self.subscriber:
            logger.warning("Pub/Sub subscriber not available")
            return None
        
        try:
            subscription_path = self.get_subscription_path(subscription_id)
            
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path,
                callback=callback
            )
            
            logger.info(f"Subscribed to {subscription_path}")
            
            if timeout:
                streaming_pull_future.result(timeout=timeout)
            
            return streaming_pull_future
            
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            raise
    
    def pull(
        self,
        subscription_id: str,
        max_messages: int = 10
    ) -> list:
        """
        Pull messages from a subscription.
        
        Args:
            subscription_id: Subscription identifier
            max_messages: Maximum number of messages to pull
            
        Returns:
            List of received messages
        """
        if not self.subscriber:
            logger.warning("Pub/Sub subscriber not available")
            return []
        
        try:
            subscription_path = self.get_subscription_path(subscription_id)
            
            response = self.subscriber.pull(
                subscription=subscription_path,
                max_messages=max_messages
            )
            
            return list(response.received_messages)
            
        except Exception as e:
            logger.error(f"Failed to pull messages: {e}")
            raise
    
    def acknowledge(self, subscription_id: str, ack_ids: list) -> None:
        """
        Acknowledge received messages.
        
        Args:
            subscription_id: Subscription identifier
            ack_ids: List of acknowledgment IDs
        """
        if not self.subscriber:
            logger.warning("Pub/Sub subscriber not available")
            return
        
        try:
            subscription_path = self.get_subscription_path(subscription_id)
            
            self.subscriber.acknowledge(
                subscription=subscription_path,
                ack_ids=ack_ids
            )
            
            logger.info(f"Acknowledged {len(ack_ids)} messages")
            
        except Exception as e:
            logger.error(f"Failed to acknowledge messages: {e}")
            raise


# Global service instance
_pubsub_service: Optional[PubSubService] = None


def get_pubsub_service(project_id: Optional[str] = None) -> PubSubService:
    """
    Get or create the global Pub/Sub service instance.
    
    Args:
        project_id: Optional Google Cloud project ID
        
    Returns:
        PubSubService instance
    """
    global _pubsub_service
    
    if _pubsub_service is None:
        _pubsub_service = PubSubService(project_id=project_id)
    
    return _pubsub_service


def get_publisher() -> Optional[Any]:
    """
    Get the Pub/Sub publisher client.
    
    Returns:
        Publisher client or None if not available
    """
    service = get_pubsub_service()
    return service.publisher


def get_subscriber() -> Optional[Any]:
    """
    Get the Pub/Sub subscriber client.
    
    Returns:
        Subscriber client or None if not available
    """
    service = get_pubsub_service()
    return service.subscriber


def publish_message(
    topic_id: str,
    data: Dict[str, Any],
    **attributes: str
) -> Optional[str]:
    """
    Convenience function to publish a message.
    
    Args:
        topic_id: Topic identifier
        data: Message data
        **attributes: Message attributes
        
    Returns:
        Message ID if successful
    """
    service = get_pubsub_service()
    return service.publish(topic_id, data, **attributes)
