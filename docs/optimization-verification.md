# Optimization verification — 2026-10-23

Local repository: `controlled-agent-runtime-ai-rd`. All changes are local; no GitHub push or remote CI execution was performed.

## Verified

| Check | Result |
| --- | --- |
| Python unit/regression tests | 473 passed |
| Golden deterministic replay | 50/50 passed |
| Browser unit/regression tests | 287 passed |
| Ruff (`core` and `server.py`) | passed |
| Focused mypy | 8 files passed, including executor and tool boundary |
| Dependency consistency | no broken requirements |
| Compose configuration | parsed successfully |
| Git whitespace check | passed |

Testing used Python 3.13.1 and Node 22.22.2 on macOS. CI remains configured for Python 3.11 and Node 20. Python dependency locking resolves universally for Python 3.11+. Tests and golden replay use explicit offline model doubles; this run makes no live-model quality claim.

The workbench backend was also checked over HTTP with curl independently of the browser: Research search `allow`; Reviewer publish `deny/default_deny`; Ops publish `allow` only after a passing source-bound golden evidence file. Browser verification showed the backend reason and no committed events. Frontend source contains sample requests, not preset gate decisions; unavailable backend responses display an unavailable state.

## Implemented outline items

- P0: standalone backend PolicyGate, real HTTP evaluation endpoint, workbench fetch integration, default-deny tests; shared mechanics turn/loot and explicit-consumption authorization extracted to the gate.
- P0: deterministic narration routing and round-robin idle speaker selection; obsolete replay patches removed; regression tests updated.
- P0: origin links, live CI links, explicit golden/live-benchmark distinction, business-role reframing boundaries and historical-evidence labels.
- P1: core debug output uses logging, bare container function annotations parameterized, DirectorView documentation corrected; empty physical-tool stub removed and inventory tool bound to scoped runtime data.
- P1: configurable retries with exponential backoff for safe proposals/model calls, structured categorized errors, cancellation propagation and invalid actor-contract fallback; state mutation is never automatically retried.
- P1: replaceable IntentClassifier interface, default keyword fast path and existing model fallback documented honestly.
- P2: Dockerfile/Compose, pinned direct and transitive dependencies, local-origin CORS defaults, full checkpoint transaction file locking and lint/type CI steps.
- Original BG3 repository: 3,188 tracked node_modules files removed from the index, ignore rule added, README links back to both maintained extractions.

## Remaining external verification

Docker engine started and Compose syntax passed. An actual build was attempted, but Docker Hub returned `insufficient_scope` while resolving the public Python base image. Public ECR and clean-credential Docker Hub downloads were attempted; required layers did not finish during verification. **No successful container build/start is claimed.** The Dockerfile supports `PYTHON_IMAGE` and `PIP_INDEX_URL` build arguments; Compose exposes `CONTROLLED_AGENT_PYTHON_IMAGE` and `CONTROLLED_AGENT_PIP_INDEX_URL` for accessible mirrors without changing defaults or user Docker settings.

Remote CI requires pushing the local branch. The existing four-case live LLM benchmark was not rerun; its dry-run selected four cases only. No production connectors or production authorization service were added.

The lock uses Unix flock and is a deliberately serial single-machine solution, not distributed concurrency. Existing checkpoint deserialization emits a warning for the project's CheckResult type with current LangGraph; it did not fail regression or golden evaluation.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
npm ci
make check
python scripts/generate_gate_evidence.py
python server.py
# Container, once the registry is reachable:
docker compose up --build
```

See [engineering boundaries](engineering-boundaries.md) for the exact implementation limits.
