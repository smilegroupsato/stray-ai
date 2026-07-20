# First Deterministic Wake Judgment — 2026-07-20

## Scope

The persistent `stray-001` habitat on devbox performed its first manual wake check against an already existing local Eternal Free Party snapshot.

The wake check did not fetch the venue, read venue content, invoke the language model, or start a visit.

## Environment

- host: devbox
- repository branch: `agent/wake-decision`
- local Python: 3.14.4
- local test result: 22 passed
- GitHub Actions: Python 3.11 and 3.12 passed

## Trusted facts

```text
checked_at:             2026-07-20T13:49:53+09:00
minimum_rest_hours:     12.0
elapsed_rest_hours:     1.4895
maximum_fatigue:        0.5
recovered_fatigue:      0.8604
previous_snapshot_id:   ae3bdba670c87b0057bb85730e8f928fd95cee4b
candidate_snapshot_id:  ae3bdba670c87b0057bb85730e8f928fd95cee4b
venue_changed:          false
venue_content_read:     false
```

## Decision

```text
source:        deterministic_gate
eligible:      false
decision:      remain_asleep
brain.status:  not_invoked
```

The body gate reported two blockers:

- minimum rest time had not elapsed
- fatigue remained above the wake threshold

The visitor remained `resting` with `current_location: null`.

## Preservation

Before and after the wake check:

```text
state file:    unchanged
Visit JSON:    4 -> 4
Trace files:   1 -> 1
wake records:  0 -> 1
```

The new local observation record was written to:

```text
/srv/sgos/data/stray-ai/agents/stray-001/wake_checks/2026-07-20_134953.json
```

## Safety result

- no model request was made
- no venue content was read
- no remote venue fetch occurred
- no visit was started
- no Visit JSON was changed
- no Trace was created or removed
- no persistent state was changed
- no remote write occurred

The first wake judgment therefore demonstrated that remaining asleep is an explicit, observable, successful outcome rather than a missing action or failure.
