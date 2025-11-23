"""
Repository interface definitions for archie-service-admin.

This module contains abstract base classes (interfaces) that define contracts for
all external system interactions. These interfaces enable:
- Dependency injection in service layer
- Test doubles (fakes) for unit testing
- Clear separation of concerns
- Consistent error handling patterns

Available Interfaces:
    - ISecretRepository: Google Cloud Secret Manager operations
    - IFigmaAPIRepository: Figma API client operations
    - IFigmaRepository: Database operations for Figma entities (to be implemented)
    - IConfigRepository: Application configuration access (to be implemented)

Usage Pattern:
    Services should depend on these interfaces, not concrete implementations:
    
    class FigmaService:
        def __init__(
            self,
            secret_repo: ISecretRepository,
            figma_api_repo: IFigmaAPIRepository
        ):
            self.secret_repo = secret_repo
            self.figma_api_repo = figma_api_repo

Testing Pattern:
    Tests inject fake implementations:
    
    def test_service():
        fake_secret_repo = FakeSecretRepository()
        fake_figma_api = FakeFigmaAPIRepository()
        service = FigmaService(fake_secret_repo, fake_figma_api)
        # Test service logic...
"""

__all__ = []
