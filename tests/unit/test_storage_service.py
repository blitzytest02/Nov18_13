"""
Unit tests for the Storage service module.

Tests cover:
- StorageService initialization
- Blob upload operations
- Blob download operations
- Blob management operations
- Document-specific storage operations
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Any, Dict


class TestStorageServiceInit:
    """Tests for StorageService initialization."""
    
    def test_init_with_project_id(self):
        """Test StorageService initializes with project ID."""
        from src.app.services.storage_service import StorageService
        
        service = StorageService(project_id="test-project")
        
        assert service.project_id == "test-project"
        assert service.default_bucket_name is None
        assert service._client is None
    
    def test_init_with_bucket_name(self):
        """Test StorageService accepts default bucket name."""
        from src.app.services.storage_service import StorageService
        
        service = StorageService(
            project_id="test-project",
            default_bucket_name="test-bucket"
        )
        
        assert service.default_bucket_name == "test-bucket"
    
    def test_init_with_custom_client(self):
        """Test StorageService accepts pre-configured client."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        assert service._client is mock_client


class TestStorageServiceBucket:
    """Tests for bucket operations."""
    
    def test_get_bucket_with_name(self):
        """Test getting a bucket by name."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        bucket = service.get_bucket("my-bucket")
        
        assert bucket is mock_bucket
        mock_client.bucket.assert_called_once_with("my-bucket")
    
    def test_get_bucket_uses_default(self):
        """Test get_bucket uses default bucket name."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        
        service = StorageService(
            project_id="test-project",
            default_bucket_name="default-bucket",
            client=mock_client
        )
        
        bucket = service.get_bucket()
        
        mock_client.bucket.assert_called_once_with("default-bucket")
    
    def test_get_bucket_raises_without_name(self):
        """Test get_bucket raises when no bucket name provided."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        with pytest.raises(ValueError, match="Bucket name must be provided"):
            service.get_bucket()
    
    def test_get_bucket_raises_without_client(self, mocker):
        """Test get_bucket raises when no client available."""
        from src.app.services.storage_service import StorageService
        
        # Patch STORAGE_AVAILABLE to False to prevent real client creation
        mocker.patch('src.app.services.storage_service.STORAGE_AVAILABLE', False)
        
        service = StorageService(
            project_id="test-project",
            default_bucket_name="bucket"
        )
        
        with pytest.raises(RuntimeError, match="Storage client not available"):
            service.get_bucket()


class TestStorageServiceUpload:
    """Tests for upload operations."""
    
    def test_upload_string_success(self):
        """Test uploading string content."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.upload_string(
            content="Hello, World!",
            blob_name="test.txt",
            bucket_name="test-bucket"
        )
        
        assert result == "gs://test-bucket/test.txt"
        mock_blob.upload_from_string.assert_called_once_with(
            "Hello, World!",
            content_type="text/plain"
        )
    
    def test_upload_string_with_metadata(self):
        """Test uploading string with metadata."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        service.upload_string(
            content="Data",
            blob_name="data.txt",
            bucket_name="test-bucket",
            metadata={"key": "value"}
        )
        
        assert mock_blob.metadata == {"key": "value"}
    
    def test_upload_json_success(self):
        """Test uploading JSON data."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        data = {"name": "test", "value": 123}
        result = service.upload_json(
            data=data,
            blob_name="data.json",
            bucket_name="test-bucket"
        )
        
        assert result == "gs://test-bucket/data.json"
        call_args = mock_blob.upload_from_string.call_args
        uploaded_content = call_args[0][0]
        assert json.loads(uploaded_content) == data
        assert call_args[1]["content_type"] == "application/json"
    
    def test_upload_file_success(self):
        """Test uploading a file."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.upload_file(
            local_path="/path/to/file.txt",
            blob_name="file.txt",
            bucket_name="test-bucket"
        )
        
        assert result == "gs://test-bucket/file.txt"
        mock_blob.upload_from_filename.assert_called_once_with(
            "/path/to/file.txt",
            content_type=None
        )


class TestStorageServiceDownload:
    """Tests for download operations."""
    
    def test_download_string_success(self):
        """Test downloading blob as string."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_blob.download_as_string.return_value = b"Hello, World!"
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.download_string(
            blob_name="test.txt",
            bucket_name="test-bucket"
        )
        
        assert result == "Hello, World!"
    
    def test_download_bytes_success(self):
        """Test downloading blob as bytes."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"\x00\x01\x02"
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.download_bytes(
            blob_name="binary.dat",
            bucket_name="test-bucket"
        )
        
        assert result == b"\x00\x01\x02"
    
    def test_download_json_success(self):
        """Test downloading and parsing JSON blob."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_blob.download_as_string.return_value = b'{"key": "value"}'
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.download_json(
            blob_name="data.json",
            bucket_name="test-bucket"
        )
        
        assert result == {"key": "value"}
    
    def test_download_to_file_success(self):
        """Test downloading blob to local file."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        service.download_to_file(
            blob_name="file.txt",
            local_path="/local/path/file.txt",
            bucket_name="test-bucket"
        )
        
        mock_blob.download_to_filename.assert_called_once_with("/local/path/file.txt")


class TestStorageServiceBlobOperations:
    """Tests for blob management operations."""
    
    def test_blob_exists_true(self):
        """Test checking if blob exists (returns True)."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.blob_exists(
            blob_name="existing.txt",
            bucket_name="test-bucket"
        )
        
        assert result is True
    
    def test_blob_exists_false(self):
        """Test checking if blob exists (returns False)."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.blob_exists(
            blob_name="nonexistent.txt",
            bucket_name="test-bucket"
        )
        
        assert result is False
    
    def test_delete_blob_success(self):
        """Test deleting a blob."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.delete_blob(
            blob_name="to-delete.txt",
            bucket_name="test-bucket"
        )
        
        assert result is True
        mock_blob.delete.assert_called_once()
    
    def test_delete_blob_failure(self):
        """Test deleting a blob that fails."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_blob.delete.side_effect = Exception("Delete failed")
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.delete_blob(
            blob_name="to-delete.txt",
            bucket_name="test-bucket"
        )
        
        assert result is False
    
    def test_list_blobs_success(self):
        """Test listing blobs in bucket."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        
        # Create mock blobs with proper name attributes
        mock_blob1 = MagicMock()
        mock_blob1.name = "file1.txt"
        mock_blob2 = MagicMock()
        mock_blob2.name = "file2.txt"
        mock_blob3 = MagicMock()
        mock_blob3.name = "subdir/file3.txt"
        
        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]
        mock_client.bucket.return_value = mock_bucket
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.list_blobs(bucket_name="test-bucket")
        
        assert result == ["file1.txt", "file2.txt", "subdir/file3.txt"]
    
    def test_list_blobs_with_prefix(self):
        """Test listing blobs with prefix filter."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blobs = [
            MagicMock(name="prefix/file1.txt"),
            MagicMock(name="prefix/file2.txt")
        ]
        mock_bucket.list_blobs.return_value = mock_blobs
        mock_client.bucket.return_value = mock_bucket
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.list_blobs(
            prefix="prefix/",
            bucket_name="test-bucket"
        )
        
        mock_bucket.list_blobs.assert_called_once_with(
            prefix="prefix/",
            max_results=None
        )
        assert len(result) == 2
    
    def test_copy_blob_success(self):
        """Test copying a blob."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "test-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.copy_blob(
            source_blob_name="source.txt",
            dest_blob_name="dest.txt",
            source_bucket_name="test-bucket"
        )
        
        assert result == "gs://test-bucket/dest.txt"
        mock_bucket.copy_blob.assert_called_once()
    
    def test_get_blob_metadata_success(self):
        """Test getting blob metadata."""
        from src.app.services.storage_service import StorageService
        from datetime import datetime
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.name = "test.txt"
        mock_blob.size = 1024
        mock_blob.content_type = "text/plain"
        mock_blob.time_created = datetime(2024, 1, 1, 12, 0, 0)
        mock_blob.updated = datetime(2024, 1, 2, 12, 0, 0)
        mock_blob.metadata = {"custom": "value"}
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.get_blob_metadata(
            blob_name="test.txt",
            bucket_name="test-bucket"
        )
        
        assert result["name"] == "test.txt"
        assert result["size"] == 1024
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {"custom": "value"}
    
    def test_generate_signed_url(self):
        """Test generating signed URL."""
        from src.app.services.storage_service import StorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = StorageService(
            project_id="test-project",
            client=mock_client
        )
        
        result = service.generate_signed_url(
            blob_name="file.txt",
            expiration=3600,
            bucket_name="test-bucket"
        )
        
        assert result == "https://signed-url.example.com"
        mock_blob.generate_signed_url.assert_called_once()


class TestDocumentStorageService:
    """Tests for DocumentStorageService."""
    
    def test_init(self):
        """Test DocumentStorageService initialization."""
        from src.app.services.storage_service import DocumentStorageService
        
        service = DocumentStorageService(
            project_id="test-project",
            documents_bucket="docs-bucket"
        )
        
        assert service.project_id == "test-project"
        assert service.default_bucket_name == "docs-bucket"
    
    def test_store_document_section(self):
        """Test storing a document section."""
        from src.app.services.storage_service import DocumentStorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "docs-bucket"
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = DocumentStorageService(
            project_id="test-project",
            documents_bucket="docs-bucket",
            client=mock_client
        )
        
        section_data = {"heading": "Test", "content": "Content"}
        result = service.store_document_section(
            document_id="doc-123",
            section_id="section-1",
            section_data=section_data
        )
        
        assert result == "gs://docs-bucket/documents/doc-123/section-1.json"
    
    def test_retrieve_document_section(self):
        """Test retrieving a document section."""
        from src.app.services.storage_service import DocumentStorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_string.return_value = b'{"heading": "Test", "content": "Content"}'
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        service = DocumentStorageService(
            project_id="test-project",
            documents_bucket="docs-bucket",
            client=mock_client
        )
        
        result = service.retrieve_document_section(
            document_id="doc-123",
            section_id="section-1"
        )
        
        assert result == {"heading": "Test", "content": "Content"}
    
    def test_list_document_sections(self):
        """Test listing document sections."""
        from src.app.services.storage_service import DocumentStorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blobs = [
            MagicMock(name="documents/doc-123/section-1.json"),
            MagicMock(name="documents/doc-123/section-2.json")
        ]
        mock_bucket.list_blobs.return_value = mock_blobs
        mock_client.bucket.return_value = mock_bucket
        
        service = DocumentStorageService(
            project_id="test-project",
            documents_bucket="docs-bucket",
            client=mock_client
        )
        
        result = service.list_document_sections(document_id="doc-123")
        
        assert len(result) == 2
        mock_bucket.list_blobs.assert_called_once_with(
            prefix="documents/doc-123/",
            max_results=None
        )
    
    def test_delete_document(self):
        """Test deleting a document and its sections."""
        from src.app.services.storage_service import DocumentStorageService
        
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.name = "docs-bucket"
        mock_blobs = [
            MagicMock(name="documents/doc-123/section-1.json"),
            MagicMock(name="documents/doc-123/section-2.json"),
            MagicMock(name="documents/doc-123/section-3.json")
        ]
        mock_bucket.list_blobs.return_value = mock_blobs
        mock_client.bucket.return_value = mock_bucket
        
        service = DocumentStorageService(
            project_id="test-project",
            documents_bucket="docs-bucket",
            client=mock_client
        )
        
        result = service.delete_document(document_id="doc-123")
        
        assert result == 3


class TestStorageServiceHelpers:
    """Tests for helper functions."""
    
    def test_get_storage_service(self):
        """Test getting global storage service instance."""
        from src.app.services.storage_service import get_storage_service
        import src.app.services.storage_service as storage_module
        
        # Reset global state
        storage_module._storage_service = None
        
        service = get_storage_service(
            project_id="test-project",
            bucket_name="test-bucket"
        )
        
        assert service is not None
        assert service.project_id == "test-project"
        assert service.default_bucket_name == "test-bucket"
        
        # Should return same instance
        service2 = get_storage_service()
        assert service is service2
        
        # Cleanup
        storage_module._storage_service = None
    
    def test_get_document_storage_service(self):
        """Test getting document storage service instance."""
        from src.app.services.storage_service import get_document_storage_service
        import src.app.services.storage_service as storage_module
        
        # Reset global state
        storage_module._document_storage_service = None
        
        service = get_document_storage_service(
            project_id="test-project",
            documents_bucket="docs-bucket"
        )
        
        assert service is not None
        assert service.project_id == "test-project"
        
        # Cleanup
        storage_module._document_storage_service = None
    
    def test_get_storage_client(self):
        """Test getting storage client."""
        from src.app.services.storage_service import get_storage_client, get_storage_service
        import src.app.services.storage_service as storage_module
        
        # Reset global state
        storage_module._storage_service = None
        
        mock_client = MagicMock()
        service = storage_module.StorageService(
            project_id="test",
            client=mock_client
        )
        storage_module._storage_service = service
        
        client = get_storage_client()
        
        assert client is mock_client
        
        # Cleanup
        storage_module._storage_service = None
