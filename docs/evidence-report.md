# Engineering Evidence Report

Generated at: 2026-06-01 06:13:30 UTC

Overall status: **PASS**

This report is a command-backed project evidence artifact. It focuses on reproducible engineering signals instead of screenshots or subjective demo claims.

## Quality Gate

| Gate | Result | Evidence |
| --- | --- | --- |
| Python unit and integration tests | PASS | `python -m pytest -q` -> 460 tests passed in 10.89s; warnings: 0. |
| Golden replay evals | PASS | `python -m core.eval.runner --suite golden` -> 50/50 replay cases passed; failed: 0. |
| Benchmark dry-run selection | PASS | `python scripts/generate_benchmark.py --dry-run --max-cases 4` -> 4 benchmark cases selected: benchmark_dm_actor_runtime_turn (1 steps), benchmark_gatekeeper_generation_turn (1 steps), benchmark_mechanics_physics_turn (1 steps), benchmark_physical_action_turn (1 steps). |
| Web UI tests | PASS | `npm test` -> 285/285 Jest tests passed. |

## Runtime Claims

| Claim | What proves it | Relevant code/tests |
| --- | --- | --- |
| Scoped perception | Agents receive actor-specific views rather than raw global state. | `core/actors/builders.py`, `core/actors/visibility.py`, `tests/test_actor_view_builder.py`, `tests/test_visibility_rules.py` |
| Deterministic state mutation | LLM-facing nodes can propose intent, while typed events and event drain own authoritative state writes. | `core/events/models.py`, `core/events/apply.py`, `core/graph/nodes/event_drain.py`, `tests/test_event_drain.py`, `tests/test_actor_invocation_node.py` |
| Replayable behavior | Golden YAML cases validate routing, visibility, memory, item transfer, traps, and scenario endings without live model calls. | `evals/golden/`, `core/eval/runner.py`, `tests/test_golden_suite_smoke.py` |
| Operator observability | Runtime decisions and state changes are inspectable through route trace, payload summaries, and state diff. | `web_ui/director-trace.js`, `web_ui/state-diff-renderer.js`, `web_ui/tests/app.test.js` |
| Full-stack delivery | The same service path powers API, browser UI, eval runner, and benchmark tooling. | `server.py`, `core/application/game_service.py`, `web_ui/`, `scripts/generate_benchmark.py` |

## Why This Matters

This project does not claim to be a complete game or a model-training system. It demonstrates that LLM agents can be placed inside an engineering runtime with scoped context, deterministic state commits, replayable evals, and observable execution traces.

The key engineering claim is:

> The game-like scenario is the stress test. The reusable asset is the controlled Agent runtime and its quality gate.

## Reproduce

Run the full evidence report:

```bash
python scripts/generate_evidence_report.py
```

Run the core gate directly:

```bash
make check
```

Run UI tests after installing Node dependencies:

```bash
npm install
npm test
```
