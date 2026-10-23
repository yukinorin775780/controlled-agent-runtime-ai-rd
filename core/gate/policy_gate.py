from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


@dataclass(frozen=True)
class ScopedAgentView:
    """Authority supplied by trusted runtime code, never by a tool candidate."""

    actor_id: str
    allowed_tools: frozenset[str]
    visible_targets: frozenset[str] = frozenset()
    facts: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: Mapping[str, Any] = field(default_factory=dict)
    target: str = ""


@dataclass(frozen=True)
class GateDecision:
    decision: Literal["allow", "deny"]
    reason: str
    matched_rule: str

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


class PolicyGate:
    """Pure authorization rules; no execution, state writes, or model calls."""

    def evaluate(self, view: ScopedAgentView, call: ToolCall) -> GateDecision:
        if not view.actor_id or call.name not in view.allowed_tools:
            return GateDecision("deny", "Tool is outside the actor's scope.", "default_deny")
        if call.target and call.target not in view.visible_targets:
            return GateDecision("deny", "Target is outside the scoped view.", "target_scope")
        facts = view.facts
        if call.name == "combat_action":
            if facts.get("combat_active") and facts.get("active_block") and view.actor_id not in facts["active_block"]:
                return GateDecision("deny", "Actor is outside the active turn block.", "active_turn")
        elif call.name == "gatekeeper_loot":
            if not (facts.get("hazard_lab") and facts.get("gatekeeper_source") and facts.get("gatekeeper_defeated")):
                return GateDecision("deny", "Gatekeeper loot requires a confirmed defeat in Hazard Lab.", "gatekeeper_defeated")
        elif call.name == "consume_item":
            text = str(facts.get("user_input") or "").lower()
            markers = ("喝", "喝下", "服用", "使用治疗药水", "用治疗药水", "治疗药水", "药水", "drink", "potion", "use healing")
            if str(facts.get("intent") or "").lower() not in {"consume", "use_item"} and not any(m in text for m in markers):
                return GateDecision("deny", "Item consumption requires an explicit user request.", "explicit_item_use")
        elif call.name == "publish_policy_patch":
            if not all(isinstance(call.args.get(k), str) and call.args[k].strip() for k in ("patch_id", "eval_suite", "rollout")):
                return GateDecision("deny", "patch_id, eval_suite and rollout must be nonempty strings.", "publish_schema")
            if call.args["rollout"] != "staged":
                return GateDecision("deny", "Only staged rollout is permitted.", "staged_rollout")
            if facts.get("eval_passed") is not True or call.args["eval_suite"] != facts.get("eval_suite"):
                return GateDecision("deny", "No passing backend eval evidence for the requested suite.", "eval_evidence")
        elif call.name == "ticket_search":
            if call.args.get("output_scope") != "public_kb_candidate" or call.args.get("window") != "24h":
                return GateDecision("deny", "Search requires a 24h public KB candidate scope.", "retrieval_scope")
        elif call.name == "audit_log_write":
            if not isinstance(call.args.get("release_id"), str) or not call.args["release_id"].strip():
                return GateDecision("deny", "A release_id is required.", "audit_schema")
        else:
            # A caller cannot authorize an unimplemented tool merely by listing it.
            return GateDecision("deny", "No registered rule for this tool.", "default_deny")
        return GateDecision("allow", "Scope and registered preconditions passed.", call.name)


policy_gate = PolicyGate()
