"""
Services package for archie-service-admin.

This package contains the service layer, which implements all business logic for the
application. Services act as the orchestration layer between route handlers (HTTP
layer) and repositories (data/external system layer).

Architecture Pattern:
    The service layer follows a dependency injection pattern to maintain separation
    of concerns and enable comprehensive testing:

    Route Handlers (routes/)
        ↓ (validates HTTP requests, extracts data, handles responses)
    Services (services/)
        ↓ (implements business logic, coordinates operations)
    Repository Interfaces (repositories/interfaces/)
        ↓ (abstract contracts for external dependencies)
    Repository Implementations (repositories/)
        ↓ (concrete implementations of interfaces)
    External Systems (Database, Secret Manager, APIs, Config)

Key Principles:
    1. Route handlers contain NO business logic - only request validation and HTTP
       concerns. All business rules live in services.

    2. Services accept repository interfaces via constructor parameters with optional
       dependency injection:
       - Default: Services instantiate concrete repository implementations automatically
       - Testing: Services accept fake/mock repositories for unit testing
       - Production: Services use default repositories connecting to real systems

    3. Services are unaware of HTTP, JSON, or route-specific concerns. They work with
       domain objects and return structured data that routes can serialize.

    4. Repository interfaces (IFigmaRepository, ISecretRepository, IFigmaAPIRepository,
       IConfigRepository) abstract ALL external dependencies including:
       - Database operations
       - Google Secret Manager
       - Figma API calls
       - Configuration/environment variables

    5. This pattern enables:
       - Testability: Inject fakes to test business logic without external systems
       - Flexibility: Swap implementations without changing business logic
       - Clarity: Clear separation between orchestration and I/O operations

Example Usage:
    ```python
    # In route handler (production)
    from services import FigmaService

    figma_service = FigmaService()  # Uses default repositories
    installation = figma_service.create_installation(
        user_id=request.user_id,
        name=request.json['name'],
        pat=request.json['pat']
    )

    # In test file
    from services import FigmaService
    from tests.fakes import FakeFigmaRepository, FakeSecretRepository

    fake_figma_repo = FakeFigmaRepository()
    fake_secret_repo = FakeSecretRepository()
    figma_service = FigmaService(
        figma_repo=fake_figma_repo,
        secret_repo=fake_secret_repo
    )
    # Test business logic without touching real database or Secret Manager
    ```

Available Services:
    - FigmaService: Complete business logic for Figma integration including installation
      lifecycle management, access control, frame attachments, and PAT management with
      transactional consistency between database and Secret Manager.

For detailed information on specific services, see their respective module documentation.
"""

# Import service classes for convenient access by route handlers
from .figma_service import FigmaService

# Define public API for the services package
__all__ = [
    'FigmaService',
]
