"""Error types for the unified memory refresh workflow."""


class MemoryRefreshError(Exception):
    """Raised when the unified memory refresh fails."""


class MemoryRefreshPromptError(MemoryRefreshError):
    """Raised when the prompt construction fails."""
