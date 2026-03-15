"""Exceptions for planner contracts and execution."""


class PlannerContractError(ValueError):
    """Raised when planner input/output violates the bounded contract."""


class PlannerRepairError(ValueError):
    """Raised when deterministic planner repair cannot be evaluated safely."""


class PlannerProposalError(Exception):
    """Raised when planner generation fails."""
