# Visit Report v0 Phase 5 — Observed World Map

Issue: #21

## Purpose

Phase 5 adds a root-level `world.html` that combines only the world relationships already preserved in local Visit records.

The world map is not physical geography and is not a reconstruction of the internet. It is a bounded observation surface showing which persistent individuals have observed which venue snapshots.

## Core distinction from Phase 3

Phase 3 maps pages and transitions inside one individual’s observed venue snapshots.

Phase 5 maps the higher-level relation:

```text
persistent individual → observed place snapshot
```

It does not create edges between consecutive Visits. Chronology is evidence, not proof of travel between places.

## Output model

```text
reports/
├─ index.html
├─ world.html
├─ visits.html
├─ latest.html
├─ map.html
└─ individuals/
   └─ <agent-id>/
      ├─ index.html
      ├─ latest.html
      ├─ map.html
      └─ <visit>.html
```

`index.html` links to `world.html`. `world.html` links back to `index.html` with a relative URL.

## Input boundary

Phase 5 may read only:

- safely discovered immediate child directories under the configured agents directory
- preserved Visit JSON
- bounded profile and state metadata already allowed by Phase 4
- trusted source coordinates resolved by the existing report-source pipeline

Phase 5 must not read or render:

- memory body
- Trace body
- wake-check body as geography
- raw venue content
- secrets
- absolute local paths

## World entities

### Individual

One node per safe agent directory identifier.

Allowed display fields:

- agent id
- optional display name
- bounded status
- preserved Visit count

### Observed place

Trusted remote observations are identified by:

```text
repository URL + exact observed commit
```

Different commits remain distinct nodes, even when they belong to the same repository.

Local-only observations remain visible without fabricated repository coordinates. In v0, local-only observations are scoped to an individual unless a safe shared identity is explicitly preserved in a later phase.

### Observation relation

One aggregated relation per:

```text
individual + observed place
```

The relation records:

- number of preserved Visits
- first observed timestamp
- last observed timestamp
- supporting namespaced Visit Report links

A relation means only “this individual has a preserved Visit observation of this place.”

## No inferred world edges

The generator must not infer:

- travel from one Visit to the next
- links between venues
- links between repositories
- links between commits
- links between individuals
- movement from wake decisions or impulses
- unvisited pages, places, or snapshots

## Presentation

`world.html` contains:

1. a bounded summary
2. a deterministic static individual-to-place SVG graph
3. an accessible individual/place relationship table
4. an observed-place table with exact trusted source coordinates where available
5. a chronological Visit evidence table

The page uses static HTML and inline CSS/SVG only. It has no JavaScript, analytics, remote assets, controls, or write actions.

## Link behavior

- trusted place nodes may link to the repository at the observed commit
- evidence rows link to `individuals/<agent-id>/<visit>.html`
- all local Report navigation is relative
- local-only place nodes have no fabricated external link
- no host, port, URL prefix, or server path is hardcoded

## Failure behavior

- malformed Visit JSON is skipped without blocking valid records
- malformed or empty individuals do not block valid individuals
- conflicting or untrusted source coordinates fall back to local-only observation
- an empty collection still produces a truthful empty `world.html`
- all record-derived strings are escaped
- generated source records remain unchanged

## Current archive expectation

The current preserved archive should produce:

- 1 individual: `stray-001`
- 4 preserved Visits
- 2 observed places
  - one local-only first habitat
  - Eternal Free Party at commit `ae3bdba670c87b0057bb85730e8f928fd95cee4b`
- 2 aggregated observation relations
  - local-only habitat: 1 Visit
  - Eternal Free Party snapshot: 3 Visits
- 4 chronological evidence rows
- no cross-venue travel edge

## Implementation shape

Recommended module boundary:

```text
src/stray_ai/report_world.py
```

Recommended responsibilities:

- build an immutable observed-world model from already loaded source-aware Visit records
- render deterministic static HTML/SVG
- return bounded counts and the generated `world.html` path

`report_collection.py` remains responsible for discovering individuals, generating isolated per-individual reports, and invoking the world-map generator after individual archives are available.

## Validation

Before merge:

- unit tests for aggregation, commit separation, local-only isolation, escaping, empty input, and malformed records
- full CI
- devbox regeneration
- persistent-source hash comparison
- Gateway route check for `/stray-ai/world.html`
- browser inspection on desktop and mobile

No Visit, wake check, scheduler, snapshot, or individual creation is part of validation.
