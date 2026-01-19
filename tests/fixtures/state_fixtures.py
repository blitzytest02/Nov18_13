"""
Test fixtures for ReverseDocumentState.

This module provides factory functions and sample data for testing
state management functionality in the reverse document generator.
"""

from typing import Any, Dict, List, Optional

from faker import Faker

from src.app.services.state_manager import ReverseDocumentState, get_state
from tests.fixtures.document_fixtures import (
    SAMPLE_DOCUMENT_SECTION,
    SAMPLE_CHANGED_SECTION,
    SAMPLE_SECTIONS_LIST,
)


fake = Faker()


def create_test_state(
    tech_spec: Optional[str] = None,
    document_sections: Optional[List[Dict[str, Any]]] = None,
    current_section_index: int = 0,
    completed: bool = False,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ReverseDocumentState:
    """
    Create a test ReverseDocumentState with optional overrides.
    
    Args:
        tech_spec: Technical specification content
        document_sections: List of document section dictionaries
        current_section_index: Current processing position
        completed: Whether processing is complete
        error: Error message if any
        metadata: Additional metadata
        
    Returns:
        ReverseDocumentState instance
    """
    return get_state(
        tech_spec=tech_spec or fake.paragraph(nb_sentences=5),
        document_sections=document_sections or [],
        current_section_index=current_section_index,
        completed=completed,
        error=error,
        metadata=metadata or {}
    )


def create_empty_state() -> ReverseDocumentState:
    """
    Create an empty state with minimal data.
    
    Returns:
        ReverseDocumentState with empty/default values
    """
    return get_state(tech_spec="")


def create_state_with_sections(count: int = 3) -> ReverseDocumentState:
    """
    Create a state with generated document sections.
    
    Args:
        count: Number of sections to include
        
    Returns:
        ReverseDocumentState with sections
    """
    sections = [
        {
            "heading": f"Section {i}",
            "content": fake.paragraph(),
            "status": "UNCHANGED",
            "changes": [],
            "order": i
        }
        for i in range(count)
    ]
    return get_state(
        tech_spec=fake.paragraph(nb_sentences=5),
        document_sections=sections
    )


def create_completed_state(
    with_error: bool = False
) -> ReverseDocumentState:
    """
    Create a state marked as completed.
    
    Args:
        with_error: Whether to include an error message
        
    Returns:
        Completed ReverseDocumentState
    """
    return get_state(
        tech_spec=fake.paragraph(),
        document_sections=SAMPLE_SECTIONS_LIST.copy(),
        current_section_index=len(SAMPLE_SECTIONS_LIST),
        completed=True,
        error="Processing failed" if with_error else None
    )


def create_in_progress_state(section_index: int = 1) -> ReverseDocumentState:
    """
    Create a state that is in progress (partially processed).
    
    Args:
        section_index: The current section being processed
        
    Returns:
        ReverseDocumentState in progress
    """
    return get_state(
        tech_spec=fake.paragraph(nb_sentences=5),
        document_sections=SAMPLE_SECTIONS_LIST.copy(),
        current_section_index=section_index,
        completed=False
    )


def create_state_with_metadata(
    metadata: Optional[Dict[str, Any]] = None
) -> ReverseDocumentState:
    """
    Create a state with metadata.
    
    Args:
        metadata: Custom metadata dictionary
        
    Returns:
        ReverseDocumentState with metadata
    """
    default_metadata = {
        "created_at": "2024-01-01T00:00:00Z",
        "last_updated": "2024-01-01T00:00:00Z",
        "processing_time_ms": 1500,
        "llm_calls": 3
    }
    return get_state(
        tech_spec=fake.paragraph(),
        document_sections=[],
        metadata=metadata or default_metadata
    )


# Sample state data for testing
SAMPLE_EMPTY_STATE = {
    "tech_spec": "",
    "document_sections": [],
    "current_section_index": 0,
    "completed": False,
    "error": None,
    "metadata": {}
}

SAMPLE_STATE_WITH_SECTIONS = {
    "tech_spec": "This is a sample technical specification for testing purposes.",
    "document_sections": SAMPLE_SECTIONS_LIST,
    "current_section_index": 0,
    "completed": False,
    "error": None,
    "metadata": {
        "created_at": "2024-01-01T00:00:00Z"
    }
}

SAMPLE_COMPLETED_STATE = {
    "tech_spec": "Completed tech spec.",
    "document_sections": SAMPLE_SECTIONS_LIST,
    "current_section_index": len(SAMPLE_SECTIONS_LIST),
    "completed": True,
    "error": None,
    "metadata": {
        "completed_at": "2024-01-01T01:00:00Z",
        "processing_time_ms": 5000
    }
}

SAMPLE_ERROR_STATE = {
    "tech_spec": "Failed tech spec.",
    "document_sections": [SAMPLE_DOCUMENT_SECTION],
    "current_section_index": 0,
    "completed": True,
    "error": "Processing failed: LLM timeout",
    "metadata": {
        "error_occurred_at": "2024-01-01T00:30:00Z"
    }
}

# Invalid state data for testing validation
INVALID_STATE_MISSING_TECH_SPEC = {
    "document_sections": [],
    "current_section_index": 0,
    "completed": False
}

INVALID_STATE_WRONG_TYPE_SECTIONS = {
    "tech_spec": "Valid spec",
    "document_sections": "not a list",
    "current_section_index": 0,
    "completed": False
}

INVALID_STATE_WRONG_TYPE_INDEX = {
    "tech_spec": "Valid spec",
    "document_sections": [],
    "current_section_index": "not an int",
    "completed": False
}

INVALID_STATE_WRONG_TYPE_COMPLETED = {
    "tech_spec": "Valid spec",
    "document_sections": [],
    "current_section_index": 0,
    "completed": "not a bool"
}
