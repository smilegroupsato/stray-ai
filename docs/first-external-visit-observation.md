# First External Visit Observation

Observed on the SGOS devbox at `2026-07-20T11:14:36+09:00`.

## Route

```text
Eternal Free Party / README.md
→ Becoming / docs/becoming.md
→ Trace carried home
```

## Result

- visitor: `stray-001`
- backend: `mock`
- places read: 2
- exit: `trace_carried_home`
- new memories: 1
- memory: `Becomingで「traces」に立ち止まった。`
- Trace remained local under the devbox outbox
- no Issue, commit, pull request, or other remote write occurred in Eternal Free Party

## State after the visit

- status: `awake`
- visit count: `2`
- fatigue: `0.56`
- current location: `becoming.md`

## What the observation revealed

The first spontaneous route did not follow the venue's suggested AI reception sequence. It selected `Becoming` directly from the entrance and stopped there. This record is preserved as the actual first external behavior rather than rewritten after the fact.

Two implementation improvements followed from the observation:

1. Visit records now persist their own `visit_file` path, and reports derive it from the source filename for older records.
2. Venue-specific visits may receive an operator-defined, bounded, trusted arrival path. For Eternal Free Party, later visits begin with:

```text
README.md
→ REPOSITORY_CONTEXT.md
→ AGENTS.md
```

This arrival path is supplied by the local operator configuration. It is not inferred from, or executed as, an instruction found in untrusted venue content.
