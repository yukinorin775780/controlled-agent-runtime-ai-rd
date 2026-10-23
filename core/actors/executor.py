from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.actors import ActorScopedMemoryProvider, build_actor_view
from core.actors.contracts import ReflectionRequest, reflection_request_from_dict, reflection_request_to_dict
from core.actors.registry import ActorRegistry
from core.actors.contracts import ActorRuntime, ActorDecision
from core.actors.retry import RetryPolicy, error_category, with_retry
from core.eval.telemetry import emit_telemetry
from core.events.models import DomainEvent, event_to_dict
from core.memory.compat import get_default_memory_service


FALLBACK_REASON_RUNTIME_MISSING = "runtime_missing"
FALLBACK_REASON_RUNTIME_FAILED = "runtime_failed"
REFLECTION_STATUS_PROCESSED = "processed"
REFLECTION_STATUS_SKIPPED = "skipped"
REFLECTION_SKIP_REASON_RUNTIME_MISSING = "runtime_missing"
REFLECTION_SKIP_REASON_RUNTIME_FAILED = "runtime_failed"


def _safe_get_runtime(registry: ActorRegistry, actor_id: str) -> ActorRuntime | None:
    if hasattr(registry, "try_get"):
        runtime = registry.try_get(actor_id)
    else:
        runtime = None
    if runtime is not None:
        return runtime
    try:
        return registry.get(actor_id)
    except KeyError:
        return None


async def invoke_actor_runtime(
    *,
    state: Dict[str, Any],
    actor_id: str,
    registry: ActorRegistry,
    retry_policy: RetryPolicy = RetryPolicy(),
) -> Tuple[Dict[str, Any], List[DomainEvent], List[ReflectionRequest]]:
    runtime = _safe_get_runtime(registry, actor_id)
    if runtime is None:
        return {
            "mode": "fallback",
            "actor_id": actor_id,
            "reason": FALLBACK_REASON_RUNTIME_MISSING,
        }, [], []

    try:
        memory_service = get_default_memory_service()
        actor_view = build_actor_view(
            state,
            actor_id,
            memory_provider=ActorScopedMemoryProvider(memory_service.retriever),
        )
        decision = await with_retry(lambda: runtime.decide(actor_view), component="actor_decide", policy=retry_policy)
        if not isinstance(decision, ActorDecision) or decision.actor_id != actor_id:
            raise ValueError("Runtime must return an ActorDecision for the scoped actor.")
    except Exception as exc:  # plugin boundary: preserve fallback for all classified failures
        emit_telemetry("execution_error", component="actor_executor", actor_id=actor_id,
                       error_type=type(exc).__name__, category=error_category(exc), retrying=False)
        return {
            "mode": "fallback",
            "actor_id": actor_id,
            "reason": FALLBACK_REASON_RUNTIME_FAILED,
            "error_type": exc.__class__.__name__,
            "error_category": error_category(exc),
        }, [], []

    visible_flags = getattr(actor_view, "visible_flags", {})
    visible_environment_objects = getattr(actor_view, "visible_environment_objects", {})
    if not isinstance(visible_flags, dict):
        visible_flags = {}
    if not isinstance(visible_environment_objects, dict):
        visible_environment_objects = {}

    decision_dict = {
        "mode": "runtime",
        "actor_id": decision.actor_id,
        "kind": decision.kind,
        "spoken_text": decision.spoken_text,
        "thought_summary": decision.thought_summary,
        "physical_action": dict(decision.physical_action or {}) if decision.physical_action else None,
        "visible_flag_keys": sorted(str(key) for key in visible_flags.keys()),
        "visible_environment_object_ids": sorted(
            str(key) for key in visible_environment_objects.keys()
        ),
    }
    return decision_dict, list(decision.emitted_events), list(decision.requested_reflections)


async def process_reflection_queue(
    *,
    state: Dict[str, Any],
    registry: ActorRegistry,
    max_items: int = 1,
    retry_policy: RetryPolicy = RetryPolicy(),
) -> Dict[str, Any]:
    queue_raw = list(state.get("reflection_queue") or [])
    if not queue_raw:
        return {}

    pending_events = list(state.get("pending_events") or [])
    max_batch_size = max(1, int(max_items or 1))
    handled_count = 0
    normalized_requests: List[ReflectionRequest] = []
    for raw_request in queue_raw:
        if isinstance(raw_request, ReflectionRequest):
            normalized_requests.append(raw_request)
            continue
        if not isinstance(raw_request, dict):
            continue
        normalized_requests.append(reflection_request_from_dict(raw_request))

    normalized_requests.sort(
        key=lambda item: -int(item.priority or 0),
    )
    queue_length_before = len(normalized_requests)
    remaining_requests: List[ReflectionRequest] = []
    telemetry_records: List[Dict[str, Any]] = []

    for request in normalized_requests:
        if handled_count >= max_batch_size:
            remaining_requests.append(request)
            continue
        runtime = _safe_get_runtime(registry, request.actor_id)
        if runtime is None:
            remaining_requests.append(request)
            handled_count += 1
            telemetry_records.append(
                {
                    "actor_id": request.actor_id,
                    "reason": request.reason,
                    "status": REFLECTION_STATUS_SKIPPED,
                    "skip_reason": REFLECTION_SKIP_REASON_RUNTIME_MISSING,
                    "source_turn": int(request.source_turn or 0),
                    "emitted_event_count": 0,
                }
            )
            continue
        try:
            events = await with_retry(lambda: runtime.reflect(request), component="actor_reflect", policy=retry_policy)
        except Exception as exc:  # reflection extension boundary, classified by with_retry
            remaining_requests.append(request)
            handled_count += 1
            telemetry_records.append(
                {
                    "actor_id": request.actor_id,
                    "reason": request.reason,
                    "status": REFLECTION_STATUS_SKIPPED,
                    "skip_reason": REFLECTION_SKIP_REASON_RUNTIME_FAILED,
                    "source_turn": int(request.source_turn or 0),
                    "emitted_event_count": 0,
                    "error_type": exc.__class__.__name__,
                    "error_category": error_category(exc),
                }
            )
            continue
        pending_events.extend(event_to_dict(item) for item in events)
        handled_count += 1
        telemetry_records.append(
            {
                "actor_id": request.actor_id,
                "reason": request.reason,
                "status": REFLECTION_STATUS_PROCESSED,
                "skip_reason": "",
                "source_turn": int(request.source_turn or 0),
                "emitted_event_count": len(events),
            }
        )

    remaining = [reflection_request_to_dict(item) for item in remaining_requests]
    queue_length_after = len(remaining)
    for record in telemetry_records:
        emit_telemetry(
            "reflection_processed",
            actor_id=record["actor_id"],
            reason=record["reason"],
            status=record["status"],
            skip_reason=record["skip_reason"],
            source_turn=record["source_turn"],
            emitted_event_count=record["emitted_event_count"],
            queue_length_before=queue_length_before,
            queue_length_after=queue_length_after,
            max_items=max_batch_size,
            error_type=record.get("error_type", ""),
            error_category=record.get("error_category", ""),
        )

    return {
        "reflection_queue": remaining,
        "pending_events": pending_events,
    }


def enqueue_reflection_requests(
    *,
    state: Dict[str, Any],
    requests: List[ReflectionRequest],
) -> List[Dict[str, Any]]:
    queue = list(state.get("reflection_queue") or [])
    queue.extend(reflection_request_to_dict(item) for item in requests)
    return queue
