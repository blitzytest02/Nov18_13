"""
Repository package for archie-service-admin.

This package provides centralized exports of all repository interfaces and concrete
implementations that abstract external dependencies such as databases, Google Cloud
Secret Manager, Figma API, and application configuration. It implements the Repository
Pattern with Dependency Injection as specified in section B.1 of the Agent Action Plan.

Architectural Purpose:
    The repository layer serves as the boundary between business logic (service layer)
    and external systems (database, APIs, cloud services). This separation enables:

    1. **Testability**: Services depend on interface abstractions, allowing tests to
       inject fake implementations without requiring actual external systems

    2. **Flexibility**: Concrete implementations can be swapped without changing
       business logic (e.g., switch from PostgreSQL to MongoDB by implementing
       IFigmaRepository with a different database adapter)

    3. **Isolation**: External SDK dependencies (google-cloud-secret-manager, requests,
       SQLAlchemy) are encapsulated in repository implementations, never exposed to
       service layer

    4. **Consistency**: All external interactions follow standardized patterns for
       error handling, retry logic, and transaction management

Package Structure:
    - interfaces/: Abstract base classes (ABCs) defining repository contracts
        * IFigmaRepository: Database operations for Figma entities
        * ISecretRepository: Google Cloud Secret Manager operations
        * IFigmaAPIRepository: Figma REST API client operations
        * IConfigRepository: Application configuration access

    - Concrete implementations: Production implementations of interfaces
        * FigmaRepository: SQLAlchemy-based database operations
        * SecretRepository: Google Secret Manager client wrapper
        * FigmaAPIRepository: HTTP client for Figma API
        * ConfigRepository: Environment variable configuration access

Design Pattern (Dependency Injection):
    Services receive repository dependencies through constructor injection, with
    optional parameters that default to production implementations. This pattern
    enables simple production usage while supporting explicit test injection:

    Production Usage (implicit defaults):
        >>> from repositories import FigmaService
        >>> service = FigmaService()  # Uses default production repos
        >>> installation = service.create_installation(
        ...     user_id=1, name="My Figma", pat="figd_..."
        ... )

    Test Usage (explicit fakes):
        >>> from tests.fakes import (
        ...     FakeFigmaRepository, FakeSecretRepository
        ... )
        >>> from repositories import FigmaService
        >>>
        >>> fake_figma_repo = FakeFigmaRepository()
        >>> fake_secret_repo = FakeSecretRepository()
        >>> service = FigmaService(
        ...     figma_repo=fake_figma_repo,
        ...     secret_repo=fake_secret_repo
        ... )
        >>> # Service now uses in-memory fakes instead of real DB

Import Patterns:
    This __init__.py provides convenient imports for both interfaces and implementations:

    Service Layer Import:
        >>> from repositories import (
        ...     IFigmaRepository,      # Interface for type hints
        ...     ISecretRepository,     # Interface for type hints
        ...     FigmaRepository,       # Default implementation
        ...     SecretRepository       # Default implementation
        ... )
        >>>
        >>> class FigmaService:
        ...     def __init__(
        ...         self,
        ...         figma_repo: IFigmaRepository = None,
        ...         secret_repo: ISecretRepository = None
        ...     ):
        ...         self.figma_repo = figma_repo or FigmaRepository()
        ...         self.secret_repo = secret_repo or SecretRepository()

    Test Layer Import:
        >>> from repositories import IFigmaRepository, ISecretRepository
        >>>
        >>> class FakeFigmaRepository(IFigmaRepository):
        ...     # Implement all abstract methods for testing
        ...     pass

Transaction Consistency Pattern:
    Repositories support coordinated transactions between database and external systems.
    This pattern maintains consistency when operations span multiple systems (e.g.,
    creating a database record and storing a secret in Secret Manager):

    >>> from repositories import FigmaRepository, SecretRepository
    >>>
    >>> figma_repo = FigmaRepository(db_session)
    >>> secret_repo = SecretRepository()
    >>>
    >>> try:
    ...     with db_session.begin():
    ...         # Step 1: Create database record
    ...         installation = figma_repo.create_installation(user_id=1, name="My Figma")
    ...
    ...         # Step 2: Store secret (raises SecretManagerError on failure)
    ...         secret_name = f"figma-secret-{installation.id}"
    ...         secret_repo.create_secret(secret_name, pat_value)
    ...
    ...         # Both operations succeeded - transaction commits automatically
    ... except SecretManagerError as e:
    ...     # Secret Manager failed - database transaction rolls back automatically
    ...     # No orphaned database records exist without corresponding secrets
    ...     logger.error(f"Failed to store PAT: {e}")
    ...     raise

Reference Documentation:
    - Agent Action Plan Section 0.2: Requirements analysis and technical scope
    - Agent Action Plan Section B.1: Architectural pattern (DI + Repository Pattern)
    - archie-service-admin/docs/figma_technical_guide.md: Detailed implementation guide
"""

# Import all repository interfaces from interfaces subpackage
# These are abstract base classes (ABCs) that define contracts for
# external system interactions
from .interfaces import (
    IFigmaRepository,
    ISecretRepository,
    IFigmaAPIRepository,
    IConfigRepository,
)

# Import all concrete repository implementations
# These are production implementations that interact with actual
# external systems
from .figma_repository import FigmaRepository
from .secret_repository import SecretRepository
from .figma_api_repository import FigmaAPIRepository
from .config_repository import ConfigRepository

# Explicit exports for controlled public API
# This __all__ list defines what gets imported when using
# "from repositories import *" and helps IDEs provide accurate
# autocomplete suggestions
__all__ = [
    # Repository Interfaces (for type hints and test fake base classes)
    "IFigmaRepository",
    "ISecretRepository",
    "IFigmaAPIRepository",
    "IConfigRepository",
    # Concrete Implementations (for production usage and default init)
    "FigmaRepository",
    "SecretRepository",
    "FigmaAPIRepository",
    "ConfigRepository",
]
