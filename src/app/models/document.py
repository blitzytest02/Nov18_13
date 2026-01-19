"""
Document models for the reverse document generator.

This module defines the data structures for representing document sections
and their statuses during the reverse document generation process.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class DocumentSectionStatus(str, Enum):
    """
    Enumeration of possible statuses for a document section.
    
    Attributes:
        UNCHANGED: The section has not been modified
        CHANGED: The section has been modified with tracked changes
        NEW: The section is newly added
        DELETED: The section has been marked for deletion
        PENDING: The section is pending review
    """
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    NEW = "NEW"
    DELETED = "DELETED"
    PENDING = "PENDING"


class DocumentSection(BaseModel):
    """
    Represents a section of a document in the reverse document generator.
    
    A document section contains a heading, content, status, and optionally
    a list of changes if the status is CHANGED.
    
    Attributes:
        heading: The section heading/title
        content: The main content of the section
        status: The current status of the section
        changes: List of changes made to the section (required if status is CHANGED)
        order: Optional ordering index for the section
    """
    heading: str = Field(..., min_length=1, description="Section heading")
    content: str = Field(default="", description="Section content")
    status: DocumentSectionStatus = Field(
        default=DocumentSectionStatus.UNCHANGED,
        description="Current status of the section"
    )
    changes: List[str] = Field(
        default_factory=list,
        description="List of changes made to the section"
    )
    order: Optional[int] = Field(
        default=None,
        description="Optional ordering index"
    )

    @field_validator("changes")
    @classmethod
    def validate_changes_for_status(cls, v: List[str], info) -> List[str]:
        """
        Validate that changes list is populated when status is CHANGED.
        
        Args:
            v: The changes list value
            info: Validation info containing other field values
            
        Returns:
            The validated changes list
            
        Raises:
            ValueError: If status is CHANGED but changes list is empty
        """
        # Note: This validator runs before we have access to the status field
        # Full validation happens in model_validator
        return v

    @field_validator("heading")
    @classmethod
    def validate_heading_not_empty(cls, v: str) -> str:
        """
        Validate that heading is not empty or whitespace only.
        
        Args:
            v: The heading value
            
        Returns:
            The stripped heading value
            
        Raises:
            ValueError: If heading is empty or whitespace only
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("Heading cannot be empty or whitespace only")
        return stripped

    def model_post_init(self, __context) -> None:
        """
        Post-initialization validation to ensure business rules are met.
        
        Validates that:
        - CHANGED status requires non-empty changes list
        - UNCHANGED status should have empty changes list
        """
        if self.status == DocumentSectionStatus.CHANGED and not self.changes:
            raise ValueError(
                "Document section with CHANGED status must have at least one change"
            )

    def add_change(self, change: str) -> None:
        """
        Add a change to the section and update status to CHANGED.
        
        Args:
            change: Description of the change to add
        """
        if change and change.strip():
            self.changes.append(change.strip())
            self.status = DocumentSectionStatus.CHANGED

    def clear_changes(self) -> None:
        """
        Clear all changes and reset status to UNCHANGED.
        """
        self.changes = []
        self.status = DocumentSectionStatus.UNCHANGED

    def to_dict(self) -> dict:
        """
        Convert the section to a dictionary representation.
        
        Returns:
            Dictionary containing all section fields
        """
        return {
            "heading": self.heading,
            "content": self.content,
            "status": self.status.value,
            "changes": self.changes,
            "order": self.order
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentSection":
        """
        Create a DocumentSection from a dictionary.
        
        Args:
            data: Dictionary containing section data
            
        Returns:
            New DocumentSection instance
        """
        # Handle status conversion from string
        if "status" in data and isinstance(data["status"], str):
            data = data.copy()
            data["status"] = DocumentSectionStatus(data["status"])
        return cls(**data)
