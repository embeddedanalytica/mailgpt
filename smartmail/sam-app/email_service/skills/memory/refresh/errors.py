"""Exceptions for the memory refresh workflow."""


class MemoryRefreshPromptError(ValueError):
    """Raised when memory refresh prompt input is invalid."""


class MemoryRefreshError(Exception):
    """Raised when memory refresh generation fails."""

    def __init__(
        self,
        message: str,
        *,
        raw_response: str = "",
        cause_message: str = "",
    ) -> None:
        super().__init__(message)
        self.raw_response = str(raw_response or "")
        self.cause_message = str(cause_message or "")
