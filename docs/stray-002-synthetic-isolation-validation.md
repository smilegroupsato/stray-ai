# Stray-002 Synthetic Multi-Individual Isolation Validation

- Page created: 2026-07-24 12:14 JST
- Last updated: 2026-07-24 12:14 JST

## Purpose

Validate that the repository-backed definition of `stray-002` can coexist with
`stray-001` without creating a persistent second runtime or allowing state,
memory, wake, selection, Visit Request, or Report data to cross individual
boundaries.

This is a synthetic pre-runtime validation. It does not use
`/srv/sgos/data/stray-ai`, invoke a devbox launcher, read a live Venue, approve or
execute a Visit, publish a Surface, or create a scheduler.

## Fixture

The integration test creates two temporary individuals:

- `stray-001`, with an Alpha Visit, private memory marker, state, wake history,
  selection history, and Visit Request namespace;
- `stray-002`, with a Beta Visit and its own distinct equivalents.

Both use temporary snapshots and a temporary Venue registry. The bounded wake
brain is a local synthetic adapter that returns `request_visit` without adding
an impulse.

## Assertions

The validation proves that:

1. state, profile, and memory bytes remain unchanged for both individuals;
2. wake-selection records are written only below the selected individual's
   `wake_selections/` directory and carry the matching `agent_id`;
3. wake records are written only below the selected individual's
   `wake_checks/` directory and carry the matching `agent_id`;
4. another individual's wake record is rejected before a Visit Request can be
   created;
5. each valid Visit Request is written below its own individual's
   `visit_requests/` directory;
6. a transplanted Visit Request is rejected by its embedded `agent_id`;
7. no Visit claim or new Visit is created;
8. individual Reports contain only their own observed route;
9. private memory markers are absent from all generated HTML;
10. historical root compatibility aliases remain fixed to explicit primary
    individual `stray-001`.

## Result

The repository requires no production-code change for this boundary. The
existing path-containment checks, embedded identity checks, and report
namespaces pass when exercised together through the synthetic two-individual
integration test.

This result authorizes only the next human decision about persistent
`stray-002` runtime birth. It does not itself authorize that birth, a first
devbox-backed rummage, automatic wake or selection, a Visit, or scheduling.

## Update history

- 2026-07-24 12:14 JST: Created the synthetic validation record and documented
  its fixture, assertions, result, and remaining authorization boundary.
