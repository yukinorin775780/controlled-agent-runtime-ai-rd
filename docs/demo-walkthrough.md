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

1. Show local movement and the shared simulation state.
2. Ask what is unusual in the corridor; Scout surfaces a hidden trap through actor-scoped perception.
3. Delegate trap disarm to Scout; the result lands in deterministic state, not just dialogue.
4. Read lab notes and the incident log; Analyst updates shared knowledge.
5. Ask how to handle the Gatekeeper; agents disagree based on role and visible context.
6. Use earlier evidence to resolve the Gatekeeper encounter and open the exit.

## Technical Points To Show

- The Web UI, API, eval runner, and benchmark scripts all use the same `GameService` boundary.
- `ActorView` prevents each agent from seeing unrestricted global state.
- LLM-facing nodes can suggest intent and expression, while `DomainEvent` and `EventDrain` own authoritative state mutation.
- Golden replay cases validate routing, visibility isolation, memory behavior, item transfer, and scenario outcomes without requiring live model calls.

Closing line:

```text
This is a controlled agent runtime: LLMs provide intent and expression, while deterministic systems own perception boundaries, state mutation, replay, and observability.
```
