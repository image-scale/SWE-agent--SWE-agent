from __future__ import annotations


class FormatError(Exception):
    """Exception raised when there's a format error in parsing."""
    pass


class FunctionCallingFormatError(FormatError):
    """Exception raised when there's a format error in function calling."""

    def __init__(self, message: str, error_type: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.extra_info = {"error_type": error_type}
