"""Business role reframing: evaluates candidates, does not execute external tools."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from core.gate.policy_gate import ScopedAgentView, ToolCall, policy_gate

ROOT = Path(__file__).resolve().parents[2]
ROLE_TOOLS = {
    "ops_agent": frozenset({"eval_summary", "policy_diff_read", "publish_policy_patch"}),
    "research_agent": frozenset({"ticket_search", "kb_lookup", "semantic_cluster"}),
    "reviewer_agent": frozenset({"ci_status", "eval_summary", "audit_log_write"}),
}
MASKED_FIELDS = {
    "ops_agent": ["raw_user_pii", "billing_token", "private_escalation_notes"],
    "research_agent": ["account_id", "payment_context", "internal_owner_notes"],
    "reviewer_agent": ["deploy_token", "direct_publish_action"],
}


def source_digest() -> str:
    digest = hashlib.sha256()
    for folder in ("core", "evals/golden", "config", "characters"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                digest.update(str(path.relative_to(ROOT)).encode())
                digest.update(path.read_bytes())
    for name in ("server.py", "requirements.in", "requirements.lock", "scripts/generate_gate_evidence.py"):
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def eval_facts() -> dict[str, Any]:
    try:
        data = json.loads((ROOT / "artifacts/gate-evidence.json").read_text())
        passed = (data.get("ok") is True and data.get("suite") == "golden"
                  and data.get("case_count") == 50 and data.get("passed_count") == 50
                  and data.get("source_digest") == source_digest())
    except (OSError, ValueError, TypeError, AttributeError):
        passed = False
    return {"eval_passed": passed, "eval_suite": "golden"}


def evaluate_candidate(actor_id: str, call: ToolCall) -> dict[str, Any]:
    tools = ROLE_TOOLS.get(actor_id, frozenset())
    view = ScopedAgentView(actor_id, tools, facts=eval_facts())
    decision = policy_gate.evaluate(view, call)
    return {
        "intent": "TOOL_ORCHESTRATION", "route": "policy.evaluate",
        "selected_agent": actor_id,
        "scoped_agent_view": {"allowed_tools": sorted(tools),
                              "masked_fields": MASKED_FIELDS.get(actor_id, [])},
        "policy_gate": asdict(decision),
        "proposed_tool_call": {"name": call.name, "args": dict(call.args), "target": call.target},
        "domain_events": [],
        "execution": "evaluation_only",
    }
