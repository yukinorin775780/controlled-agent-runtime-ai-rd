import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.gate.policy_gate import PolicyGate, ScopedAgentView, ToolCall
from core.actors.retry import RetryPolicy, with_retry
from core.graph.graph_routers import route_after_narration
from core.application.checkpoint_lock import checkpoint_lock
from core.tools.npc_tools import check_target_inventory, inventory_scope


def test_allow_deny_default_deny():
    gate = PolicyGate()
    view = ScopedAgentView("ops", frozenset({"publish_policy_patch"}), facts={"eval_passed": True, "eval_suite": "golden"})
    call = ToolCall("publish_policy_patch", {"patch_id": "a", "eval_suite": "golden", "rollout": "staged"})
    assert gate.evaluate(view, call).allowed
    assert not gate.evaluate(ScopedAgentView("ops", view.allowed_tools), call).allowed
    assert gate.evaluate(view, ToolCall("unknown")).matched_rule == "default_deny"
    assert gate.evaluate(ScopedAgentView("ops", frozenset({"unknown"})), ToolCall("unknown")).matched_rule == "default_deny"


def test_schema_target_and_turn_rules():
    gate = PolicyGate()
    assert gate.evaluate(ScopedAgentView("ops", frozenset({"publish_policy_patch"})), ToolCall("publish_policy_patch")).matched_rule == "publish_schema"
    assert gate.evaluate(ScopedAgentView("ops", frozenset({"combat_action"})), ToolCall("combat_action", target="hidden")).matched_rule == "target_scope"
    assert not gate.evaluate(ScopedAgentView("scout", frozenset({"combat_action"}), facts={"combat_active": True, "active_block": ["enemy"]}), ToolCall("combat_action")).allowed


def test_gate_api_uses_server_roles_and_fails_closed_without_evidence():
    import server
    with patch("core.gate.workbench.eval_facts", return_value={"eval_passed": False, "eval_suite": "golden"}):
        client = TestClient(server.app)
        reviewer = client.post("/api/gate/evaluate", json={"actor_id": "reviewer_agent", "tool_name": "publish_policy_patch"}).json()
        assert reviewer["policy_gate"]["decision"] == "deny"
        research = client.post("/api/gate/evaluate", json={"actor_id": "research_agent", "tool_name": "ticket_search", "args": {"window": "24h", "output_scope": "public_kb_candidate"}}).json()
        assert research["policy_gate"]["decision"] == "allow"
        assert research["domain_events"] == []
        ops = client.post("/api/gate/evaluate", json={"actor_id": "ops_agent", "tool_name": "publish_policy_patch", "args": {"patch_id": "a", "eval_suite": "golden", "rollout": "staged", "eval_passed": True}}).json()
        assert ops["policy_gate"]["matched_rule"] == "eval_evidence"


def test_routing_is_deterministic_and_keeps_priority():
    ordinary = {"latest_roll": {"result": {"raw_roll": 10}}}
    assert {route_after_narration(ordinary) for _ in range(100)} == {"__end__"}
    assert route_after_narration({**ordinary, "speaker_queue": ["analyst"]}) == "generation"
    assert route_after_narration({"latest_roll": {"result": {"raw_roll": 20}}}) == "generation"


def test_retry_backoff_and_nontransient_failure():
    async def run():
        calls = 0
        async def transient():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise TimeoutError("temporary")
            return "ok"
        with patch("core.actors.retry.asyncio.sleep") as sleep:
            assert await with_retry(transient, component="test", policy=RetryPolicy(base_delay=0.5)) == "ok"
            assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1.0]
        async def invalid():
            raise ValueError("invalid")
        with patch("core.actors.retry.asyncio.sleep") as sleep:
            with pytest.raises(ValueError):
                await with_retry(invalid, component="test")
            sleep.assert_not_called()
    asyncio.run(run())


def test_checkpoint_serializes_full_transactions_and_cancellation(tmp_path):
    async def run():
        trace = []
        path = str(tmp_path / "state.db")
        async def transaction(i):
            async with checkpoint_lock(path):
                trace.append((i, "read"))
                await asyncio.sleep(0.02)
                trace.append((i, "write"))
        await asyncio.gather(transaction(1), transaction(2))
        assert trace == [(1, "read"), (1, "write"), (2, "read"), (2, "write")]
        async with checkpoint_lock(path):
            waiter = asyncio.create_task(transaction(3))
            await asyncio.sleep(0.02)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
        await transaction(4)
    asyncio.run(run())


def test_inventory_tool_requires_bound_scope():
    assert "Denied" in check_target_inventory.invoke({"target_id": "player", "item_keyword": "gold"})
    with inventory_scope({"player": {"gold": 3}}):
        assert "player 拥有 3 个 gold" in check_target_inventory.invoke({"target_id": "player", "item_keyword": "gold"})
        assert "Denied" in check_target_inventory.invoke({"target_id": "other", "item_keyword": "gold"})


def test_keyword_classifier_interface_is_used(monkeypatch):
    from core.llm.dm import analyze_intent
    class Fake:
        def classify(self, text, **context):
            return {"action_type": "CHAT", "reason": "injected"}
    monkeypatch.setattr("core.intent._default_classifier", Fake())
    assert analyze_intent("anything")["reason"] == "injected"


def test_backend_eval_evidence_rejects_missing_stale_and_incomplete(tmp_path, monkeypatch):
    import json
    import core.gate.workbench as workbench
    monkeypatch.setattr(workbench, "ROOT", tmp_path)
    monkeypatch.setattr(workbench, "source_digest", lambda: "current")
    assert workbench.eval_facts()["eval_passed"] is False
    (tmp_path / "artifacts").mkdir()
    path = tmp_path / "artifacts/gate-evidence.json"
    evidence = {"ok": True, "suite": "golden", "case_count": 50, "passed_count": 50, "source_digest": "old"}
    path.write_text(json.dumps(evidence))
    assert workbench.eval_facts()["eval_passed"] is False
    evidence["source_digest"] = "current"
    path.write_text(json.dumps(evidence))
    assert workbench.eval_facts()["eval_passed"] is True
    evidence["passed_count"] = 49
    path.write_text(json.dumps(evidence))
    assert workbench.eval_facts()["eval_passed"] is False
    path.write_text("invalid json")
    assert workbench.eval_facts()["eval_passed"] is False


def test_retry_exhaustion_has_structured_errors_without_secret_message():
    from core.eval.telemetry import InMemoryTelemetrySink, telemetry_scope
    sink = InMemoryTelemetrySink()
    async def run():
        async def failed():
            raise ConnectionError("secret must not be copied")
        with telemetry_scope(sink), patch("core.actors.retry.asyncio.sleep"):
            with pytest.raises(ConnectionError):
                await with_retry(failed, component="unit", policy=RetryPolicy())
    asyncio.run(run())
    records = [e["payload"] for e in sink.events if e["event_name"] == "execution_error"]
    assert [r["attempt"] for r in records] == [1, 2, 3]
    assert [r["retrying"] for r in records] == [True, True, False]
    assert all(r["category"] == "transient" for r in records)
    assert "secret" not in str(records)


def test_retry_propagates_cancellation():
    async def cancelled():
        raise asyncio.CancelledError()
    async def run():
        with patch("core.actors.retry.asyncio.sleep") as sleep:
            with pytest.raises(asyncio.CancelledError):
                await with_retry(cancelled, component="unit")
            sleep.assert_not_called()
    asyncio.run(run())


def test_cors_default_denies_remote_origins():
    import server
    client = TestClient(server.app)
    headers = {"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"}
    assert client.options("/api/gate/evaluate", headers=headers).status_code == 400
    headers["Origin"] = "http://localhost:8000"
    response = client.options("/api/gate/evaluate", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8000"


def test_invalid_actor_contract_uses_safe_fallback():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from core.actors.executor import invoke_actor_runtime
    runtime = SimpleNamespace(decide=AsyncMock(return_value={"actor_id": "other"}))
    registry = SimpleNamespace(try_get=lambda actor_id: runtime)
    with patch("core.actors.executor.get_default_memory_service", return_value=SimpleNamespace(retriever=Mock())), patch("core.actors.executor.build_actor_view", return_value=object()):
        decision, events, reflections = asyncio.run(invoke_actor_runtime(state={}, actor_id="analyst", registry=registry))
    assert decision["mode"] == "fallback"
    assert decision["error_category"] == "invalid_contract"
    assert events == reflections == []
