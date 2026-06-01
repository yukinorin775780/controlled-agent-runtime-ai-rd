# Demo Walkthrough

Target length: 60-90 seconds.

Recommended URL:

```text
http://127.0.0.1:8000/web_ui/?session_id=demo_run_001&map_id=hazard_lab&qa_no_idle=1
```

## Setup

```bash
pip install -r requirements.txt
python server.py
```

Optional local gate:

```bash
make check
```

## Walkthrough

1. Open the Agent Runtime Workbench and select `Policy Publish`.
2. Show the business intent in the bottom input: Ops Agent validates a knowledge-base change and calls `publish_policy_patch`.
3. Walk through Runtime Flow: Intent -> Router -> Scoped View -> Tool Gate -> EventDrain.
4. Open Payload Inspector and point out `selected_agent`, `allowed_tools`, `masked_fields`, `policy_gate`, `proposed_tool_call`, and `domain_events`.
5. Switch to `Release Audit` and show how the same flow can block direct publish while still committing an audit event.
6. Mention that the map behind the workbench is a scenario preview used to keep the runtime grounded in a stateful environment.

## Technical Points To Show

- The Web UI, API, eval runner, and benchmark scripts all use the same `GameService` boundary.
- `ActorView` is an execution-context boundary: different agents receive different prompt slices, tool allowlists, visible fields, and memory scopes.
- LLM-facing nodes can suggest intent, expression, and typed tool candidates, while `DomainEvent` and `EventDrain` own authoritative state mutation and audit commits.
- Golden replay cases validate routing, visibility isolation, memory behavior, item transfer, tool-like state transitions, and scenario outcomes without requiring live model calls.

Closing line:

```text
The workbench shows what happens before and after model/tool execution: intent routing, scoped AgentView, policy gates, typed events, and observable commits.
```
