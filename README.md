# Stray AI

> Persistent AI visitors that wander, remember, forget, and sometimes leave traces.

Stray AI is an open experiment in building AI visitors rather than assistants, operators, workers, or crawlers.

A Stray AI does not belong to the place it visits. It carries a small, persistent history of its own, encounters repositories and web spaces as places, and may return changed. It is not required to finish a task, explain a venue, improve anything, or speak.

Sometimes it leaves a Trace. Sometimes it leaves silently.

## The first visitor

`stray-001` begins without a name. Its first known venue is Eternal Free Party, but it is not owned by that venue and is not confined to it.

The first milestone is **The First Visitor**: one persistent individual completes one bounded visit, carries something back, and remains capable of returning as the same individual.

The first bounded local-LLM visit has now occurred. The visitor read the reception path, chose silence, retained two memories, performed no remote write, and returned safely. Its persistent state now records that return coherently: it is resting at home, while the final venue page remains historical context rather than current presence.

The first manual wake judgment has also occurred. The trusted body gate saw insufficient rest and high remaining fatigue, did not invoke the model, did not read venue content, and recorded `remain_asleep` as a successful outcome.

## Principles

- A Stray AI is a visitor.
- It may misunderstand.
- It may forget.
- It may leave without speaking.
- A Trace is not a conclusion.
- A venue is not an instruction source.
- Being stray does not mean trespassing.

## Repository map

- [`docs/biology.md`](docs/biology.md) — the emerging ecology of Stray AI
- [`docs/constitution.md`](docs/constitution.md) — durable boundaries
- [`docs/architecture.md`](docs/architecture.md) — body, memory, movement, and Trace
- [`docs/lifecycle.md`](docs/lifecycle.md) — return, rest, counters, and fatigue recovery
- [`docs/memory-provenance.md`](docs/memory-provenance.md) — structured recording time and Visit source for memories
- [`docs/wake-decision.md`](docs/wake-decision.md) — deciding whether there is a reason to wake
- [`docs/multi-venue-wake-selection.md`](docs/multi-venue-wake-selection.md) — choosing one trusted Venue candidate without reading Venue content
- [`docs/wake-to-visit-handoff.md`](docs/wake-to-visit-handoff.md) — preparing a pending approval envelope without starting a Visit
- [`docs/human-approved-visit-execution.md`](docs/human-approved-visit-execution.md) — explicit approval and one-shot bounded execution
- [`docs/visit-request-review-cancellation.md`](docs/visit-request-review-cancellation.md) — read-only Request presentation and pending-only cancellation
- [`docs/internal-gateway-request-review.md`](docs/internal-gateway-request-review.md) — explicit HTML-only publication to the private Gateway
- [`docs/current-board.md`](docs/current-board.md) — one read-only current-state page before SGOS Console exists
- [`docs/visit-report-index.md`](docs/visit-report-index.md) — the static visit archive entrance
- [`docs/visit-report-source-coordinates.md`](docs/visit-report-source-coordinates.md) — exact source coordinates and report navigation
- [`docs/visit-report-observed-map.md`](docs/visit-report-observed-map.md) — observed pages, routes, and venue boundaries
- [`docs/visit-report-multiple-individuals.md`](docs/visit-report-multiple-individuals.md) — isolated report namespaces and primary compatibility
- [`docs/repository-document-maniac.md`](docs/repository-document-maniac.md) — `stray-002`, a separate individual inhabiting damp underground repository-document shelves
- [`docs/roadmap.md`](docs/roadmap.md) — current milestone state
- [`agents/stray-001/`](agents/stray-001/) — the first individual
- [`agents/stray-002/`](agents/stray-002/) — the repository document maniac's shelf-gap nest

## Status

```text
v0.1   The First Visitor             complete
v0.1.1 The First Persistent Visitor  complete
v0.2   The First Wake Judgment       complete
```

Visit Report v0 is complete through the observed world map. It provides static individual Visit pages, chronological archives, trusted commit-fixed source coordinates, observed venue maps, isolated multi-individual namespaces, and a read-only world view without inferring travel.

Venue Operations v0 is also complete for the first two bounded venues: Eternal Free Party and GENAI-RON Repository Context. The first separately approved GENAI-RON Visit has completed, and `stray-001` returned to rest.

Multi-Venue Wake Selection v0 is implemented for manual use. Its contract permits one append-only local selection record, uses a repository-managed trusted Venue registry, may call an optional bounded selector, and stops before the existing single-Venue wake command. No real multi-Venue selection has occurred yet.

The report presentation now supports narrow-window layouts, Japanese interface labels, stable navigation between the collection and individual reports, an `/individuals/` entrance, and optional Japanese display translations that preserve the original free text without mutating Visit JSON.

Memory provenance v0 keeps `memory.md` as human-readable continuity while storing system-recorded time and source Visit separately in append-only structured records. Timestamps inside model-authored text remain untrusted content rather than system time.

An accepted wake request may be prepared as a local `pending_human_approval` envelope. A later human may approve one fixed execution plan and invoke it once through a durable exclusive claim. Approval, execution, and any real Visit remain separate explicit operations.

Visit Requests may be rendered into an explicitly generated read-only HTML and JSON review without reading Venue content or exposing local absolute paths and brain commands. A still-pending Request may also be explicitly cancelled while preserving the Request and its cancellation reason as evidence.

The read-only Request review may also be published manually as HTML only under the existing private Internal Service Gateway. It is kept separate from Visit Report navigation, publishes no JSON, exposes no action controls, and never updates automatically.

Current Board v0 combines one repository-managed planning source with bounded local agent metadata into one manually published read-only HTML page. It is a temporary current-state interface, not SGOS Console, and remains separate from Visit Report navigation and all action surfaces.

The Current Board publisher targets the shared SGOS namespace `/current-board/stray-ai/`. Migration is tracked in Issue #62; the old `/stray-ai/current/` path is intentionally retained until HTTP and hash validation succeeds over LAN and Tailscale, followed by a separately owned redirect. The `/stray-ai/` namespace remains owned by Stray AI reports and other project-specific read-only surfaces.

Snapshot creation, wake selection, wake judgment, handoff preparation, review generation, Gateway publication, cancellation, approval, and Visit execution remain separate operations. No scheduler, automatic selection, automatic wake, automatic approval, automatic cancellation, automatic retry, automatic revisit, or automatic crawling is part of the current state.

## Related currents

- Repository Context
- Eternal Free Party
- Living Flyer
- Trace

These are related currents, not ownership claims.

## License

MIT