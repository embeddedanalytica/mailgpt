"""Exceptions for the response-generation workflow."""


class ResponseGenerationContractError(ValueError):
    """Raised when response-generation input/output violates the bounded contract."""


class ResponseGenerationProposalError(Exception):
    """Raised when the response-generation workflow cannot produce a valid payload."""
