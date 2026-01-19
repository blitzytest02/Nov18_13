"""
Document helper for the reverse document generator.

This module provides the ReverseDocumentHelper class which handles
the core business logic for processing documents in the reverse
document generation workflow.
"""

from typing import Any, Callable, Dict, List, Optional

from src.app.models.document import DocumentSection, DocumentSectionStatus
from src.app.services.state_manager import (
    ReverseDocumentState,
    add_document_section,
    advance_section,
    get_state,
    mark_completed,
    update_state,
)


class ReverseDocumentHelper:
    """
    Helper class for managing the reverse document generation process.
    
    This class provides methods for:
    - Processing document sections
    - Managing processing state
    - Executing tools and handling responses
    - Coordinating with external services
    
    Attributes:
        state: The current processing state
        tools: Dictionary of available tools
        llm_handler: Optional handler for LLM interactions
    """

    def __init__(
        self,
        tech_spec: str = "",
        tools: Optional[Dict[str, Callable]] = None,
        llm_handler: Optional[Callable] = None
    ):
        """
        Initialize the ReverseDocumentHelper.
        
        Args:
            tech_spec: The technical specification to process
            tools: Dictionary mapping tool names to callable handlers
            llm_handler: Optional handler for LLM operations
        """
        self.state = get_state(tech_spec=tech_spec)
        self.tools = tools if tools is not None else {}
        self.llm_handler = llm_handler

    def get_tools(self) -> Dict[str, Callable]:
        """
        Get the dictionary of available tools.
        
        Returns:
            Dictionary mapping tool names to callables
        """
        return self.tools

    def register_tool(self, name: str, handler: Callable) -> None:
        """
        Register a new tool handler.
        
        Args:
            name: The name of the tool
            handler: The callable that handles tool execution
        """
        self.tools[name] = handler

    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool by name.
        
        Args:
            name: The name of the tool to unregister
            
        Returns:
            True if the tool was removed, False if it didn't exist
        """
        if name in self.tools:
            del self.tools[name]
            return True
        return False

    def get_state(self) -> ReverseDocumentState:
        """
        Get the current processing state.
        
        Returns:
            The current ReverseDocumentState
        """
        return self.state

    def set_state(self, state: ReverseDocumentState) -> None:
        """
        Set the processing state.
        
        Args:
            state: The new state to set
        """
        self.state = state

    def process_document_section(
        self,
        section_data: Dict[str, Any]
    ) -> DocumentSection:
        """
        Process a single document section.
        
        Creates a DocumentSection from the provided data and adds it
        to the current state.
        
        Args:
            section_data: Dictionary containing section information
            
        Returns:
            The created DocumentSection
            
        Raises:
            ValueError: If section_data is invalid
        """
        if not section_data:
            raise ValueError("Section data cannot be empty")

        if "heading" not in section_data:
            raise ValueError("Section data must contain 'heading'")

        section = DocumentSection.from_dict(section_data)
        self.state = add_document_section(self.state, section)
        
        return section

    def process_multiple_sections(
        self,
        sections_data: List[Dict[str, Any]]
    ) -> List[DocumentSection]:
        """
        Process multiple document sections.
        
        Args:
            sections_data: List of section data dictionaries
            
        Returns:
            List of created DocumentSection objects
        """
        results = []
        for section_data in sections_data:
            section = self.process_document_section(section_data)
            results.append(section)
        return results

    def handle_llm_response(
        self,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Handle a response from an LLM.
        
        Parses the response and extracts relevant information for
        document processing.
        
        Args:
            response: The LLM response text
            context: Optional context information
            
        Returns:
            Dictionary containing parsed response data
        """
        if not response:
            return {"success": False, "error": "Empty response"}

        # Process the response
        result = {
            "success": True,
            "response": response,
            "context": context or {}
        }

        # Update metadata in state
        metadata = dict(self.state.get("metadata", {}))
        metadata["last_llm_response"] = response[:100]  # Store first 100 chars
        self.state = update_state(self.state, metadata=metadata)

        return result

    def execute_tool(
        self,
        tool_name: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Execute a registered tool.
        
        Args:
            tool_name: Name of the tool to execute
            *args: Positional arguments for the tool
            **kwargs: Keyword arguments for the tool
            
        Returns:
            The result of the tool execution
            
        Raises:
            KeyError: If the tool is not registered
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' not registered")

        handler = self.tools[tool_name]
        return handler(*args, **kwargs)

    def advance_to_next_section(self) -> bool:
        """
        Advance to the next document section.
        
        Returns:
            True if there are more sections, False if completed
        """
        self.state = advance_section(self.state)
        return not self.state.get("completed", False)

    def complete_processing(
        self,
        error: Optional[str] = None
    ) -> ReverseDocumentState:
        """
        Mark the processing as complete.
        
        Args:
            error: Optional error message if processing failed
            
        Returns:
            The final state
        """
        self.state = mark_completed(self.state, error=error)
        return self.state

    def get_document_sections(self) -> List[Dict[str, Any]]:
        """
        Get all document sections from the current state.
        
        Returns:
            List of document section dictionaries
        """
        return list(self.state.get("document_sections", []))

    def get_section_count(self) -> int:
        """
        Get the count of document sections.
        
        Returns:
            Number of sections in the state
        """
        return len(self.state.get("document_sections", []))

    def is_completed(self) -> bool:
        """
        Check if processing is completed.
        
        Returns:
            True if completed, False otherwise
        """
        return self.state.get("completed", False)

    def get_error(self) -> Optional[str]:
        """
        Get any error message from the state.
        
        Returns:
            Error message string or None
        """
        return self.state.get("error")

    def reset(self, tech_spec: Optional[str] = None) -> None:
        """
        Reset the helper to initial state.
        
        Args:
            tech_spec: Optional new tech spec to use
        """
        spec = tech_spec if tech_spec is not None else self.state.get("tech_spec", "")
        self.state = get_state(tech_spec=spec)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the helper state to a dictionary.
        
        Returns:
            Dictionary representation of the current state
        """
        return dict(self.state)

    @classmethod
    def from_state(
        cls,
        state: ReverseDocumentState,
        tools: Optional[Dict[str, Callable]] = None,
        llm_handler: Optional[Callable] = None
    ) -> "ReverseDocumentHelper":
        """
        Create a helper instance from an existing state.
        
        Args:
            state: The state to initialize from
            tools: Optional tools dictionary
            llm_handler: Optional LLM handler
            
        Returns:
            New ReverseDocumentHelper instance
        """
        helper = cls(tools=tools, llm_handler=llm_handler)
        helper.state = state
        return helper
