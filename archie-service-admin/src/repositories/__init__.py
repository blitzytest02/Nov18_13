"""
Repository package for archie-service-admin.

This package contains all repository implementations and interfaces that abstract
external dependencies such as databases, Google Cloud Secret Manager, Figma API,
and application configuration.

Package Structure:
    - interfaces/: Abstract base classes defining repository contracts
    - implementations: Concrete repository classes (e.g., FigmaRepository, SecretRepository)

Design Pattern:
    This package follows the Repository Pattern with Dependency Injection:
    - Interfaces define contracts for external system interactions
    - Concrete implementations handle actual external system communication
    - Services depend on interface abstractions, not concrete implementations
    - Test code injects fake implementations for unit testing

Purpose:
    - Separate business logic from infrastructure concerns
    - Enable testability through interface-based dependency injection
    - Provide consistent error handling across external system interactions
    - Isolate external SDK dependencies (Google Cloud, Figma API, etc.)
"""

# Repository interfaces are available through the interfaces subpackage
# Import them in your code as:
# from repositories.interfaces.i_secret_repository import ISecretRepository
# from repositories.interfaces.i_figma_api_repository import IFigmaAPIRepository

__all__ = []
