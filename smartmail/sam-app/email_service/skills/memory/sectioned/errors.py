"""Errors for sectioned memory refresh."""

from skills.memory.errors import MemoryRefreshError


class SectionedMemoryRefreshError(MemoryRefreshError):
    """Invalid LLM output or execution failure for sectioned memory refresh."""
