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
    - IConfigRepository: Application configuration access

Usage Pattern:
    Services should depend on these interfaces, not concrete implementations:
    
    class FigmaService:
        def __init__(
            self,
            secret_repo: ISecretRepository,
            figma_api_repo: IFigmaAPIRepository,
            config_repo: IConfigRepository
        ):
            self.secret_repo = secret_repo
            self.figma_api_repo = figma_api_repo
            self.config_repo = config_repo

Testing Pattern:
    Tests inject fake implementations:
    
    def test_service():
        fake_secret_repo = FakeSecretRepository()
        fake_figma_api = FakeFigmaAPIRepository()
        fake_config = FakeConfigRepository()
        service = FigmaService(fake_secret_repo, fake_figma_api, fake_config)
        # Test service logic...
"""

from .i_secret_repository import ISecretRepository
from .i_figma_api_repository import IFigmaAPIRepository
from .i_config_repository import IConfigRepository

__all__ = [
    'ISecretRepository',
    'IFigmaAPIRepository',
    'IConfigRepository',
]
