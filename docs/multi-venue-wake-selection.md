# Multi-Venue Wake Selection v0

Issue: #56  
Design origin: #53

## Purpose

Multi-Venue Wake Selection lets one resting Stray consider more than one bounded Venue without reading Venue content and without starting a wake check or Visit.

The layer answers only:

```text
remain asleep
or
select one trusted Venue for later human consideration
```

A selected Venue is not a wake decision. The selection record is evidence that one candidate drew attention; it does not authorize anything else.

## Position in the flow

```text
trusted Venue registry
→ trusted local candidate construction
→ candidate-independent body gate
→ optional bounded selector
→ append-only wake selection record
→ stop
```

A human may later invoke the existing single-Venue `stray-ai-wake` command with the selected Venue. There is no automatic chaining.

## Human decisions

The implementation is governed by four explicit decisions:

1. **Side effects** — only one append-only `wake_selections/*.json` record may be created. `state.json`, memory, impulses, Visit JSON, wake records, Trace, Requests, counters, and reports remain byte-identical.
2. **Trusted Venue source** — `registry/venues.yml` is the Source of Truth for Venue IDs admitted to selection.
3. **Selector scope** — v0 includes a deterministic body gate and an optional bounded command selector. Deterministic mode never chooses a Venue.
4. **Stop boundary** — after writing the selection record, the command exits. It does not wake, prepare a Request, approve, execute, fetch a snapshot, or run a Visit.

## Trusted Venue registry

`registry/venues.yml` contains only host-approved identity metadata:

```yaml
schema_version: 0.1
venues:
  - venue_id: eternal-free-party
    display_name: Eternal Free Party
    selection_enabled: true
```

The runtime selector receives `venue_id`, not `display_name`.

The registry must not contain:

- Venue page content
- snapshot content
- local absolute paths
- source repository instructions
- brain commands
- automatic execution policy

Venue IDs must be unique safe slugs. Unknown, duplicate, malformed, disabled, or path-like IDs fail closed.

## Candidate construction

A candidate is identified by:

```json
{
  "venue_id": "trusted-id",
  "candidate_snapshot_id": "opaque-id"
}
```

The candidate snapshot must already exist under:

```text
<venues-root>/<venue-id>/<snapshot-id>
```

Candidate construction may use either:

- repeated explicit `venue_id=snapshot_id` inputs; or
- an explicit current-snapshot mode that reads only each registered Venue's local `current` symlink target.

It must not call a snapshot script, fetch a repository, read `SNAPSHOT.txt`, or read any Venue file.

Validation rejects:

- unknown or disabled Venue IDs
- duplicate Venue IDs
- empty snapshot IDs
- absolute paths, separators, dot segments, or path escape
- symlink snapshot directories
- missing local snapshot directories
- malformed registry data
- candidate sets above the bounded maximum

Validated candidates are sorted by Venue ID before selector input and record creation. CLI order, registry order, filesystem order, and timestamp order must never become hidden ranking rules.

When current-snapshot mode finds no valid `current` snapshot for a registered Venue, that omission is recorded safely and is not represented as changed or unchanged.

## Same-Venue comparison

For each validated candidate, the previous snapshot identity comes only from the latest preserved Visit to that same Venue.

```json
{
  "venue_id": "genai-ron-rc",
  "previous_snapshot_id": "opaque-id-or-null",
  "candidate_snapshot_id": "opaque-id",
  "comparison_available": true,
  "comparison_scope": "same_venue_history",
  "changed": false
}
```

Allowed scopes are:

```text
same_venue_history
same_venue_no_history
explicit_previous
```

No cross-Venue fallback is permitted. `comparison_available: false` is distinct from `changed: false`. A changed identity is not a claim about what changed.

## Candidate-independent body gate

Before an optional selector process can run, the host evaluates only trusted local state:

- lifecycle status is `resting`
- minimum rest time elapsed
- recovered fatigue is at or below the profile threshold

If the gate is blocked, the selector is not invoked and the result is `remain_asleep`.

Candidate count, candidate order, or snapshot metadata cannot bypass this gate.

## Selector input boundary

The optional selector receives only:

- agent ID
- bounded unresolved impulses already admitted by the wake layer
- elapsed rest and recovered fatigue
- conservative wake thresholds
- sorted validated candidate metadata
- output contract

It does not receive:

- memory text
- profile prose
- Venue display names
- repository URLs
- local paths or snapshot roots
- source metadata
- Venue or snapshot file contents
- brain commands
- report data

## Selector output contract

```json
{
  "decision": "remain_asleep | select_venue",
  "selected_venue_id": "exact candidate ID or null",
  "observation": "bounded short text",
  "reason": "bounded short text",
  "reason_code": "no_specific_reason | rest_preferred | tie_unresolved | opaque_identity_changed | unresolved_impulse | comparison_unavailable"
}
```

Validation rules:

- `remain_asleep` requires `selected_venue_id: null`
- `select_venue` requires exactly one ID in the validated candidate set
- unsupported decisions or reason codes fail closed
- malformed JSON, oversized text, timeout, nonzero exit, adapter failure, or unknown selection fails closed
- deterministic mode always remains asleep
- equal-looking candidates remain unresolved unless the bounded selector explicitly selects one valid ID

The selector must not claim that Venue content changed. It knows only opaque identity facts.

## Persistent observation

Each manual run writes one local record:

```text
agents/<agent-id>/wake_selections/YYYY-MM-DD_HHMMSS.json
```

The record includes:

- checked time and agent ID
- body-gate facts and blockers
- registry schema and identity
- sorted validated candidates
- safe omissions from current-snapshot construction
- candidate validation status and safe error
- selector invocation, protocol, model label, status, and safe error
- final decision and selected Venue ID or null
- bounded observation, reason, and reason code
- explicit no-content-read and no-automatic-action flags

Selection records are append-only local evidence. They are not automatically published to Current Board, Visit Report, Request Review, or the Internal Gateway.

## State boundary

Both outcomes preserve:

```text
status: resting
current_location: null
```

Selection must not:

- change `state.json` or `memory.md`
- add an unresolved impulse
- increment counters
- create or modify Visit JSON
- create a Trace
- create or modify a wake check
- create, approve, claim, execute, cancel, or retry a Visit Request
- fetch or prepare a snapshot
- regenerate reports
- publish to the Gateway

## Devbox launchers

`setup_devbox.sh` may create manual launchers:

```text
select-wake-venue.sh
select-wake-venue-llm.sh
```

They may inspect only repository registry data, local `current` symlink targets, and existing snapshot directory identities. Setup creates `wake_selections/` but does not run selection.

## CLI

Deterministic mode over safe existing `current` symlinks is manual and always
remains asleep:

```bash
stray-ai-select-wake-venue \
  --agent /srv/sgos/data/stray-ai/agents/stray-001 \
  --registry registry/venues.yml \
  --venues-root /srv/sgos/data/stray-ai/venues \
  --use-current-snapshots
```

Explicit candidates use repeated `--candidate venue_id=snapshot_id`. Explicit and
current-snapshot modes are mutually exclusive. Command mode additionally requires
`--selector command` and `--selector-command`; it still writes only a selection
record and never invokes the wake command.

## Testing boundary

Implementation tests use synthetic agent habitats and synthetic snapshot directories only. No test or implementation step uses persistent `stray-001` data or Venue content.

A real selection run remains a separate explicit human decision after merge and validation.
