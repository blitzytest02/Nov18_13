"""Pytest configuration for archie-service-admin tests."""
import sys
import os

# Add archie-service-admin directory to Python path for imports
# This allows both absolute imports (from src.repositories import ...)
# and relative imports within src package (from ..models import ...)
root_path = os.path.dirname(os.path.abspath(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)
