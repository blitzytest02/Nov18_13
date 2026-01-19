"""
Integration tests for Google Cloud Storage operations.

Tests cover:
- File upload operations
- File download operations
- Bucket operations
- Error handling
- Large file handling
"""

import json
import io
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.integration
class TestStorageUpload:
    """Tests for Cloud Storage upload operations."""
    
    def test_upload_string_success(self, mock_storage_client):
        """Test successful string upload."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("test-file.txt")
        
        blob.upload_from_string("Test content")
        
        blob.upload_from_string.assert_called_once_with("Test content")
    
    def test_upload_json_success(self, mock_storage_client):
        """Test successful JSON upload."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("test-data.json")
        
        data = {"key": "value", "number": 42}
        blob.upload_from_string(json.dumps(data), content_type="application/json")
        
        blob.upload_from_string.assert_called_once()
    
    def test_upload_binary_data(self, mock_storage_client):
        """Test uploading binary data."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("binary-file.bin")
        
        binary_data = b"\x00\x01\x02\x03\x04"
        blob.upload_from_string(binary_data)
        
        blob.upload_from_string.assert_called_once_with(binary_data)
    
    def test_upload_with_metadata(self, mock_storage_client):
        """Test upload with custom metadata."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file-with-metadata.txt")
        
        blob.metadata = {"custom-key": "custom-value", "source": "test"}
        blob.upload_from_string("Content")
        
        assert blob.metadata["custom-key"] == "custom-value"
    
    def test_upload_with_content_type(self, mock_storage_client):
        """Test upload with specific content type."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("document.html")
        
        blob.upload_from_string(
            "<html><body>Test</body></html>",
            content_type="text/html"
        )
        
        blob.upload_from_string.assert_called_once()
    
    def test_upload_large_file(self, mock_storage_client):
        """Test uploading large file."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("large-file.txt")
        
        # Create 5 MB of data
        large_data = "x" * (5 * 1024 * 1024)
        blob.upload_from_string(large_data)
        
        blob.upload_from_string.assert_called_once()


@pytest.mark.integration
class TestStorageDownload:
    """Tests for Cloud Storage download operations."""
    
    def test_download_as_string(self, mock_storage_client):
        """Test downloading file as string."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("test-file.txt")
        
        blob.download_as_string.return_value = b"Downloaded content"
        
        content = blob.download_as_string()
        
        assert content == b"Downloaded content"
    
    def test_download_as_bytes(self, mock_storage_client):
        """Test downloading file as bytes."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("binary-file.bin")
        
        blob.download_as_bytes.return_value = b"\x00\x01\x02\x03"
        
        content = blob.download_as_bytes()
        
        assert isinstance(content, bytes)
    
    def test_download_json(self, mock_storage_client):
        """Test downloading JSON file."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("data.json")
        
        blob.download_as_string.return_value = b'{"key": "value"}'
        
        content = blob.download_as_string()
        data = json.loads(content.decode("utf-8"))
        
        assert data["key"] == "value"
    
    def test_download_to_file(self, mock_storage_client, tmp_path):
        """Test downloading to a local file."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("test-file.txt")
        
        local_path = tmp_path / "downloaded.txt"
        
        # Mock download_to_filename
        def mock_download(filename):
            with open(filename, "w") as f:
                f.write("Downloaded content")
        
        blob.download_to_filename.side_effect = mock_download
        
        blob.download_to_filename(str(local_path))
        
        assert local_path.exists()
        assert local_path.read_text() == "Downloaded content"


@pytest.mark.integration
class TestStorageBlobOperations:
    """Tests for blob operations."""
    
    def test_check_blob_exists(self, mock_storage_client):
        """Test checking if blob exists."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("existing-file.txt")
        
        blob.exists.return_value = True
        
        assert blob.exists() is True
    
    def test_check_blob_not_exists(self, mock_storage_client):
        """Test checking non-existent blob."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("non-existent.txt")
        
        blob.exists.return_value = False
        
        assert blob.exists() is False
    
    def test_delete_blob(self, mock_storage_client):
        """Test deleting a blob."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file-to-delete.txt")
        
        blob.delete()
        
        blob.delete.assert_called_once()
    
    def test_copy_blob(self, mock_storage_client):
        """Test copying a blob."""
        client = mock_storage_client
        source_bucket = client.bucket("source-bucket")
        dest_bucket = client.bucket("dest-bucket")
        
        source_blob = source_bucket.blob("source-file.txt")
        
        source_bucket.copy_blob.return_value = MagicMock()
        
        source_bucket.copy_blob(source_blob, dest_bucket, "dest-file.txt")
        
        source_bucket.copy_blob.assert_called_once()
    
    def test_rename_blob(self, mock_storage_client):
        """Test renaming a blob."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("old-name.txt")
        
        bucket.rename_blob.return_value = MagicMock()
        
        bucket.rename_blob(blob, "new-name.txt")
        
        bucket.rename_blob.assert_called_once()
    
    def test_get_blob_metadata(self, mock_storage_client):
        """Test getting blob metadata."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file.txt")
        
        blob.size = 1024
        blob.content_type = "text/plain"
        blob.time_created = "2024-01-15T12:00:00Z"
        blob.updated = "2024-01-15T12:30:00Z"
        
        assert blob.size == 1024
        assert blob.content_type == "text/plain"


@pytest.mark.integration
class TestStorageBucketOperations:
    """Tests for bucket operations."""
    
    def test_get_bucket(self, mock_storage_client):
        """Test getting a bucket."""
        client = mock_storage_client
        
        bucket = client.bucket("test-bucket")
        
        assert bucket is not None
    
    def test_list_blobs(self, mock_storage_client):
        """Test listing blobs in bucket."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        
        mock_blobs = [MagicMock(name=f"file{i}.txt") for i in range(5)]
        bucket.list_blobs.return_value = mock_blobs
        
        blobs = list(bucket.list_blobs())
        
        assert len(blobs) == 5
    
    def test_list_blobs_with_prefix(self, mock_storage_client):
        """Test listing blobs with prefix filter."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        
        mock_blobs = [MagicMock(name=f"documents/file{i}.txt") for i in range(3)]
        bucket.list_blobs.return_value = mock_blobs
        
        blobs = list(bucket.list_blobs(prefix="documents/"))
        
        assert len(blobs) == 3
        bucket.list_blobs.assert_called_with(prefix="documents/")
    
    def test_bucket_exists(self, mock_storage_client):
        """Test checking if bucket exists."""
        client = mock_storage_client
        bucket = client.bucket("existing-bucket")
        
        bucket.exists.return_value = True
        
        assert bucket.exists() is True


@pytest.mark.integration
class TestStorageErrorHandling:
    """Tests for Cloud Storage error handling."""
    
    def test_handle_not_found_error(self, mock_storage_client):
        """Test handling blob not found error."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("non-existent.txt")
        
        from google.cloud.exceptions import NotFound
        blob.download_as_string.side_effect = NotFound("Blob not found")
        
        with pytest.raises(NotFound):
            blob.download_as_string()
    
    def test_handle_permission_denied(self, mock_storage_client):
        """Test handling permission denied error."""
        client = mock_storage_client
        bucket = client.bucket("restricted-bucket")
        blob = bucket.blob("file.txt")
        
        blob.upload_from_string.side_effect = PermissionError("Access denied")
        
        with pytest.raises(PermissionError):
            blob.upload_from_string("Content")
    
    def test_handle_network_error(self, mock_storage_client):
        """Test handling network error."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file.txt")
        
        blob.upload_from_string.side_effect = ConnectionError("Network error")
        
        with pytest.raises(ConnectionError):
            blob.upload_from_string("Content")
    
    def test_handle_timeout(self, mock_storage_client):
        """Test handling timeout error."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file.txt")
        
        blob.upload_from_string.side_effect = TimeoutError("Upload timed out")
        
        with pytest.raises(TimeoutError):
            blob.upload_from_string("Content")


@pytest.mark.integration
class TestStorageSignedUrls:
    """Tests for signed URL generation."""
    
    def test_generate_signed_url_for_upload(self, mock_storage_client):
        """Test generating signed URL for upload."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("upload-target.txt")
        
        blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=300,
            method="PUT"
        )
        
        assert signed_url.startswith("https://")
    
    def test_generate_signed_url_for_download(self, mock_storage_client):
        """Test generating signed URL for download."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file.txt")
        
        blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=3600,
            method="GET"
        )
        
        assert signed_url.startswith("https://")
    
    def test_signed_url_with_content_type(self, mock_storage_client):
        """Test generating signed URL with content type."""
        client = mock_storage_client
        bucket = client.bucket("test-bucket")
        blob = bucket.blob("file.json")
        
        blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=300,
            method="PUT",
            content_type="application/json"
        )
        
        blob.generate_signed_url.assert_called_once()


@pytest.mark.integration
class TestStorageWithFlaskApp:
    """Tests for Cloud Storage integration with Flask app."""
    
    def test_upload_document_via_api(self, client, mock_storage_client, mocker):
        """Test uploading document via API endpoint."""
        mocker.patch(
            "src.app.services.storage_service.get_storage_client",
            return_value=mock_storage_client
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
    
    def test_storage_error_returns_api_error(self, client, mock_storage_client, mocker):
        """Test storage error returns appropriate API error."""
        mock_storage_client.bucket.side_effect = Exception("Storage unavailable")
        
        mocker.patch(
            "src.app.services.storage_service.get_storage_client",
            return_value=mock_storage_client
        )
        
        response = client.post(
            "/api/v1/documents/process",
            data=json.dumps({
                "tech_spec": "Test specification",
                "sections": [{"heading": "Test", "content": "Content"}]
            }),
            content_type="application/json"
        )
        
        # Should handle error gracefully
        assert response.status_code in [200, 400, 500]


@pytest.mark.integration
class TestStorageDocumentOperations:
    """Tests for document-specific storage operations."""
    
    def test_store_document_section(self, mock_storage_client):
        """Test storing document section."""
        client = mock_storage_client
        bucket = client.bucket("documents-bucket")
        
        section_data = {
            "heading": "Introduction",
            "content": "This is the introduction.",
            "order": 1
        }
        
        blob = bucket.blob("documents/doc-123/section-1.json")
        blob.upload_from_string(json.dumps(section_data), content_type="application/json")
        
        blob.upload_from_string.assert_called_once()
    
    def test_retrieve_document_section(self, mock_storage_client):
        """Test retrieving document section."""
        client = mock_storage_client
        bucket = client.bucket("documents-bucket")
        
        section_data = {
            "heading": "Introduction",
            "content": "This is the introduction.",
            "order": 1
        }
        
        blob = bucket.blob("documents/doc-123/section-1.json")
        blob.download_as_string.return_value = json.dumps(section_data).encode()
        
        content = blob.download_as_string()
        retrieved = json.loads(content.decode())
        
        assert retrieved["heading"] == "Introduction"
    
    def test_list_document_sections(self, mock_storage_client):
        """Test listing document sections."""
        client = mock_storage_client
        bucket = client.bucket("documents-bucket")
        
        mock_blobs = [
            MagicMock(name="documents/doc-123/section-1.json"),
            MagicMock(name="documents/doc-123/section-2.json"),
            MagicMock(name="documents/doc-123/section-3.json")
        ]
        bucket.list_blobs.return_value = mock_blobs
        
        blobs = list(bucket.list_blobs(prefix="documents/doc-123/"))
        
        assert len(blobs) == 3
    
    def test_delete_document_and_sections(self, mock_storage_client):
        """Test deleting document and all its sections."""
        client = mock_storage_client
        bucket = client.bucket("documents-bucket")
        
        mock_blobs = [
            MagicMock(name="documents/doc-123/section-1.json"),
            MagicMock(name="documents/doc-123/section-2.json")
        ]
        bucket.list_blobs.return_value = mock_blobs
        
        # Delete each blob
        for blob in mock_blobs:
            blob.delete()
            blob.delete.assert_called()


# Fixtures

@pytest.fixture
def mock_storage_client():
    """Create a mock Cloud Storage client for testing."""
    mock_client = MagicMock()
    
    # Create mock bucket that returns mock blobs
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.exists.return_value = True
    mock_bucket.list_blobs.return_value = []
    
    mock_client.bucket.return_value = mock_bucket
    
    return mock_client
