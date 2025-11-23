"""
Concrete implementation of ISecretRepository for Google Cloud Secret Manager operations.

This module provides the SecretRepository class that implements secure storage and
management of Figma Personal Access Tokens (PATs) in Google Cloud Secret Manager.
All PAT storage operations use the naming pattern 'figma-secret-<installation_id>'
and include retry logic with exponential backoff to handle transient failures.

Security Rationale:
    Figma PATs are highly sensitive credentials that grant full access to a user's
    Figma resources. Storing these tokens in Google Secret Manager instead of the
    application database provides several critical security benefits:

    1. Encryption at Rest: Secret Manager encrypts all secret values using Google-managed
       or customer-managed encryption keys (CMEK), providing defense in depth

    2. Access Control: IAM policies control access to secrets independently from
       database access controls, enabling principle of least privilege

    3. Audit Logging: All secret access is logged in Cloud Audit Logs, providing
       comprehensive audit trails for compliance and security monitoring

    4. Automatic Rotation: Secret Manager supports versioning, enabling PAT rotation
       without loss of historical versions for rollback scenarios

    5. Separation of Concerns: Database breaches do not expose PAT values, requiring
       separate compromise of Secret Manager to access sensitive credentials

Transaction Consistency Pattern:
    This implementation is designed to work within database transactions to maintain
    consistency between the figma_installation table and Secret Manager. All write
    operations (create, update, delete) raise SecretManagerError on failure, allowing
    the calling service layer to rollback database changes.

    Example Transaction Pattern:
        try:
            with db.transaction():
                installation = figma_repo.create_installation(user_id, name)
                secret_repo.create_secret(f'figma-secret-{installation.id}', pat)
                db.commit()
        except SecretManagerError as e:
            # Database transaction automatically rolled back
            # No orphaned database record exists without corresponding secret
            logger.error(f"Failed to store PAT: {e}")
            raise

Retry Logic:
    All write operations implement exponential backoff retry logic to handle transient
    failures such as network timeouts or temporary service unavailability. The default
    retry count is 3 attempts with delays of 1s, 2s, 4s between attempts. Permanent
    errors (permission denied, already exists, not found) are not retried.

Application Default Credentials:
    This implementation uses Google Cloud Application Default Credentials (ADC) for
    authentication. No explicit credentials are passed in code. The credentials are
    automatically discovered from:
    - Local development: gcloud auth application-default login
    - Production: Service account attached to compute resources
    - Testing: Explicit GOOGLE_APPLICATION_CREDENTIALS environment variable

Per section 0.3 Key Discovery 6: This approach follows Google Cloud best practices
and eliminates the need for explicit credential management in application code.
"""

import logging
import time
from typing import Optional

from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions

from .interfaces.i_secret_repository import ISecretRepository
from .interfaces.i_config_repository import IConfigRepository


# Module-level logger for Secret Manager operations
logger = logging.getLogger(__name__)


class SecretManagerError(Exception):
    """
    Custom exception for Google Cloud Secret Manager operation failures.

    This exception is raised after retry exhaustion or on non-retryable errors
    during Secret Manager operations. It signals to the calling code (typically
    service layer) that a Secret Manager operation has failed and any associated
    database transaction should be rolled back to maintain consistency.

    Usage:
        The service layer catches this exception to trigger transaction rollback:

        try:
            with db.transaction():
                installation = create_installation(...)
                secret_repo.create_secret(f'figma-secret-{installation.id}', pat)
                db.commit()
        except SecretManagerError as e:
            # Transaction rolled back automatically
            logger.error(f"Secret storage failed: {e}")
            return {"error": "Unable to store credentials"}

    Attributes:
        message: Human-readable error description
        original_exception: The underlying GCP exception that caused the failure
        operation: The operation that failed (create, update, delete, get)
    """

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
        operation: Optional[str] = None
    ):
        """
        Initialize SecretManagerError with context information.

        :param message: Human-readable error description
        :param original_exception: The underlying exception from Secret Manager SDK
        :param operation: The operation that failed (e.g., 'create_secret', 'delete_secret')
        """
        super().__init__(message)
        self.original_exception = original_exception
        self.operation = operation


class SecretRepository(ISecretRepository):
    """
    Concrete implementation of ISecretRepository using Google Cloud Secret Manager.

    This class wraps the Google Cloud Secret Manager Python client library to provide
    secure storage and management of Figma Personal Access Tokens. All operations
    follow the naming convention 'figma-secret-<installation_id>' and include retry
    logic with exponential backoff for resilience against transient failures.

    Thread Safety:
        This class is thread-safe. The Secret Manager client can be safely used across
        multiple concurrent requests. Each operation creates its own request context
        and does not share mutable state between threads.

    Dependencies:
        - IConfigRepository: Used to retrieve GCP project ID for resource path construction
        - google.cloud.secretmanager: Google Cloud SDK for Secret Manager operations

    Initialization:
        The class initializes the Secret Manager client using Application Default
        Credentials automatically discovered by the Google Cloud SDK. No explicit
        credentials are required in the constructor.

    Example Usage:
        >>> config_repo = ConfigRepository()
        >>> secret_repo = SecretRepository(config_repo)
        >>>
        >>> # Create a secret for installation ID 42
        >>> secret_repo.create_secret('figma-secret-42', 'figd_AbC123...')
        True
        >>>
        >>> # Retrieve the PAT
        >>> pat = secret_repo.get_secret('figma-secret-42')
        >>> print(pat)
        'figd_AbC123...'
        >>>
        >>> # Update the PAT (creates new version)
        >>> secret_repo.update_secret('figma-secret-42', 'figd_NewToken456...')
        True
        >>>
        >>> # Delete the secret
        >>> secret_repo.delete_secret('figma-secret-42')
        True

    Error Handling:
        All write operations raise SecretManagerError on failure after retry exhaustion.
        Read operations (get_secret) return None for missing secrets and raise
        SecretManagerError only for permission or infrastructure errors.
    """

    def __init__(self, config_repo: Optional[IConfigRepository] = None):
        """
        Initialize SecretRepository with configuration dependency.

        Creates a Secret Manager client using Application Default Credentials and
        retrieves the GCP project ID from the configuration repository. The project
        ID is used to construct resource paths for all Secret Manager operations.

        Why Dependency Injection:
            The config_repo parameter enables testing with fake configurations and
            follows the dependency injection pattern described in section B.1 of the
            Agent Action Plan. Services can inject a FakeConfigRepository to test
            Secret Manager integration without requiring actual GCP project access.

        :param config_repo: Configuration repository for GCP project ID retrieval.
                           If None, instantiates ConfigRepository() as default.
        :type config_repo: Optional[IConfigRepository]
        :raises ValueError: If project_id cannot be retrieved from configuration
        """
        # Initialize Secret Manager client with Application Default Credentials
        # Per section 0.3 Key Discovery 6: Client libraries support ADC automatically
        self._client = secretmanager.SecretManagerServiceClient()

        # Import ConfigRepository here to avoid circular imports at module level
        if config_repo is None:
            from .config_repository import ConfigRepository
            config_repo = ConfigRepository()

        self._config_repo = config_repo

        # Retrieve and validate GCP project ID
        # Per section 0.4 Key Discovery 7: Must use project ID, not project NAME
        try:
            self._project_id = self._config_repo.get_project_id()
            if not self._project_id:
                raise ValueError("GCP project ID is empty or not configured")
        except Exception as e:
            logger.error(f"Failed to retrieve GCP project ID: {e}")
            raise ValueError(f"Unable to initialize SecretRepository: {e}")

        logger.info(f"SecretRepository initialized for project: {self._project_id}")

    def create_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Create a new secret in Google Cloud Secret Manager.

        This method creates both the secret resource and its initial version containing
        the provided PAT value. The secret is created with automatic replication across
        all GCP regions for high availability and disaster recovery.

        Secret Naming Pattern:
            Must follow the pattern 'figma-secret-<installation_id>' as defined in
            section A.1.5 of the Agent Action Plan. Example: 'figma-secret-42' for
            figma_installation with id=42.

        Transaction Integration:
            This method is designed to work within database transactions. On failure,
            it raises SecretManagerError after retry exhaustion, signaling the calling
            service to rollback any database changes made prior to secret creation.
            This ensures consistency between figma_installation records and their
            corresponding secrets in Secret Manager.

        Retry Behavior:
            - Attempts operation up to retry_count times (default 3)
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors: network timeout, 503 Service Unavailable
            - Does NOT retry on permanent errors: already exists, permission denied
            - Raises SecretManagerError only after all retries exhausted

        Why Automatic Replication:
            The replication policy is set to automatic (all regions) rather than
            user-managed to ensure PATs remain accessible even if a specific region
            experiences an outage. This aligns with high availability requirements
            for production systems where Figma integration must remain operational.

        :param secret_name: Name following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: The Figma PAT to store securely
        :type secret_value: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret created successfully
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name or secret_value is empty or invalid
        """
        # Validate inputs
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")
        if not secret_value or not secret_value.strip():
            raise ValueError("secret_value cannot be empty")

        # Construct resource paths
        parent = f"projects/{self._project_id}"

        logger.info(f"Creating secret: {secret_name} (project: {self._project_id})")

        # Retry loop with exponential backoff
        attempt = 0
        last_exception = None

        while attempt < retry_count:
            try:
                # Step 1: Create the secret resource with automatic replication
                # Per section 0.4: Pattern from research shows create_secret + add_secret_version
                secret = self._client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {
                            "replication": {
                                "automatic": {}  # Replicate to all regions for high availability
                            }
                        }
                    }
                )

                logger.debug(f"Secret resource created: {secret.name}")

                # Step 2: Add the first secret version with the PAT value
                version = self._client.add_secret_version(
                    request={
                        "parent": secret.name,
                        "payload": {
                            "data": secret_value.encode("UTF-8")  # Encode string to bytes
                        }
                    }
                )

                logger.info(f"Secret created successfully: {secret_name} (version: {version.name})")
                return True

            except gcp_exceptions.AlreadyExists as e:
                # Secret already exists - this is a permanent error, do not retry
                logger.error(f"Secret {secret_name} already exists: {e}")
                raise SecretManagerError(
                    f"Secret '{secret_name}' already exists in project '{self._project_id}'",
                    original_exception=e,
                    operation="create_secret"
                )

            except gcp_exceptions.PermissionDenied as e:
                # Permission denied - permanent error, do not retry
                # Per section 0.3 Key Discovery 7: Check IAM roles for service account
                logger.error(f"Permission denied creating secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Permission denied: Service account lacks "
                    f"roles/secretmanager.admin for project '{self._project_id}'",
                    original_exception=e,
                    operation="create_secret"
                )

            except (gcp_exceptions.DeadlineExceeded, gcp_exceptions.ServiceUnavailable) as e:
                # Transient errors - retry with exponential backoff
                attempt += 1
                last_exception = e

                if attempt < retry_count:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"Transient error creating secret {secret_name} "
                        f"(attempt {attempt}/{retry_count}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to create secret {secret_name} "
                        f"after {retry_count} attempts"
                    )
                    raise SecretManagerError(
                        f"Failed to create secret '{secret_name}' "
                        f"after {retry_count} attempts: {e}",
                        original_exception=e,
                        operation="create_secret"
                    )

            except Exception as e:
                # Unexpected error - log and raise immediately without retry
                logger.error(f"Unexpected error creating secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Unexpected error creating secret '{secret_name}': {e}",
                    original_exception=e,
                    operation="create_secret"
                )

        # Should not reach here, but handle edge case
        raise SecretManagerError(
            f"Failed to create secret '{secret_name}' after {retry_count} attempts",
            original_exception=last_exception,
            operation="create_secret"
        )

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve the latest version of a secret value from Google Cloud Secret Manager.

        This method accesses the most recent enabled version of the secret and returns
        its decrypted PAT value. Read operations do not include retry logic as they
        are typically fast and transient failures are rare.

        Secret Naming Pattern:
            Must use pattern 'figma-secret-<installation_id>'.
            Example: get_secret('figma-secret-42') retrieves the PAT
            for figma_installation with id=42.

        Security Considerations:
            - The returned PAT should be used immediately and never logged or stored
            - Never expose the PAT value in error messages or API responses
            - Consider the returned value as highly sensitive credential material
            - Calling code should validate PAT format before use with Figma API

        Version Selection:
            Always retrieves the latest enabled version using the 'latest' alias. If
            the latest version is disabled or destroyed, returns None rather than
            attempting to retrieve previous versions. This ensures only active PATs
            are returned to calling code.

        Caching Guidance:
            This method does NOT cache results. If caching is needed for performance
            (e.g., to avoid repeated Secret Manager API calls during PAT validation),
            implement it in the service layer with appropriate TTL and cache
            invalidation on secret updates.

        Use Cases:
            - Validating PAT status during installation retrieval (Active/Expired)
            - Accessing PAT for Figma API calls (frame validation, metadata retrieval)
            - PAT rotation operations (retrieve old, compare with new)
            - Internal API endpoints providing PAT to authorized internal services

        Example Usage:
            >>> pat = secret_repo.get_secret('figma-secret-42')
            >>> if pat is None:
            ...     raise InstallationNotFoundError(42)
            >>> # Use PAT immediately for Figma API validation
            >>> is_valid = figma_api_repo.validate_pat(pat)

        :param secret_name: Name following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :return: Decrypted secret value (PAT) or None if secret not found
        :rtype: Optional[str]
        :raises SecretManagerError: On permission errors or unexpected failures
        :raises ValueError: If secret_name is empty or invalid
        """
        # Validate input
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")

        # Construct resource path for latest version
        # Per section 0.4: Use 'latest' alias to get most recent enabled version
        name = f"projects/{self._project_id}/secrets/{secret_name}/versions/latest"

        logger.debug(f"Retrieving secret: {secret_name} (project: {self._project_id})")

        try:
            # Access the secret version and retrieve payload
            response = self._client.access_secret_version(request={"name": name})

            # Decode bytes to string
            # Per section 0.4: Pattern from research shows decode("UTF-8")
            secret_value = response.payload.data.decode("UTF-8")

            logger.debug(f"Secret retrieved successfully: {secret_name}")
            return secret_value

        except gcp_exceptions.NotFound:
            # Secret does not exist - return None (not an error condition)
            # Per interface contract: "Secret does not exist: Returns None"
            logger.info(f"Secret {secret_name} not found in project {self._project_id}")
            return None

        except gcp_exceptions.PermissionDenied as e:
            # Permission denied - raise as SecretManagerError
            logger.error(f"Permission denied accessing secret {secret_name}: {e}")
            raise SecretManagerError(
                f"Permission denied: Service account lacks "
                f"roles/secretmanager.secretAccessor for '{secret_name}'",
                original_exception=e,
                operation="get_secret"
            )

        except Exception as e:
            # Unexpected error - log and raise
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            raise SecretManagerError(
                f"Unexpected error retrieving secret '{secret_name}': {e}",
                original_exception=e,
                operation="get_secret"
            )

    def update_secret(
        self,
        secret_name: str,
        secret_value: str,
        retry_count: int = 3
    ) -> bool:
        """
        Update an existing secret by creating a new version with the provided PAT value.

        This method implements PAT rotation by creating a new version of the secret
        without modifying or deleting existing versions. Previous versions remain
        enabled and accessible, supporting audit trails and rollback scenarios if
        the new PAT is found to be invalid.

        Secret Naming Pattern:
            Must use pattern 'figma-secret-<installation_id>'. Example:
            update_secret('figma-secret-42', 'figd_NewToken456...') updates the PAT
            for figma_installation with id=42.

        Transaction Integration:
            Designed for use within database transactions during PAT rotation. On
            failure, raises SecretManagerError to trigger transaction rollback,
            ensuring the figma_installation.updated_at timestamp is only modified
            if the PAT update succeeds in Secret Manager.

        Example PAT Rotation Transaction:
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
                logger.error(f"PAT rotation failed: {e}")
                raise APIError("Unable to update Personal Access Token")

        Versioning Behavior:
            - Creates new version with automatically incremented version number
            - Previous versions remain enabled and accessible
            - Latest version is automatically used by get_secret()
            - Old versions can be manually disabled or destroyed separately
            - Version history supports audit and compliance requirements

        Retry Behavior:
            - Attempts operation up to retry_count times (default 3)
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors: network timeout, 503 Service Unavailable
            - Does NOT retry on permanent errors: permission denied, not found
            - Raises SecretManagerError only after all retries exhausted

        Why Not Delete Old Versions:
            Keeping previous PAT versions enables:
            1. Audit trail of all PAT changes for security compliance
            2. Rollback capability if new PAT is found to be invalid
            3. Grace period for services still using old PAT
            4. Investigation of security incidents involving token compromise

        :param secret_name: Name following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param secret_value: New PAT value to store as latest version
        :type secret_value: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret version created successfully
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name or secret_value is empty or invalid
        """
        # Validate inputs
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")
        if not secret_value or not secret_value.strip():
            raise ValueError("secret_value cannot be empty")

        # Construct resource path
        secret_path = f"projects/{self._project_id}/secrets/{secret_name}"

        logger.info(f"Updating secret: {secret_name} (project: {self._project_id})")

        # Retry loop with exponential backoff
        attempt = 0
        last_exception = None

        while attempt < retry_count:
            try:
                # Add new secret version with updated PAT value
                # Per section 0.4: Pattern from research shows add_secret_version
                version = self._client.add_secret_version(
                    request={
                        "parent": secret_path,
                        "payload": {
                            "data": secret_value.encode("UTF-8")
                        }
                    }
                )

                logger.info(
                    f"Secret updated successfully: {secret_name} "
                    f"(new version: {version.name})"
                )
                return True

            except gcp_exceptions.NotFound as e:
                # Secret does not exist - permanent error, do not retry
                logger.error(f"Secret {secret_name} not found for update: {e}")
                raise SecretManagerError(
                    f"Secret '{secret_name}' does not exist in project '{self._project_id}'",
                    original_exception=e,
                    operation="update_secret"
                )

            except gcp_exceptions.PermissionDenied as e:
                # Permission denied - permanent error, do not retry
                logger.error(f"Permission denied updating secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Permission denied: Service account lacks permissions "
                    f"to update '{secret_name}'",
                    original_exception=e,
                    operation="update_secret"
                )

            except (gcp_exceptions.DeadlineExceeded, gcp_exceptions.ServiceUnavailable) as e:
                # Transient errors - retry with exponential backoff
                attempt += 1
                last_exception = e

                if attempt < retry_count:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"Transient error updating secret {secret_name} "
                        f"(attempt {attempt}/{retry_count}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to update secret {secret_name} "
                        f"after {retry_count} attempts"
                    )
                    raise SecretManagerError(
                        f"Failed to update secret '{secret_name}' "
                        f"after {retry_count} attempts: {e}",
                        original_exception=e,
                        operation="update_secret"
                    )

            except Exception as e:
                # Unexpected error - log and raise immediately without retry
                logger.error(f"Unexpected error updating secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Unexpected error updating secret '{secret_name}': {e}",
                    original_exception=e,
                    operation="update_secret"
                )

        # Should not reach here, but handle edge case
        raise SecretManagerError(
            f"Failed to update secret '{secret_name}' after {retry_count} attempts",
            original_exception=last_exception,
            operation="update_secret"
        )

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

        Secret Naming Pattern:
            Must use pattern 'figma-secret-<installation_id>'. Example:
            delete_secret('figma-secret-42') deletes all PAT versions for
            figma_installation with id=42.

        Transaction Integration:
            CRITICAL for maintaining consistency during installation deletion. Must be
            called within a transaction that also soft-deletes the figma_installation
            record. On failure, raises SecretManagerError to trigger database rollback,
            preventing orphaned secrets or installations.

        Example Installation Deletion Transaction:
            try:
                with db.transaction():
                    # Soft delete installation record
                    figma_repo.soft_delete_installation(installation_id)
                    # Remove secret from Secret Manager
                    secret_repo.delete_secret(f'figma-secret-{installation_id}')
                    db.commit()
            except SecretManagerError as e:
                # Installation soft-delete rolled back
                # No orphaned secret or installation record
                logger.error(f"Failed to delete secret: {e}")
                raise APIError("Unable to complete installation deletion")

        Consistency Requirements:
            This operation is critical for preventing orphaned secrets. Per section
            A.3.3 of the Agent Action Plan: "Database and Secret Manager must remain
            synchronized - no orphaned secrets or installations." If deletion fails:
            - Database changes MUST be rolled back
            - Do NOT leave installation marked as deleted with secret still present
            - Do NOT leave secret in Secret Manager without database reference

        Retry Behavior:
            - Attempts operation up to retry_count times (default 3)
            - Uses exponential backoff: 1s, 2s, 4s between attempts
            - Retries on transient errors: network timeout, 503 Service Unavailable
            - Does NOT retry on permanent errors: permission denied
            - Treats "not found" as success (idempotent deletion)
            - Raises SecretManagerError only after all retries exhausted

        Idempotency:
            This method is idempotent. If the secret does not exist (returns NotFound),
            the method returns True (successful deletion) rather than raising an error.
            This allows for safe retry of deletion operations and cleanup of partial
            failures where the secret was already deleted in a previous attempt.

        Audit Logging:
            All deletion attempts are logged with the secret name and operation result.
            This supports compliance and security audit requirements for tracking when
            PATs are removed from the system.

        Why Permanent Deletion:
            Unlike update operations that preserve version history, deletion is permanent
            because:
            1. Soft-deleted installations should not retain access to PATs
            2. Prevents accumulation of unused secrets and associated costs
            3. Reduces attack surface by removing credentials no longer in use
            4. Complies with data retention policies for sensitive credentials

        :param secret_name: Name following pattern 'figma-secret-<installation_id>'
        :type secret_name: str
        :param retry_count: Number of retry attempts on transient failures (default: 3)
        :type retry_count: int
        :return: True if secret deleted successfully or does not exist (idempotent)
        :rtype: bool
        :raises SecretManagerError: After retry exhaustion or on non-retryable errors
        :raises ValueError: If secret_name is empty or invalid
        """
        # Validate input
        if not secret_name or not secret_name.strip():
            raise ValueError("secret_name cannot be empty")

        # Construct resource path
        name = f"projects/{self._project_id}/secrets/{secret_name}"

        logger.info(f"Deleting secret: {secret_name} (project: {self._project_id})")

        # Retry loop with exponential backoff
        attempt = 0
        last_exception = None

        while attempt < retry_count:
            try:
                # Delete the secret and all its versions
                # Per section 0.4: Pattern from research shows delete_secret
                self._client.delete_secret(request={"name": name})

                logger.info(f"Secret deleted successfully: {secret_name}")
                return True

            except gcp_exceptions.NotFound:
                # Secret does not exist - treat as successful deletion (idempotent)
                # Per interface contract: "Treats 'not found' as success"
                logger.info(
                    f"Secret {secret_name} not found "
                    f"(already deleted or never existed)"
                )
                return True

            except gcp_exceptions.PermissionDenied as e:
                # Permission denied - permanent error, do not retry
                logger.error(f"Permission denied deleting secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Permission denied: Service account lacks permissions "
                    f"to delete '{secret_name}'",
                    original_exception=e,
                    operation="delete_secret"
                )

            except (gcp_exceptions.DeadlineExceeded, gcp_exceptions.ServiceUnavailable) as e:
                # Transient errors - retry with exponential backoff
                attempt += 1
                last_exception = e

                if attempt < retry_count:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 2 ** (attempt - 1)
                    logger.warning(
                        f"Transient error deleting secret {secret_name} "
                        f"(attempt {attempt}/{retry_count}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to delete secret {secret_name} "
                        f"after {retry_count} attempts"
                    )
                    raise SecretManagerError(
                        f"Failed to delete secret '{secret_name}' "
                        f"after {retry_count} attempts: {e}",
                        original_exception=e,
                        operation="delete_secret"
                    )

            except Exception as e:
                # Unexpected error - log and raise immediately without retry
                logger.error(f"Unexpected error deleting secret {secret_name}: {e}")
                raise SecretManagerError(
                    f"Unexpected error deleting secret '{secret_name}': {e}",
                    original_exception=e,
                    operation="delete_secret"
                )

        # Should not reach here, but handle edge case
        raise SecretManagerError(
            f"Failed to delete secret '{secret_name}' after {retry_count} attempts",
            original_exception=last_exception,
            operation="delete_secret"
        )
