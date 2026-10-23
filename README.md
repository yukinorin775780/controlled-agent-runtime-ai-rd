# Controlled Agent Runtime Workbench

[![checks](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd/actions/workflows/checks.yml/badge.svg)](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd/actions/workflows/checks.yml)

## Origin and scope

Extracted from [BG3-LLM-Agent](https://github.com/yukinorin775780/BG3-LLM-Agent), where the original iteration history lives. The sibling projects are [the workbench](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd) and [the simulation runtime](https://github.com/yukinorin775780/controlled-agent-sim-runtime).

The core is a controlled agent runtime. Hazard Lab is its stateful stress-test scenario. Ops / Research / Reviewer are a **presentation-layer reframing** of role boundaries. Their workbench candidates now call the real backend PolicyGate; the business connectors themselves are not implemented. Gate evaluation does not publish anything, write an audit log, or commit DomainEvents. The role mask labels illustrate intended fields, not integrations with real customer data. Historical screenshots below predate this correction.

## Evidence and evaluation limits

The linked CI workflow runs pytest, golden replay, npm tests, Ruff and focused mypy checks. Its badge is the public execution record; local results do not imply a successful remote run. These local changes must be pushed before GitHub can verify them.

- **50/50 golden eval** means deterministic logical replay with scripted model responses and controlled dice/time. It checks regression of logic, visibility and state commits, not live model quality.
- **Real LLM benchmark** has four cases; it is separate, requires credentials, and measures behavior only within those cases. A benchmark dry-run only selects cases and proves no model quality result.
- Routing is deterministic for the same state. Live language generation and ordinary game dice are not globally deterministic; golden replay explicitly supplies their outputs.

## Reproducible local setup

Python 3.11+ on Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
npm ci
pytest -q
python -m core.eval.runner --suite golden
npm test
python server.py
```

Optional Chroma/Streamlit dependencies are listed in `requirements-optional.txt`. The default memory backend degrades to the existing fallback when Chroma is absent.

For a containerized backend and browser UI:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000/web_ui/. The workbench and rule evaluation need no live model key; open-ended chat requires `BAILIAN_API_KEY` and the matching base URL. SQLite data persists in the named Docker volume.

## Backend gate verification

```bash
curl -s http://127.0.0.1:8000/api/gate/evaluate -H 'Content-Type: application/json' -d '{"actor_id":"research_agent","tool_name":"ticket_search","args":{"window":"24h","output_scope":"public_kb_candidate"}}'
```

This returns `allow` with `reason` and `matched_rule`; changing the role to `reviewer_agent` denies the search. Publishing candidates default to `deny` until `python scripts/generate_gate_evidence.py` records a complete passing golden suite for the current source digest. Changes to source invalidate that evidence. This evidence is a local logic regression gate, not approval for a real production release.

See [engineering boundaries](docs/engineering-boundaries.md) for intent parsing, retry safety and single-machine concurrency limits.

## Architecture and implementation

The simulation uses GameService → LangGraph → ActorView / mechanics → typed events and legacy physics → checkpoint / UI. Some legacy mechanics still mutate domain snapshots directly; not every effect is event-sourced. The business workbench is a separate presentation of candidate evaluation:

```text
Sample candidate → POST /api/gate/evaluate → backend ScopedAgentView → PolicyGate → decision / reason / matched_rule
```

No business tool is executed by this endpoint. Existing screenshots and `docs/evidence-report.md` are historical; use current API responses and CI runs for evidence. The current local verification is documented in [optimization verification](docs/optimization-verification.md).

## Repository Map

```text
core/application/      service boundary shared by API, UI, evals, and benchmarks
core/graph/            LangGraph state machine, routing, and node orchestration
core/actors/           ActorView, ActorRuntime, registry, visibility contracts
core/events/           typed events, apply path, event store
core/memory/           scoped memory, retrieval, distillation, service layer
core/eval/             golden replay runner, assertions, telemetry, reports
evals/golden/          deterministic replay cases
evals/benchmark/       benchmark cases for model-backed runs
web_ui/                Runtime Workbench, Director Timeline, payload inspector, state diff
docs/                  walkthrough, architecture, case study, evidence report
```

## Project Boundary

This is not a model-training project and not a content-volume showcase. The scenario preview is intentionally small. The project focuses on the runtime infrastructure needed to make agent behavior bounded, observable, replayable, and testable.
