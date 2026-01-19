"""
State management for the reverse document generator.

This module provides the state management functionality for tracking
document processing state throughout the reverse document generation workflow.
"""

from typing import Any, Dict, List, Optional, TypedDict

from src.app.models.document import DocumentSection


class ReverseDocumentState(TypedDict, total=False):
    """
    TypedDict representing the state of the reverse document generation process.
    
    This state object is used to track:
    - The technical specification being processed
    - The list of document sections being generated
    - The current processing position
    - Completion status
    - Any error information
    
    Attributes:
        tech_spec: The technical specification content being processed
        document_sections: List of DocumentSection objects being generated
        current_section_index: Index of the section currently being processed
        completed: Whether the processing has completed
        error: Any error message if processing failed
        metadata: Additional metadata about the processing
    """
    tech_spec: str
    document_sections: List[Dict[str, Any]]
    current_section_index: int
    completed: bool
    error: Optional[str]
    metadata: Dict[str, Any]


def get_state(
    tech_spec: str = "",
    document_sections: Optional[List[Dict[str, Any]]] = None,
    current_section_index: int = 0,
    completed: bool = False,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ReverseDocumentState:
    """
    Create and return a new ReverseDocumentState with the provided values.
    
    This factory function ensures all required fields are properly initialized
    with sensible defaults.
    
    Args:
        tech_spec: The technical specification content
        document_sections: List of document section dictionaries
        current_section_index: Current processing position
        completed: Whether processing is complete
        error: Error message if any
        metadata: Additional metadata
        
    Returns:
        A new ReverseDocumentState instance
        
    Example:
        >>> state = get_state(tech_spec="My spec content")
        >>> state["tech_spec"]
        'My spec content'
        >>> state["completed"]
        False
    """
    return ReverseDocumentState(
        tech_spec=tech_spec,
        document_sections=document_sections if document_sections is not None else [],
        current_section_index=current_section_index,
        completed=completed,
        error=error,
        metadata=metadata if metadata is not None else {}
    )


def update_state(
    state: ReverseDocumentState,
    **updates: Any
) -> ReverseDocumentState:
    """
    Create a new state with the specified updates applied.
    
    This function creates a copy of the state with updates applied,
    preserving immutability.
    
    Args:
        state: The current state
        **updates: Key-value pairs to update
        
    Returns:
        A new ReverseDocumentState with updates applied
        
    Example:
        >>> state = get_state(tech_spec="content")
        >>> new_state = update_state(state, completed=True)
        >>> new_state["completed"]
        True
    """
    new_state = dict(state)
    new_state.update(updates)
    return ReverseDocumentState(**new_state)


def add_document_section(
    state: ReverseDocumentState,
    section: DocumentSection
) -> ReverseDocumentState:
    """
    Add a document section to the state.
    
    Creates a new state with the section appended to document_sections.
    
    Args:
        state: The current state
        section: The DocumentSection to add
        
    Returns:
        A new ReverseDocumentState with the section added
    """
    new_sections = list(state.get("document_sections", []))
    new_sections.append(section.to_dict())
    return update_state(state, document_sections=new_sections)


def get_current_section(state: ReverseDocumentState) -> Optional[Dict[str, Any]]:
    """
    Get the current document section being processed.
    
    Args:
        state: The current state
        
    Returns:
        The current document section dict, or None if no sections exist
    """
    sections = state.get("document_sections", [])
    index = state.get("current_section_index", 0)
    
    if sections and 0 <= index < len(sections):
        return sections[index]
    return None


def advance_section(state: ReverseDocumentState) -> ReverseDocumentState:
    """
    Advance to the next section in the document.
    
    Args:
        state: The current state
        
    Returns:
        A new state with current_section_index incremented
    """
    current_index = state.get("current_section_index", 0)
    sections = state.get("document_sections", [])
    
    new_index = current_index + 1
    completed = new_index >= len(sections)
    
    return update_state(
        state,
        current_section_index=new_index,
        completed=completed
    )


def mark_completed(
    state: ReverseDocumentState,
    error: Optional[str] = None
) -> ReverseDocumentState:
    """
    Mark the processing as completed.
    
    Args:
        state: The current state
        error: Optional error message if processing failed
        
    Returns:
        A new state marked as completed
    """
    return update_state(state, completed=True, error=error)


def validate_state(state: ReverseDocumentState) -> bool:
    """
    Validate that a state object has all required fields.
    
    Args:
        state: The state to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ["tech_spec", "document_sections", "current_section_index", "completed"]
    
    for field in required_fields:
        if field not in state:
            return False
    
    # Validate types
    if not isinstance(state.get("tech_spec"), str):
        return False
    if not isinstance(state.get("document_sections"), list):
        return False
    if not isinstance(state.get("current_section_index"), int):
        return False
    if not isinstance(state.get("completed"), bool):
        return False
    
    return True
