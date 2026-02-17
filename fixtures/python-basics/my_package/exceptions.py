"""Custom exception classes."""


class MyError(Exception):
    """Base error for my_package.

    Args:
        message: The error message.
        code: An optional error code.
    """

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


class NotFoundError(MyError):
    """Raised when a resource is not found.

    Args:
        resource: The name of the resource that was not found.
    """

    def __init__(self, resource: str) -> None:
        super().__init__(f"Resource not found: {resource}", code=404)
        self.resource = resource


class ValidationError(MyError):
    """Raised when validation fails.

    Args:
        field: The field that failed validation.
        reason: The reason for the failure.
    """

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Validation failed for '{field}': {reason}", code=400)
        self.field = field
        self.reason = reason
