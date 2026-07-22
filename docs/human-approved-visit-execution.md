# Human-approved Visit Execution v0

This layer connects a prepared Visit request to one bounded Visit only after two separate human actions.

It does not make wake judgment, prepare a request, approve automatically, fetch a venue, create a snapshot, schedule work, regenerate reports, or publish a Trace.

## State transition

```text
pending_human_approval
        |
        | explicit approval command
        v
approved
        |
        | separate explicit execution command
        v
executing
        |
        +----> executed
        |
        +----> execution_failed
```

`execution_failed` and an interrupted `executing` state are fail-stop conditions. v0 provides no automatic retry or recovery command.

## Approval

Approval requires all of the following:

- an existing top-level request under `agents/<id>/visit_requests/`;
- exact confirmation of the request id;
- a human-provided approver name;
- the visitor still being `resting` with no current location;
- an unchanged source wake record and SHA-256;
- the accepted or corrected `request_visit` wake decision;
- the existing snapshot root still matching the opaque candidate identity;
- an entrance and arrival path that remain inside that snapshot;
- an existing local Trace outbox;
- one fixed execution backend and brain plan.

Approval records a canonical SHA-256 over the immutable request core, approver, and execution plan. It reads no venue page content and starts no Visit.

Supported approval plans are:

```text
mock
command brain argv + label + timeout
```

The command plan is stored as an argv array and is invoked without a shell. Secrets must not be embedded in the stored command.

Example deterministic approval:

```bash
stray-ai-approve-visit \
  --agent /path/to/agents/stray-001 \
  --request /path/to/agents/stray-001/visit_requests/REQUEST_ID.json \
  --confirm-request-id REQUEST_ID \
  --approved-by "Taku Sato" \
  --backend mock \
  --seed 7 \
  --outbox /path/to/outbox/traces
```

Example command-brain approval:

```bash
stray-ai-approve-visit \
  --agent /path/to/agents/stray-001 \
  --request /path/to/agents/stray-001/visit_requests/REQUEST_ID.json \
  --confirm-request-id REQUEST_ID \
  --approved-by "Taku Sato" \
  --backend command \
  --brain-command "python scripts/openai_compatible_brain.py" \
  --brain-label MODEL_NAME \
  --brain-timeout 150 \
  --outbox /path/to/outbox/traces
```

Repeated approval is idempotent only when the approver and full plan are identical. Conflicting approval fails closed.

## Execution

Execution accepts only:

- the agent directory;
- the already approved request file;
- exact confirmation of the request id.

It accepts no replacement snapshot, route, outbox, backend, command, model label, timeout, or seed.

Before calling the existing bounded `run_visit`, execution revalidates the source wake, request core, approval digest, snapshot identity, route containment, outbox, and resting state. It then creates a claim with exclusive file creation:

```text
agents/<id>/visit_requests/claims/<request-id>.json
```

The claim is durable and is never removed automatically. This prevents concurrent or repeated execution even if the request envelope is manually reverted.

Execution command:

```bash
stray-ai-execute-approved-visit \
  --agent /path/to/agents/stray-001 \
  --request /path/to/agents/stray-001/visit_requests/REQUEST_ID.json \
  --confirm-request-id REQUEST_ID
```

On success, the request becomes `executed` and records the resulting Visit file. On an ordinary exception after claim, it becomes `execution_failed`. A process interruption may leave `executing`; the durable claim still blocks automatic or accidental repetition.

## Safety boundary

This milestone adds no:

- scheduler, cron, systemd timer, watcher, or queue worker;
- automatic wake check;
- automatic request preparation;
- automatic approval;
- automatic retry or recovery;
- remote venue fetch;
- snapshot creation;
- report generation;
- remote Trace publication.

A real Visit for a persistent individual remains a separate human decision after code, CI, and synthetic validation.
