# Case Study

## Problem

Many LLM agent demos give the model broad context and let generated text imply state changes. That is risky for any stateful interactive system where hidden information, inventory, flags, and user-facing consequences must remain consistent.

Controlled Agent Sim Runtime turns a compact game-like scenario into an engineering testbed: agents can perceive, reason, speak, and suggest actions, while deterministic systems own state mutation and replay.

## Solution

The runtime splits the workflow into explicit layers:

- `GameService` is the orchestration boundary shared by Web UI, evals, benchmark scripts, and API calls.
- LangGraph routes user input through input parsing, Director routing, mechanics, actor runtime, lore/retrieval, generation, and event drain nodes.
- `ActorView` gives each agent only the world state it is allowed to know.
- `DomainEvent` and `EventDrain` convert proposed consequences into deterministic state commits.
- Golden replay cases verify visibility, item transfer, memory isolation, traps, encounter outcomes, and final escape paths without live LLM calls.

## Architecture

```mermaid
flowchart LR
    UI["Web UI / Demo"] --> API["FastAPI Service"]
    API --> Graph["LangGraph Workflow"]
    Graph --> Router["Director Router"]
    Router --> View["ActorView Builder"]
    Router --> Mechanics["Rules / Mechanics"]
    View --> Actors["Actor Runtime"]
    Actors --> Events["DomainEvent"]
    Mechanics --> Events
    Events --> Drain["EventDrain"]
    Drain --> State["GameState Checkpoint"]
    State --> Eval["Golden Replay / Benchmark"]
    State --> UI
```

## Delivery

- Built a runnable vertical slice with service API, browser UI, map interaction, party state, inventory, dice/check feedback, and Director Timeline.
- Added regression gates through `pytest`, `python -m core.eval.runner --suite golden`, and `python scripts/generate_benchmark.py --dry-run --max-cases 4`.
- Kept the scenario small so technical review can focus on visibility boundaries, state ownership, eval design, and observability.

## Results

- Demonstrates a 0-to-1 AI application workflow from requirement decomposition to demo, tests, and operator inspection.
- Shows how LLM output can be integrated into a safer runtime without letting free-form generation silently rewrite authoritative state.
- Provides a concrete bridge between game-like simulation and AI tooling: the scenario is the inspectable test surface, while the reusable value is the controlled agent runtime.
