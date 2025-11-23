"""
Interface for Google Cloud Secret Manager operations.

This module defines the abstract base class for Secret Manager repository implementations,
providing a standardized interface for secure storage and management of sensitive credentials
such as Figma Personal Access Tokens (PATs).

Security Pattern:
    All Figma PATs must be stored in Google Cloud Secret Manager, never in the application
    database. This ensures sensitive credentials are encrypted at rest and access is controlled
    through GCP IAM policies rather than application-level security.

Secret Naming Convention:
    All secrets must follow the pattern: 'figma-secret-<installation_id>'
    Example: 'figma-secret-42' for figma_installation with id=42
    
    This consistent naming pattern enables:
    - Easy correlation between database records and stored secrets
    - Automated secret lifecycle management
    - Simplified audit logging and access tracking

Transaction Consistency:
    All methods that modify secrets (create, update, delete) raise SecretManagerError
    on failure. This allows calling code to implement proper transaction rollback patterns,
    maintaining consistency between database state and Secret Manager state.
    
    Example Transaction Pattern:
        try:
            with db.transaction():
                installation = db.create_installation(...)
                secret_repo.create_secret(f"figma-secret-{installation.id}", pat)
                db.commit()
        except SecretManagerError:
            # Transaction automatically rolled back
            raise

Retry Logic:
    All write operations (create, update, delete) include configurable retry logic to handle
    transient failures such as network timeouts or temporary service unavailability. The
    default retry count is 3 attempts, with exponential backoff between attempts.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ISecretRepository(ABC):
    """
    Repository interface for Google Cloud Secret Manager operations.
    
    This abstract base class defines the contract for all Secret Manager interactions,
    enabling dependency injection and testability through fake implementations. Concrete
    implementations must handle Google Cloud Secret Manager SDK operations, including
    authentication, error handling, and retry logic.
    
    Purpose:
        - Abstracts external Secret Manager SDK dependencies
        - Enables testing with fake/mock implementations
        - Enforces consistent error handling and retry patterns
        - Maintains separation between business logic and infrastructure
        
    Implementation Requirements:
        Concrete implementations must:
        - Authenticate using Application Default Credentials (ADC)
        - Use GCP project ID from configuration
        - Implement exponential backoff for retries
        - Log all operations for audit purposes
        - Handle SecretManager-specific exceptions
        
    Thread Safety:
        Implementations should be thread-safe, as Secret Manager clients may be
        used across multiple concurrent requests in a web application context.
    """
    
    @abstractmethod
    def create_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Create a new secret in Google Cloud Secret Manager.
        
        This method creates both the secret resource and its initial version containing
        the provided secret value. The secret is created with automatic replication
        across all regions for high availability.
        
        Naming Pattern:
            Must follow pattern: 'figma-secret-<installation_id>'
            Example: create_secret('figma-secret-42', 'figd_AbC123...')
        
        Transaction Integration:
            This method is designed to work within database transactions. On failure,
            it raises SecretManagerError, allowing the calling code to rollback any
            database changes made prior to secret creation.
            
            Example:
                try:
                    with db.transaction():
                        installation = figma_repo.create_installation(user_id, name)
                        secret_repo.create_secret(
                            f'figma-secret-{installation.id}',
                            pat_value
                        )
                        db.commit()
                except SecretManagerError as e:
                    # Database transaction automatically rolled back
                    logger.error(f"Failed to store PAT: {e}")
                    raise APIError("Unable to complete installation creation")
        
        Retry Behavior:
            - Attempts operation up to retry_count times
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors (network timeout, 503 Service Unavailable)
            - Does not retry on permanent errors (permission denied, already exists)
            - Raises SecretManagerError only after all retries exhausted
        
        Error Scenarios:
            - Secret already exists: Raises SecretManagerError (not retried)
            - Permission denied: Raises SecretManagerError (not retried)
            - Network timeout: Retries up to retry_count times
            - Service unavailable: Retries up to retry_count times
            - Invalid secret name: Raises SecretManagerError (not retried)
        
        :param secret_name: Name of the secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: The sensitive value to store (e.g., Figma PAT)
        :type secret_value: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret created successfully
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name or secret_value is empty or invalid format
        """
        pass
    
    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve the latest version of a secret value from Google Cloud Secret Manager.
        
        This method accesses the most recent version of the secret and returns its
        decrypted payload. It does not perform retries as read operations are typically
        fast and transient failures are rare.
        
        Naming Pattern:
            Must use pattern: 'figma-secret-<installation_id>'
            Example: get_secret('figma-secret-42') returns the PAT for installation 42
        
        Security Considerations:
            - The returned secret value should be used immediately and not stored
            - Never log or expose the returned value in error messages
            - Consider the secret value as highly sensitive credential material
            - Ensure calling code validates PAT format before use
        
        Caching Guidance:
            This method does NOT cache results. If caching is needed for performance,
            implement it in a higher layer (e.g., service layer) with appropriate
            TTL and cache invalidation on secret updates.
        
        Version Selection:
            Always retrieves the latest enabled version. If the latest version is
            disabled or destroyed, returns None rather than attempting to retrieve
            previous versions.
        
        Use Cases:
            - Validating PAT status during installation retrieval
            - Accessing PAT for Figma API calls (frame validation)
            - Rotating credentials (retrieve old, compare with new)
            - Internal API endpoints providing PAT to authorized services
        
        Example Usage:
            pat = secret_repo.get_secret(f'figma-secret-{installation_id}')
            if pat is None:
                # Secret not found - installation may be deleted or corrupted
                raise InstallationNotFoundError(installation_id)
            
            # Use PAT immediately for Figma API call
            figma_api_repo.validate_pat(pat)
        
        Error Scenarios:
            - Secret does not exist: Returns None (not an error condition)
            - Permission denied: Raises SecretManagerError
            - Network error: Raises SecretManagerError (no retry for reads)
            - Secret version disabled: Returns None
            - Malformed secret name: Raises SecretManagerError
        
        :param secret_name: Name of the secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :return: Secret value (decrypted string) or None if secret not found
        :rtype: Optional[str]
        :raises SecretManagerError: On permission errors or unexpected Secret Manager failures
        :raises ValueError: If secret_name is empty or invalid format
        """
        pass
    
    @abstractmethod
    def update_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Update an existing secret by creating a new version with the provided value.
        
        This method does not modify existing versions. Instead, it creates a new version
        of the secret and marks it as the latest. Previous versions remain accessible
        through version-specific requests, supporting audit trails and rollback scenarios.
        
        Naming Pattern:
            Must use pattern: 'figma-secret-<installation_id>'
            Example: update_secret('figma-secret-42', 'figd_NewToken456...')
        
        Transaction Integration:
            Designed for use within database transactions, particularly during PAT rotation.
            On failure, raises SecretManagerError to trigger transaction rollback.
            
            Example PAT Rotation:
                try:
                    with db.transaction():
                        # Update installation timestamp
                        figma_repo.update_installation(
                            installation_id,
                            updated_at=datetime.utcnow()
                        )
                        # Store new PAT version
                        secret_repo.update_secret(
                            f'figma-secret-{installation_id}',
                            new_pat_value
                        )
                        db.commit()
                except SecretManagerError as e:
                    # Database timestamp update rolled back
                    logger.error(f"Failed to rotate PAT: {e}")
                    raise APIError("Unable to update Personal Access Token")
        
        Versioning Behavior:
            - Creates new version with incremented version number
            - Previous versions remain enabled and accessible
            - Latest version is automatically used by get_secret()
            - Old versions can be manually disabled or destroyed separately
            - Version history supports audit and compliance requirements
        
        Retry Behavior:
            - Attempts operation up to retry_count times
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors (network timeout, 503 Service Unavailable)
            - Does not retry on permanent errors (permission denied, not found)
            - Raises SecretManagerError only after all retries exhausted
        
        Validation:
            - Verifies secret exists before attempting update
            - Validates new secret value is non-empty
            - Does NOT validate PAT format (validation is service layer responsibility)
        
        Error Scenarios:
            - Secret does not exist: Raises SecretManagerError (not retried)
            - Permission denied: Raises SecretManagerError (not retried)
            - Network timeout: Retries up to retry_count times
            - Service unavailable: Retries up to retry_count times
            - Empty secret value: Raises ValueError (not retried)
        
        :param secret_name: Name of the secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: New secret value to store as latest version
        :type secret_value: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret version created successfully
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name or secret_value is empty or invalid format
        """
        pass
    
    @abstractmethod
    def delete_secret(
        self,
        secret_name: str,
        retry_count: int = 3
    ) -> bool:
        """
        Delete a secret and all its versions from Google Cloud Secret Manager.
        
        This is a destructive operation that permanently removes the secret resource
        and all associated versions. The operation cannot be undone. Deleted secrets
        may be recreated with the same name, but no historical data is retained.
        
        Naming Pattern:
            Must use pattern: 'figma-secret-<installation_id>'
            Example: delete_secret('figma-secret-42')
        
        Transaction Integration:
            Critical for maintaining consistency during installation deletion. Must be
            called within a transaction that also soft-deletes the installation record.
            On failure, raises SecretManagerError to trigger rollback.
            
            Example Installation Deletion:
                try:
                    with db.transaction():
                        # Soft delete installation record
                        figma_repo.soft_delete_installation(installation_id)
                        # Remove secret from Secret Manager
                        secret_repo.delete_secret(f'figma-secret-{installation_id}')
                        db.commit()
                except SecretManagerError as e:
                    # Installation soft-delete rolled back
                    logger.error(f"Failed to delete secret: {e}")
                    raise APIError("Unable to complete installation deletion")
        
        Consistency Requirements:
            This operation is critical for preventing orphaned secrets. If deletion fails:
            - Database changes MUST be rolled back
            - Do NOT leave installation marked as deleted with secret still present
            - Do NOT leave secret in Secret Manager without database reference
            - Automated cleanup processes may be needed for partial failures
        
        Retry Behavior:
            - Attempts operation up to retry_count times
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors (network timeout, 503 Service Unavailable)
            - Does not retry on permanent errors (permission denied)
            - Treats "not found" as success (idempotent deletion)
            - Raises SecretManagerError only after all retries exhausted
        
        Idempotency:
            This method is idempotent. If the secret does not exist, the method returns
            True (successful deletion) rather than raising an error. This allows for
            safe retry of deletion operations and cleanup of partial failures.
        
        Audit Logging:
            Implementations should log all deletion attempts, including:
            - Secret name being deleted
            - User or service account performing deletion
            - Timestamp of deletion
            - Success or failure status
            This supports compliance and security audit requirements.
        
        Error Scenarios:
            - Secret does not exist: Returns True (idempotent success)
            - Permission denied: Raises SecretManagerError (not retried)
            - Network timeout: Retries up to retry_count times
            - Service unavailable: Retries up to retry_count times
            - Secret has active leases: Waits for leases, then deletes
        
        :param secret_name: Name of the secret following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret deleted successfully or does not exist
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name is empty or invalid format
        """
        pass
