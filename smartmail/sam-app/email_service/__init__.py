"""Public integration exports for email_service."""

from .inbound_rule_router import InboundRuleRouterError, route_inbound_with_rule_engine
from .rule_engine import RuleEngineOutput
from .rule_engine_orchestrator import (
    RuleEngineOrchestratorError,
    apply_rule_engine_plan_update,
    run_rule_engine_for_week,
)
from .rule_engine_state import RuleEngineStateError, load_rule_state, update_rule_state

__all__ = [
    "InboundRuleRouterError",
    "RuleEngineOrchestratorError",
    "RuleEngineOutput",
    "RuleEngineStateError",
    "apply_rule_engine_plan_update",
    "load_rule_state",
    "route_inbound_with_rule_engine",
    "run_rule_engine_for_week",
    "update_rule_state",
]
