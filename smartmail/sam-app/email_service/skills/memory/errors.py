"""Shared error types for memory refresh workflows."""


class MemoryRefreshError(Exception):
    """Raised when the memory refresh fails."""

    def __init__(self, message: str = "", *, raw_response: str = "", cause_message: str = ""):
        super().__init__(message)
        self.raw_response = raw_response
        self.cause_message = cause_message


class MemoryRefreshPromptError(MemoryRefreshError):
    """Raised when the prompt construction fails."""
