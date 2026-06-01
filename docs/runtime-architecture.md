# Runtime Architecture

## Core Idea

Controlled Agent Sim Runtime separates agent expression from authoritative state. LLMs help interpret and speak; typed systems decide what changes.

```mermaid
flowchart TD
    Player["Player Command"] --> Service["GameService"]
    Service --> Input["Input Node"]
    Input --> Router["Director Router"]
    Router --> ActorView["ActorView"]
    Router --> Mechanics["Mechanics"]
    ActorView --> ActorRuntime["Actor Runtime"]
    ActorRuntime --> Events["DomainEvent"]
    Mechanics --> Events
    Events --> EventDrain["EventDrain"]
    EventDrain --> State["GameState"]
    State --> Memory["Memory"]
    State --> UI["Director Timeline / State Diff"]
    State --> Eval["Golden Replay"]
```

## Important Contracts

| Contract | Purpose | Evidence |
| --- | --- | --- |
| `ActorView` | Limits what each agent can perceive before generation. | Hidden traps, private memory, and actor-specific context can be tested. |
| `DomainEvent` | Represents state mutations as typed records. | Inventory, flags, damage, affection, and memory writes are not implied by prose. |
| `EventDrain` | Applies queued events to authoritative state. | One path owns final commits, making replay and debugging tractable. |
| `MemoryService` | Stores scoped memories and retrieves relevant context. | Long-running behavior avoids dumping raw global history into every prompt. |
| Golden evals | Replays scenario cases without live models. | Regression cases cover routing, visibility, trap handling, and final outcomes. |
| Director Timeline | Explains runtime decisions to an operator. | The UI exposes route stages, payloads, and state diffs during a demo. |

## Data Flow

1. The user enters dialogue or an action in the Web UI.
2. FastAPI sends the request to `GameService`.
3. LangGraph routes the request through input parsing, Director routing, mechanics, actor runtime, lore/retrieval, generation, and event drain.
4. Actors receive scoped `ActorView` payloads rather than raw global state.
5. Deterministic systems emit `DomainEvent` records for authoritative changes.
6. `EventDrain` commits changes into the checkpointed game state.
7. The UI renders narration, agent barks, dice/check feedback, state diffs, and the Director Timeline.
8. Golden replay cases use the same service-level behavior to catch regressions.

## Why This Pattern Generalizes

The same pattern applies beyond this demo:

- customer-service agents need scoped customer and policy context;
- internal coding agents need bounded filesystem and approval policies;
- operations assistants need typed action records and replayable audits;
- game AI agents need hidden-state safety and deterministic world updates.

The game-like scenario makes those constraints visible in a compact, testable form.
