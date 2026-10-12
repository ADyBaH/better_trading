class AppError(Exception):
    """Base class for application errors."""

    pass


class APIError(AppError):
    """Raised when an error occurs during API communication."""

    pass


class StorageError(AppError):
    """Raised when an error occurs during database operations."""

    pass
