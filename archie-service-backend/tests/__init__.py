"""
Tests Package for archie-service-backend.

This package contains unit tests for the archie-service-backend service,
with a focus on the Figma integration feature implementation. Tests follow
the guidelines documented in ``archie-service-backend/docs/TEST.md``.

Testing Strategy
----------------

Unit tests in this package use faked dependencies to isolate external services:

* **Faked Repositories**: Test doubles for database operations, Secret Manager,
  Figma API calls, and configuration access
* **No Integration Tests**: Initial implementation focuses on unit-level testing
  with complete isolation from external dependencies
* **pytest Discovery**: This package structure enables automatic test discovery
  by pytest without requiring explicit test imports

Package Structure
-----------------

* ``tests.fakes``: Fake implementations of repository interfaces for testing
* ``tests.unit``: Unit tests for services and route handlers using faked dependencies

For detailed testing guidelines, test execution commands, and best practices,
refer to the TEST.md documentation in the archie-service-backend docs directory.
"""
