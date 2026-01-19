"""
Test fixtures for DocumentSection models.

This module provides factory functions and sample data for testing
document-related functionality in the reverse document generator.
"""

from typing import Any, Dict, List, Optional

import factory
from faker import Faker

from src.app.models.document import DocumentSection, DocumentSectionStatus


fake = Faker()


class DocumentSectionFactory(factory.Factory):
    """
    Factory for creating DocumentSection test instances.
    
    Usage:
        >>> section = DocumentSectionFactory()
        >>> section_changed = DocumentSectionFactory(status=DocumentSectionStatus.CHANGED, changes=["Change 1"])
    """
    
    class Meta:
        model = DocumentSection
    
    heading = factory.LazyAttribute(lambda x: fake.sentence(nb_words=4))
    content = factory.LazyAttribute(lambda x: fake.paragraph(nb_sentences=3))
    status = DocumentSectionStatus.UNCHANGED
    changes = factory.LazyAttribute(lambda x: [])
    order = factory.Sequence(lambda n: n)


def create_sample_section(
    heading: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[DocumentSectionStatus] = None,
    changes: Optional[List[str]] = None,
    order: Optional[int] = None
) -> DocumentSection:
    """
    Create a sample DocumentSection with optional overrides.
    
    Args:
        heading: Optional heading override
        content: Optional content override
        status: Optional status override
        changes: Optional changes list override
        order: Optional order override
        
    Returns:
        DocumentSection instance
    """
    return DocumentSectionFactory(
        heading=heading or fake.sentence(nb_words=4),
        content=content or fake.paragraph(nb_sentences=3),
        status=status or DocumentSectionStatus.UNCHANGED,
        changes=changes or [],
        order=order
    )


def create_changed_section(
    heading: Optional[str] = None,
    changes: Optional[List[str]] = None
) -> DocumentSection:
    """
    Create a DocumentSection with CHANGED status and changes.
    
    Args:
        heading: Optional heading override
        changes: Optional list of changes (will generate if not provided)
        
    Returns:
        DocumentSection with CHANGED status
    """
    changes_list = changes or [fake.sentence() for _ in range(fake.random_int(1, 3))]
    return DocumentSectionFactory(
        heading=heading or fake.sentence(nb_words=4),
        status=DocumentSectionStatus.CHANGED,
        changes=changes_list
    )


def create_new_section(heading: Optional[str] = None) -> DocumentSection:
    """
    Create a DocumentSection with NEW status.
    
    Args:
        heading: Optional heading override
        
    Returns:
        DocumentSection with NEW status
    """
    return DocumentSectionFactory(
        heading=heading or fake.sentence(nb_words=4),
        status=DocumentSectionStatus.NEW
    )


def create_deleted_section(heading: Optional[str] = None) -> DocumentSection:
    """
    Create a DocumentSection with DELETED status.
    
    Args:
        heading: Optional heading override
        
    Returns:
        DocumentSection with DELETED status
    """
    return DocumentSectionFactory(
        heading=heading or fake.sentence(nb_words=4),
        status=DocumentSectionStatus.DELETED
    )


def create_section_dict(
    heading: str = "Test Heading",
    content: str = "Test content",
    status: str = "UNCHANGED",
    changes: Optional[List[str]] = None,
    order: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a dictionary representation of a document section.
    
    Useful for testing from_dict() and API endpoints.
    
    Args:
        heading: Section heading
        content: Section content
        status: Status string
        changes: List of changes
        order: Optional order
        
    Returns:
        Dictionary with section data
    """
    data = {
        "heading": heading,
        "content": content,
        "status": status,
        "changes": changes or []
    }
    if order is not None:
        data["order"] = order
    return data


def create_multiple_sections(count: int = 5) -> List[DocumentSection]:
    """
    Create multiple DocumentSection instances.
    
    Args:
        count: Number of sections to create
        
    Returns:
        List of DocumentSection instances
    """
    return [DocumentSectionFactory(order=i) for i in range(count)]


def create_mixed_status_sections() -> List[DocumentSection]:
    """
    Create a list of sections with various statuses.
    
    Returns:
        List of DocumentSection instances with different statuses
    """
    return [
        DocumentSectionFactory(status=DocumentSectionStatus.UNCHANGED, order=0),
        DocumentSectionFactory(
            status=DocumentSectionStatus.CHANGED,
            changes=["Modified content"],
            order=1
        ),
        DocumentSectionFactory(status=DocumentSectionStatus.NEW, order=2),
        DocumentSectionFactory(status=DocumentSectionStatus.DELETED, order=3),
        DocumentSectionFactory(status=DocumentSectionStatus.PENDING, order=4),
    ]


# Sample data for testing
SAMPLE_DOCUMENT_SECTION = {
    "heading": "Introduction",
    "content": "This is the introduction section of the document.",
    "status": "UNCHANGED",
    "changes": [],
    "order": 0
}

SAMPLE_CHANGED_SECTION = {
    "heading": "Requirements",
    "content": "Updated requirements section.",
    "status": "CHANGED",
    "changes": ["Added new requirement 1", "Updated requirement 2"],
    "order": 1
}

SAMPLE_SECTIONS_LIST = [
    SAMPLE_DOCUMENT_SECTION,
    SAMPLE_CHANGED_SECTION,
    {
        "heading": "Implementation",
        "content": "Implementation details.",
        "status": "NEW",
        "changes": [],
        "order": 2
    }
]

# Invalid data samples for testing error handling
INVALID_SECTION_EMPTY_HEADING = {
    "heading": "",
    "content": "Content",
    "status": "UNCHANGED"
}

INVALID_SECTION_MISSING_HEADING = {
    "content": "Content",
    "status": "UNCHANGED"
}

INVALID_SECTION_CHANGED_NO_CHANGES = {
    "heading": "Test",
    "content": "Content",
    "status": "CHANGED",
    "changes": []
}

INVALID_SECTION_INVALID_STATUS = {
    "heading": "Test",
    "content": "Content",
    "status": "INVALID_STATUS"
}
