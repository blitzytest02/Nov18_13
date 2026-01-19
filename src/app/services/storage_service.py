"""
Google Cloud Storage service for the reverse document generator.

This module provides functionality for uploading, downloading, and
managing files in Google Cloud Storage.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

logger = logging.getLogger(__name__)

# Optional import for Google Cloud Storage
try:
    from google.cloud import storage
    from google.cloud.storage import Blob, Bucket
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    storage = None
    Blob = None
    Bucket = None


class StorageService:
    """
    Service class for Google Cloud Storage operations.
    
    This class provides methods for uploading, downloading, and
    managing files in Cloud Storage buckets.
    
    Attributes:
        project_id: Google Cloud project ID
        default_bucket_name: Default bucket name for operations
        client: Cloud Storage client
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        default_bucket_name: Optional[str] = None,
        client: Optional[Any] = None
    ):
        """
        Initialize the Storage service.
        
        Args:
            project_id: Google Cloud project ID
            default_bucket_name: Default bucket name
            client: Optional pre-configured storage client
        """
        self.project_id = project_id
        self.default_bucket_name = default_bucket_name
        self._client = client
    
    @property
    def client(self) -> Any:
        """
        Get or create the Cloud Storage client.
        
        Returns:
            Storage client instance
        """
        if self._client is None and STORAGE_AVAILABLE:
            self._client = storage.Client(project=self.project_id)
        return self._client
    
    def get_bucket(self, bucket_name: Optional[str] = None) -> Any:
        """
        Get a bucket reference.
        
        Args:
            bucket_name: Bucket name (uses default if not provided)
            
        Returns:
            Bucket object
            
        Raises:
            ValueError: If no bucket name provided and no default set
        """
        bucket_name = bucket_name or self.default_bucket_name
        
        if not bucket_name:
            raise ValueError("Bucket name must be provided")
        
        if not self.client:
            raise RuntimeError("Storage client not available")
        
        return self.client.bucket(bucket_name)
    
    def upload_string(
        self,
        content: Union[str, bytes],
        blob_name: str,
        bucket_name: Optional[str] = None,
        content_type: str = "text/plain",
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload string content to Cloud Storage.
        
        Args:
            content: Content to upload
            blob_name: Destination blob name
            bucket_name: Target bucket name
            content_type: Content MIME type
            metadata: Optional custom metadata
            
        Returns:
            Public URL of the uploaded blob
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if metadata:
            blob.metadata = metadata
        
        blob.upload_from_string(content, content_type=content_type)
        
        logger.info(f"Uploaded {blob_name} to {bucket.name}")
        
        return f"gs://{bucket.name}/{blob_name}"
    
    def upload_json(
        self,
        data: Any,
        blob_name: str,
        bucket_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload JSON data to Cloud Storage.
        
        Args:
            data: Data to serialize as JSON
            blob_name: Destination blob name
            bucket_name: Target bucket name
            metadata: Optional custom metadata
            
        Returns:
            Public URL of the uploaded blob
        """
        content = json.dumps(data, ensure_ascii=False, indent=2)
        
        return self.upload_string(
            content=content,
            blob_name=blob_name,
            bucket_name=bucket_name,
            content_type="application/json",
            metadata=metadata
        )
    
    def download_string(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> str:
        """
        Download a blob as a string.
        
        Args:
            blob_name: Source blob name
            bucket_name: Source bucket name
            
        Returns:
            Blob content as string
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        content = blob.download_as_string()
        
        logger.info(f"Downloaded {blob_name} from {bucket.name}")
        
        return content.decode("utf-8")
    
    def download_bytes(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> bytes:
        """
        Download a blob as bytes.
        
        Args:
            blob_name: Source blob name
            bucket_name: Source bucket name
            
        Returns:
            Blob content as bytes
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        content = blob.download_as_bytes()
        
        logger.info(f"Downloaded {blob_name} from {bucket.name}")
        
        return content
    
    def download_json(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> Any:
        """
        Download and parse a JSON blob.
        
        Args:
            blob_name: Source blob name
            bucket_name: Source bucket name
            
        Returns:
            Parsed JSON data
        """
        content = self.download_string(blob_name, bucket_name)
        return json.loads(content)
    
    def download_to_file(
        self,
        blob_name: str,
        local_path: str,
        bucket_name: Optional[str] = None
    ) -> None:
        """
        Download a blob to a local file.
        
        Args:
            blob_name: Source blob name
            local_path: Local file path
            bucket_name: Source bucket name
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        blob.download_to_filename(local_path)
        
        logger.info(f"Downloaded {blob_name} to {local_path}")
    
    def upload_file(
        self,
        local_path: str,
        blob_name: str,
        bucket_name: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a local file to Cloud Storage.
        
        Args:
            local_path: Local file path
            blob_name: Destination blob name
            bucket_name: Target bucket name
            content_type: Optional content type
            
        Returns:
            GCS URL of the uploaded blob
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        blob.upload_from_filename(local_path, content_type=content_type)
        
        logger.info(f"Uploaded {local_path} to {bucket.name}/{blob_name}")
        
        return f"gs://{bucket.name}/{blob_name}"
    
    def blob_exists(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """
        Check if a blob exists.
        
        Args:
            blob_name: Blob name to check
            bucket_name: Bucket name
            
        Returns:
            True if blob exists, False otherwise
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        return blob.exists()
    
    def delete_blob(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> bool:
        """
        Delete a blob from Cloud Storage.
        
        Args:
            blob_name: Blob name to delete
            bucket_name: Bucket name
            
        Returns:
            True if deleted successfully
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        try:
            blob.delete()
            logger.info(f"Deleted {blob_name} from {bucket.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {blob_name}: {e}")
            return False
    
    def list_blobs(
        self,
        prefix: Optional[str] = None,
        bucket_name: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[str]:
        """
        List blobs in a bucket.
        
        Args:
            prefix: Optional prefix filter
            bucket_name: Bucket name
            max_results: Maximum number of results
            
        Returns:
            List of blob names
        """
        bucket = self.get_bucket(bucket_name)
        
        blobs = bucket.list_blobs(prefix=prefix, max_results=max_results)
        
        return [blob.name for blob in blobs]
    
    def copy_blob(
        self,
        source_blob_name: str,
        dest_blob_name: str,
        source_bucket_name: Optional[str] = None,
        dest_bucket_name: Optional[str] = None
    ) -> str:
        """
        Copy a blob to a new location.
        
        Args:
            source_blob_name: Source blob name
            dest_blob_name: Destination blob name
            source_bucket_name: Source bucket name
            dest_bucket_name: Destination bucket name
            
        Returns:
            GCS URL of the copied blob
        """
        source_bucket = self.get_bucket(source_bucket_name)
        dest_bucket = self.get_bucket(dest_bucket_name or source_bucket_name)
        
        source_blob = source_bucket.blob(source_blob_name)
        
        source_bucket.copy_blob(source_blob, dest_bucket, dest_blob_name)
        
        logger.info(
            f"Copied {source_blob_name} to {dest_bucket.name}/{dest_blob_name}"
        )
        
        return f"gs://{dest_bucket.name}/{dest_blob_name}"
    
    def get_blob_metadata(
        self,
        blob_name: str,
        bucket_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get metadata for a blob.
        
        Args:
            blob_name: Blob name
            bucket_name: Bucket name
            
        Returns:
            Dictionary of blob metadata
        """
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Fetch blob properties
        blob.reload()
        
        return {
            "name": blob.name,
            "size": blob.size,
            "content_type": blob.content_type,
            "created": blob.time_created,
            "updated": blob.updated,
            "metadata": blob.metadata or {}
        }
    
    def generate_signed_url(
        self,
        blob_name: str,
        expiration: int = 3600,
        method: str = "GET",
        bucket_name: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Generate a signed URL for a blob.
        
        Args:
            blob_name: Blob name
            expiration: URL expiration in seconds
            method: HTTP method (GET, PUT, etc.)
            bucket_name: Bucket name
            content_type: Content type for upload URLs
            
        Returns:
            Signed URL string
        """
        from datetime import timedelta
        
        bucket = self.get_bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        kwargs = {
            "version": "v4",
            "expiration": timedelta(seconds=expiration),
            "method": method
        }
        
        if content_type:
            kwargs["content_type"] = content_type
        
        return blob.generate_signed_url(**kwargs)


# Document section storage operations
class DocumentStorageService(StorageService):
    """
    Specialized storage service for document operations.
    
    This class extends StorageService with document-specific
    methods for managing document sections in Cloud Storage.
    """
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        documents_bucket: Optional[str] = None,
        client: Optional[Any] = None
    ):
        """
        Initialize the document storage service.
        
        Args:
            project_id: Google Cloud project ID
            documents_bucket: Bucket for document storage
            client: Optional pre-configured storage client
        """
        super().__init__(
            project_id=project_id,
            default_bucket_name=documents_bucket,
            client=client
        )
    
    def store_document_section(
        self,
        document_id: str,
        section_id: str,
        section_data: Dict[str, Any]
    ) -> str:
        """
        Store a document section.
        
        Args:
            document_id: Document identifier
            section_id: Section identifier
            section_data: Section data to store
            
        Returns:
            GCS URL of stored section
        """
        blob_name = f"documents/{document_id}/{section_id}.json"
        
        return self.upload_json(
            data=section_data,
            blob_name=blob_name,
            metadata={
                "document_id": document_id,
                "section_id": section_id
            }
        )
    
    def retrieve_document_section(
        self,
        document_id: str,
        section_id: str
    ) -> Dict[str, Any]:
        """
        Retrieve a document section.
        
        Args:
            document_id: Document identifier
            section_id: Section identifier
            
        Returns:
            Section data dictionary
        """
        blob_name = f"documents/{document_id}/{section_id}.json"
        
        return self.download_json(blob_name)
    
    def list_document_sections(
        self,
        document_id: str
    ) -> List[str]:
        """
        List all sections for a document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            List of section blob names
        """
        prefix = f"documents/{document_id}/"
        
        return self.list_blobs(prefix=prefix)
    
    def delete_document(self, document_id: str) -> int:
        """
        Delete a document and all its sections.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Number of blobs deleted
        """
        blobs = self.list_document_sections(document_id)
        deleted_count = 0
        
        for blob_name in blobs:
            if self.delete_blob(blob_name):
                deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} blobs for document {document_id}")
        
        return deleted_count


# Global service instance
_storage_service: Optional[StorageService] = None
_document_storage_service: Optional[DocumentStorageService] = None


def get_storage_service(
    project_id: Optional[str] = None,
    bucket_name: Optional[str] = None
) -> StorageService:
    """
    Get or create the global Storage service instance.
    
    Args:
        project_id: Optional Google Cloud project ID
        bucket_name: Optional default bucket name
        
    Returns:
        StorageService instance
    """
    global _storage_service
    
    if _storage_service is None:
        _storage_service = StorageService(
            project_id=project_id,
            default_bucket_name=bucket_name
        )
    
    return _storage_service


def get_document_storage_service(
    project_id: Optional[str] = None,
    documents_bucket: Optional[str] = None
) -> DocumentStorageService:
    """
    Get or create the document storage service instance.
    
    Args:
        project_id: Optional Google Cloud project ID
        documents_bucket: Optional documents bucket name
        
    Returns:
        DocumentStorageService instance
    """
    global _document_storage_service
    
    if _document_storage_service is None:
        _document_storage_service = DocumentStorageService(
            project_id=project_id,
            documents_bucket=documents_bucket
        )
    
    return _document_storage_service


def get_storage_client() -> Any:
    """
    Get the Cloud Storage client.
    
    Returns:
        Storage client or None if not available
    """
    service = get_storage_service()
    return service.client
