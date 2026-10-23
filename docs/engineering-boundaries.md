# Engineering boundaries

## Intent classification

`core.intent.IntentClassifier` is the replaceable fast-path interface. `KeywordIntentClassifier` is the default; it reuses the existing Chinese/English keyword detectors in their original precedence order. Every `analyze_intent` call passes through this interface. A `None` result retains the existing model-backed analysis path. Campaign-specific overrides still run after analysis; they are scenario rules rather than a general language classifier.

The keyword fast path is fragile: negation, overlapping aliases, mixed languages and ambiguous targets can produce errors. Existing model analysis is also fallible. Future work can inject a small-model classifier with confidence thresholds, then use keywords as a fallback and abstain on ambiguous input. This change adds no new model call or model dependency.

## PolicyGate and tools

`core/gate/policy_gate.py` owns default-deny authorization. Runtime code constructs `ScopedAgentView`; HTTP candidates cannot provide their own allowed tools or passing-eval facts. Combat turn authority, the Hazard Lab gatekeeper-loot exception, and explicit user item-consumption permission are extracted from existing mechanics/generation into this module. Physics still owns quantity, health, range, equipment and map validity checks; PolicyGate is not a replacement for domain validation.

The workbench business roles are reframing only. `/api/gate/evaluate` runs real scope/schema/precondition checks and returns a decision, not tool execution. `domain_events` is empty. Local source-bound golden evidence gates the Ops publish candidate; missing, malformed or stale evidence denies it. This endpoint is an unauthenticated local demonstration, not a production authorization service. A deployed service must supply authenticated identities rather than trust an actor label from HTTP.

`check_target_inventory` has a runtime-bound scoped implementation. Outside that scope it explicitly denies access. The unused physical-tool stub was removed; physical proposals still use the existing typed JSON/action path. There are no implemented external publish, ticket search, or CI connectors.

## Failure handling and retries

`RetryPolicy` defaults to two retries (three total attempts), with exponential delays of 0.1s and 0.2s, capped at 2s. Callers can inject different values. Timeout/connection/transport errors, rate limits and server HTTP failures are transient. Invalid contract errors and other failures do not retry. Cancellation propagates.

Only side-effect-free actor proposals, reflections (which return uncommitted events), and model generation calls retry. State writes and external mutations never retry automatically: those require idempotency keys first. Actor plugin boundaries retain a final catch to preserve the existing non-crashing fallback, after categorized structured telemetry records component, error type, attempt and retry disposition. Raw prompts, secrets and exception messages are not added to failure telemetry.

## Checkpoint concurrency

`checkpoint_lock` uses nonblocking Unix `flock` and async waiting around the full load/initialize/modify/save transaction. It covers chat, reset and reads that may initialize state, across service instances and local processes sharing one database path. Cancellation releases the lock. This intentionally serializes all sessions in that database, reducing throughput in exchange for a minimal race fix.

This is a single-machine Linux/macOS solution. All writers must use this boundary. It does not coordinate remote machines, arbitrary direct SQL writers, network filesystems, or external services. Use a transactional server database and distributed coordination before multi-host deployment. Keep the Docker data volume mounted to persist checkpoints.

## Reproducibility and CORS

`requirements.in` is the direct dependency source and `requirements.lock` pins transitive dependencies for Python 3.11+. Regenerate with `uv pip compile --python-version 3.11 --universal requirements.in -o requirements.lock`. Chroma/Streamlit are optional and excluded from the deterministic CI baseline. `npm ci` uses the existing JS lockfile.

`CONTROLLED_AGENT_CORS_ORIGINS` is a comma-separated origin allowlist, defaulting to `http://127.0.0.1:8000,http://localhost:8000`. Adjust it when changing the local port or deployment origin. Same-origin use needs no CORS exception.
