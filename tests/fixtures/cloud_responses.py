"""
Mock responses for Google Cloud services.

This module provides sample response data for testing GCS and Pub/Sub
integrations without making actual cloud API calls.
"""

from typing import Any, Dict, List


# Google Cloud Storage Mock Responses
GCS_BUCKET_RESPONSE = {
    "name": "test-bucket",
    "location": "US-CENTRAL1",
    "storage_class": "STANDARD",
    "created": "2024-01-01T00:00:00Z"
}

GCS_BLOB_RESPONSE = {
    "name": "documents/test-doc.json",
    "bucket": "test-bucket",
    "generation": "1234567890123456",
    "metageneration": "1",
    "contentType": "application/json",
    "storageClass": "STANDARD",
    "size": "1024",
    "md5Hash": "abc123def456=",
    "crc32c": "xyz789=",
    "etag": "COKh8+qv3eUCEAE=",
    "timeCreated": "2024-01-01T00:00:00Z",
    "updated": "2024-01-01T00:00:00Z"
}

GCS_BLOB_LIST_RESPONSE = {
    "kind": "storage#objects",
    "items": [
        {
            "name": "documents/doc1.json",
            "bucket": "test-bucket",
            "size": "512"
        },
        {
            "name": "documents/doc2.json",
            "bucket": "test-bucket",
            "size": "1024"
        }
    ]
}

GCS_UPLOAD_RESPONSE = {
    "name": "documents/uploaded-doc.json",
    "bucket": "test-bucket",
    "generation": "1234567890123456",
    "size": "2048",
    "timeCreated": "2024-01-01T12:00:00Z"
}

GCS_DOWNLOAD_CONTENT = b'{"tech_spec": "Sample tech spec content", "version": "1.0"}'

GCS_ERROR_NOT_FOUND = {
    "error": {
        "code": 404,
        "message": "No such object: test-bucket/nonexistent.json",
        "errors": [
            {
                "message": "No such object: test-bucket/nonexistent.json",
                "domain": "global",
                "reason": "notFound"
            }
        ]
    }
}

GCS_ERROR_FORBIDDEN = {
    "error": {
        "code": 403,
        "message": "Access denied",
        "errors": [
            {
                "message": "Access denied",
                "domain": "global",
                "reason": "forbidden"
            }
        ]
    }
}


# Google Cloud Pub/Sub Mock Responses
PUBSUB_PUBLISH_RESPONSE = {
    "messageIds": ["1234567890"]
}

PUBSUB_MESSAGE = {
    "data": "eyJ0ZWNoX3NwZWMiOiAiU2FtcGxlIHNwZWMifQ==",  # base64 encoded
    "attributes": {
        "source": "reverse-document-generator",
        "timestamp": "2024-01-01T00:00:00Z"
    },
    "messageId": "1234567890",
    "publishTime": "2024-01-01T00:00:00Z"
}

PUBSUB_PULL_RESPONSE = {
    "receivedMessages": [
        {
            "ackId": "ack-id-1",
            "message": {
                "data": "eyJ0YXNrX2lkIjogIjEyMyIsICJzdGF0dXMiOiAiY29tcGxldGUifQ==",
                "attributes": {
                    "type": "completion_notification"
                },
                "messageId": "msg-1",
                "publishTime": "2024-01-01T00:00:00Z"
            }
        },
        {
            "ackId": "ack-id-2",
            "message": {
                "data": "eyJ0YXNrX2lkIjogIjEyNCIsICJzdGF0dXMiOiAiZmFpbGVkIn0=",
                "attributes": {
                    "type": "error_notification"
                },
                "messageId": "msg-2",
                "publishTime": "2024-01-01T00:01:00Z"
            }
        }
    ]
}

PUBSUB_ACKNOWLEDGE_RESPONSE = {}  # Empty response on success

PUBSUB_ERROR_DEADLINE_EXCEEDED = {
    "error": {
        "code": 504,
        "message": "Deadline exceeded",
        "status": "DEADLINE_EXCEEDED"
    }
}

PUBSUB_ERROR_NOT_FOUND = {
    "error": {
        "code": 404,
        "message": "Resource not found",
        "status": "NOT_FOUND"
    }
}


# Decoded Pub/Sub message payloads
PUBSUB_COMPLETION_PAYLOAD = {
    "task_id": "123",
    "status": "complete",
    "result": {
        "sections_processed": 5,
        "processing_time_ms": 2500
    }
}

PUBSUB_ERROR_PAYLOAD = {
    "task_id": "124",
    "status": "failed",
    "error": {
        "code": "PROCESSING_ERROR",
        "message": "Failed to process document section"
    }
}

PUBSUB_RETRY_PAYLOAD = {
    "task_id": "125",
    "status": "retry",
    "retry_count": 2,
    "max_retries": 3,
    "next_retry_at": "2024-01-01T00:05:00Z"
}


# Helper functions for creating mock responses
def create_gcs_blob_response(
    name: str,
    bucket: str = "test-bucket",
    size: int = 1024,
    content_type: str = "application/json"
) -> Dict[str, Any]:
    """
    Create a mock GCS blob response.
    
    Args:
        name: Blob name/path
        bucket: Bucket name
        size: Blob size in bytes
        content_type: Content type
        
    Returns:
        Mock blob response dictionary
    """
    return {
        "name": name,
        "bucket": bucket,
        "generation": "1234567890123456",
        "metageneration": "1",
        "contentType": content_type,
        "storageClass": "STANDARD",
        "size": str(size),
        "timeCreated": "2024-01-01T00:00:00Z",
        "updated": "2024-01-01T00:00:00Z"
    }


def create_pubsub_message(
    data: Dict[str, Any],
    attributes: Dict[str, str] = None,
    message_id: str = "test-msg-id"
) -> Dict[str, Any]:
    """
    Create a mock Pub/Sub message.
    
    Args:
        data: Message payload data
        attributes: Optional message attributes
        message_id: Message ID
        
    Returns:
        Mock Pub/Sub message dictionary
    """
    import base64
    import json
    
    encoded_data = base64.b64encode(json.dumps(data).encode()).decode()
    
    return {
        "data": encoded_data,
        "attributes": attributes or {},
        "messageId": message_id,
        "publishTime": "2024-01-01T00:00:00Z"
    }


def create_pubsub_pull_response(
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create a mock Pub/Sub pull response.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Mock pull response dictionary
    """
    received_messages = []
    for i, msg in enumerate(messages):
        received_messages.append({
            "ackId": f"ack-id-{i}",
            "message": msg
        })
    
    return {"receivedMessages": received_messages}


# LLM/LangChain Mock Responses
LLM_COMPLETION_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1704067200,
    "model": "gpt-4",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a mock LLM response for testing."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 100,
        "total_tokens": 150
    }
}

LLM_TOOL_CALL_RESPONSE = {
    "id": "chatcmpl-456",
    "object": "chat.completion",
    "created": 1704067200,
    "model": "gpt-4",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "process_section",
                            "arguments": '{"section_id": "1", "action": "analyze"}'
                        }
                    }
                ]
            },
            "finish_reason": "tool_calls"
        }
    ]
}

LLM_ERROR_RESPONSE = {
    "error": {
        "message": "Rate limit exceeded",
        "type": "rate_limit_error",
        "code": "rate_limit_exceeded"
    }
}

# CodeGraphBuilder Mock Responses
CODE_GRAPH_BUILD_RESULT = {
    "nodes": [
        {"id": "node-1", "type": "module", "name": "main.py"},
        {"id": "node-2", "type": "class", "name": "MyClass"},
        {"id": "node-3", "type": "function", "name": "my_function"}
    ],
    "edges": [
        {"from": "node-1", "to": "node-2", "type": "contains"},
        {"from": "node-2", "to": "node-3", "type": "defines"}
    ],
    "metadata": {
        "total_nodes": 3,
        "total_edges": 2,
        "build_time_ms": 500
    }
}
