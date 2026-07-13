"""
src/exceptions/common.py

Shared HTTPException subclasses used across routers. Each carries a stable
``error_code`` (for the frontend to branch on) plus a human ``message``.

Detail shape is always:  {"error_code": "...", "message": "..."}
so the frontend can read response.detail.error_code / .message uniformly.
"""

from fastapi import HTTPException


class AppException(HTTPException):
    """Base: sets detail to {error_code, message}."""
    def __init__(self, status_code: int, error_code: str, message: str):
        super().__init__(status_code=status_code,
                         detail={"error_code": error_code, "message": message})


class EntityNotFound(AppException):
    def __init__(self, entity: str, entity_id):
        super().__init__(404, f"{entity}_not_found",
                         f"{entity.replace('_', ' ').title()} {entity_id} was not found.")


class CrossCompanyAccess(AppException):
    def __init__(self, entity: str = "resource"):
        super().__init__(403, "cross_company_access",
                         f"This {entity} belongs to another company.")


class DuplicateEntity(AppException):
    def __init__(self, entity: str, field: str, value):
        super().__init__(409, f"{entity}_duplicate",
                         f"A {entity.replace('_', ' ')} with {field}='{value}' already exists.")


class ValidationFailed(AppException):
    def __init__(self, message: str):
        super().__init__(400, "validation_failed", message)
