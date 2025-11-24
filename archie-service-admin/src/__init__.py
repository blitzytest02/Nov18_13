"""
Source package for archie-service-admin.

This package serves as the top-level container for the archie-service-admin application's
source code, organizing all implementation modules for the Figma integration feature into
a well-structured Python package hierarchy. It provides convenient re-exports of commonly
used classes and interfaces to simplify imports throughout the application.

Package Structure:
    The src/ package is organized into distinct layers following clean architecture
    principles with clear separation of concerns:

    src/
    ├── __init__.py (this file)         # Top-level package initialization
    ├── repositories/                    # Repository pattern implementations
    │   ├── __init__.py                 # Repository package exports
    │   ├── interfaces/                 # Abstract repository interfaces (ports)
    │   │   ├── i_figma_repository.py   # Database operations contract
    │   │   ├── i_secret_repository.py  # Secret Manager operations contract
    │   │   ├── i_figma_api_repository.py  # Figma API client contract
    │   │   └── i_config_repository.py  # Configuration access contract
    │   ├── figma_repository.py         # Concrete DB implementation (adapter)
    │   ├── secret_repository.py        # Concrete Secret Manager implementation
    │   ├── figma_api_repository.py     # Concrete Figma API implementation
    │   └── config_repository.py        # Concrete configuration implementation
    ├── services/                        # Business logic layer
    │   ├── __init__.py                 # Services package exports
    │   └── figma_service.py            # Core Figma integration business logic
    ├── routes/                          # HTTP request handling layer
    │   ├── __init__.py                 # Routes package exports
    │   └── figma_routes.py             # Figma API endpoints (admin service)
    └── models/                          # SQLAlchemy ORM models
        ├── __init__.py                 # Models package exports
        ├── base.py                     # Shared declarative base
        ├── figma_installation.py       # Figma installation entity
        ├── figma_installation_access.py  # Access control entity
        └── figma_attachment.py         # Frame attachment entity

Architectural Pattern:
    This package implements a layered architecture with dependency injection
    for the Figma integration feature as specified in section B.1 of the
    Agent Action Plan:

    1. **Routes Layer** (routes/):
       - HTTP request validation and response formatting
       - User authentication and authorization checks
       - NO business logic - delegates to service layer
       - Handles HTTP-specific concerns (status codes, JSON serialization)

    2. **Services Layer** (services/):
       - All business logic and orchestration
       - Coordinates operations across multiple repositories
       - Manages transactions between database and external systems
       - Unaware of HTTP/JSON - works with domain objects
       - Accepts repository interfaces via dependency injection

    3. **Repository Layer** (repositories/):
       - Abstracts ALL external dependencies (database, APIs, config)
       - Interfaces define contracts (ports in hexagonal architecture)
       - Implementations provide adapters to actual systems
       - Enables testing with fake implementations
       - Encapsulates retry logic, error handling, and resilience patterns

    4. **Models Layer** (models/):
       - SQLAlchemy ORM entity definitions
       - Database schema representation
       - Relationships and constraints
       - Shared across services via db-common-models

Design Principles Applied:
    - **Dependency Inversion**: High-level services depend on repository abstractions,
      not concrete implementations. This enables flexibility and testability.

    - **Single Responsibility**: Each layer has one clear purpose - routes handle HTTP,
      services implement business rules, repositories manage I/O.

    - **Open/Closed**: New repository implementations can be added without modifying
      service code by implementing existing interfaces.

    - **Interface Segregation**: Repository interfaces are focused and specific to
      their domain (Figma DB, Secret Manager, Figma API, Config).

    - **Separation of Concerns**: External system knowledge (SQLAlchemy, google-cloud,
      requests) is isolated to repository implementations.

Convenience Imports:
    This __init__.py re-exports frequently used classes to enable simpler import
    statements throughout the application:

    Without convenience imports:
        >>> from src.services.figma_service import FigmaService
        >>> from src.repositories.interfaces.i_figma_repository import IFigmaRepository
        >>> from src.models.figma_installation import FigmaInstallation

    With convenience imports (preferred):
        >>> from src import FigmaService, IFigmaRepository, FigmaInstallation

    The explicit __all__ list documents the public API of this package and helps
    static analysis tools provide accurate autocomplete suggestions.

Usage Examples:

    Production usage in route handlers:
        >>> from src import FigmaService
        >>>
        >>> # Service initializes with default production repositories
        >>> figma_service = FigmaService()
        >>> installation = figma_service.create_installation(
        ...     user_id=request.user_id,
        ...     name=request.json['name'],
        ...     pat=request.json['pat']
        ... )

    Testing with dependency injection:
        >>> from src import FigmaService, IFigmaRepository, ISecretRepository
        >>> from tests.fakes import FakeFigmaRepository, FakeSecretRepository
        >>>
        >>> # Inject fake repositories that don't touch real systems
        >>> fake_figma_repo = FakeFigmaRepository()
        >>> fake_secret_repo = FakeSecretRepository()
        >>> figma_service = FigmaService(
        ...     figma_repo=fake_figma_repo,
        ...     secret_repo=fake_secret_repo
        ... )
        >>> # Test business logic without actual database or Secret Manager
        >>> installation = figma_service.create_installation(
        ...     user_id=1, name="Test", pat="figd_test_token"
        ... )
        >>> assert fake_figma_repo.installations[installation['id']] is not None
        >>> secret_name = f"figma-secret-{installation['id']}"
        >>> assert fake_secret_repo.secrets[secret_name] == "figd_test_token"

Feature Overview:
    This package implements comprehensive Figma integration support for the Blitzy
    platform, enabling users to:

    - **Connect Figma**: Store Personal Access Tokens securely in Google Secret Manager
    - **Share Integrations**: Grant/revoke access to installations with role-based control
    - **Attach Frames**: Link Figma design frames to projects with URL validation
    - **Manage Credentials**: Update PATs and track validity status (Active/Expired)
    - **Maintain Consistency**: Transactional coordination between database and Secret Manager

    Key technical features:
    - Feature flag support (FIGMA_INTEGRATION_ENABLED)
    - Soft deletion for audit trails
    - PAT security (never exposed in responses)
    - Retry logic for Secret Manager operations
    - Role-based authorization (ADMIN/SUPER_ADMIN)

For detailed technical documentation, see:
    - archie-service-admin/docs/figma_technical_guide.md: Implementation guide
    - Agent Action Plan Section 0: Complete requirements specification
    - Agent Action Plan Section B.1: Architectural pattern details
"""

# Import service layer classes
# FigmaService contains all business logic for Figma integration operations
from .services import FigmaService

# Import repository interfaces for type hints and test fake base classes
# These abstract base classes define contracts that concrete implementations must fulfill
from .repositories import (
    IFigmaRepository,      # Interface for Figma database operations
    ISecretRepository,     # Interface for Google Secret Manager operations
    IFigmaAPIRepository,   # Interface for Figma REST API client operations
    IConfigRepository,     # Interface for application configuration access
)

# Import concrete repository implementations for production usage
# These are the default implementations used when services initialize without explicit injection
from .repositories import (
    FigmaRepository,       # SQLAlchemy-based database repository
    SecretRepository,      # Google Cloud Secret Manager client wrapper
    FigmaAPIRepository,    # HTTP client for Figma API
    ConfigRepository,      # Environment variable configuration access
)

# Import SQLAlchemy ORM models for Figma entities
# These models represent database tables and their relationships
from .models.figma_installation import FigmaInstallation
from .models.figma_installation_access import FigmaInstallationAccess
from .models.figma_attachment import FigmaAttachment

# Define explicit public API for this package
# This __all__ list controls what gets imported with "from src import *"
# and helps IDEs provide accurate autocomplete suggestions
__all__ = [
    # Service Layer
    # Core business logic class for all Figma integration operations
    "FigmaService",

    # Repository Interfaces
    # Abstract base classes defining contracts for external dependencies
    # Used for type hints in service constructors and as base classes for test fakes
    "IFigmaRepository",
    "ISecretRepository",
    "IFigmaAPIRepository",
    "IConfigRepository",

    # Repository Implementations
    # Concrete classes providing production implementations of repository interfaces
    # Used as default implementations when services initialize without injection
    "FigmaRepository",
    "SecretRepository",
    "FigmaAPIRepository",
    "ConfigRepository",

    # Database Models
    # SQLAlchemy ORM models representing Figma integration database entities
    # Used for type hints and return types in repository and service methods
    "FigmaInstallation",
    "FigmaInstallationAccess",
    "FigmaAttachment",
]
