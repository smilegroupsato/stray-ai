# Visit Request Review & Cancellation v0

## Purpose

This milestone gives the human operator a safe way to inspect local Visit Requests and to cancel a request that has not been approved.

It does not make approval easier by making it automatic. It makes the current state legible while preserving explicit human responsibility.

## State boundary

```text
pending_human_approval
        ├─ explicit approval → approved
        └─ explicit cancellation → cancelled
```

Only `pending_human_approval` may become `cancelled`.

The following states cannot be cancelled by this command:

- `approved`
- `executing`
- `executed`
- `execution_failed`
- any request with a durable execution claim

Cancellation after approval or execution would require a different safety review. This milestone does not define it.

## Read-only review outputs

The review command is invoked manually:

```bash
stray-ai-review-visit-requests \
  --agent /local/agent \
  --html-output /local/review/index.html \
  --json-output /local/review/requests.json
```

It scans top-level `visit_requests/*.json` files and produces:

- one static HTML page for human review;
- one machine-readable JSON summary;
- no state transition;
- no approval;
- no cancellation;
- no Visit.

The page contains no form, button, JavaScript action, or command execution surface.

## What the review may inspect

The review layer may read metadata needed to describe and check a request:

- Request JSON;
- source wake record bytes and SHA-256;
- profile identity;
- snapshot directory identity;
- existence and containment of the approved relative route;
- approval, cancellation, execution, and claim metadata already present in the Request.

It does not read Venue page contents. Checking whether a bounded page exists is not the same as opening and interpreting that page.

## Presentation minimization

HTML and JSON presentation deliberately omit:

- `snapshot_root` absolute paths;
- absolute outbox paths;
- full brain commands;
- local Visit file paths;
- any `/srv/...` coordinate.

For an approved command-brain plan, the review shows only:

- backend;
- bounded model label;
- timeout;
- command argument count;
- a SHA-256 fingerprint of the command list;
- whether an outbox was configured.

The fingerprint helps compare plans without disclosing the command itself.

Free text is treated as untrusted display data, escaped in HTML, bounded in length, and stripped of absolute local paths.

## Malformed Requests

One malformed Request must not hide every other Request.

The collection renders malformed files as isolated invalid cards with bounded error codes. It does not expose parser exceptions or local paths in the presentation.

## Explicit cancellation

Cancellation is a separate command:

```bash
stray-ai-cancel-visit-request \
  --agent /local/agent \
  --request /local/agent/visit_requests/REQUEST_ID.json \
  --confirm-request-id REQUEST_ID \
  --cancelled-by "Human Name" \
  --reason "Why this pending encounter should not proceed"
```

The command requires:

- the Request to be a top-level local Request file;
- supported schema;
- Request id matching the filename;
- Request identity matching the agent profile;
- exact Request-id confirmation;
- a named human canceller;
- a non-empty bounded reason;
- status exactly `pending_human_approval`;
- no approval record;
- no execution history;
- no durable claim;
- `visit_started: false`.

## Cancellation record

The Request is not deleted. Its status becomes `cancelled` and it receives:

```json
{
  "cancellation": {
    "cancelled_at": "...",
    "cancelled_by": "...",
    "confirmed_request_id": "...",
    "reason": "..."
  }
}
```

This preserves why the encounter did not happen.

Repeating the exact same cancellation is idempotent. A conflicting canceller or reason fails closed.

## Excluded automation

This milestone adds no:

- scheduler, cron, timer, poller, or queue worker;
- automatic review generation;
- approval or execution controls in HTML;
- automatic approval;
- automatic cancellation;
- automatic snapshot creation or fetch;
- automatic Visit;
- automatic retry;
- report regeneration;
- remote write or Trace publication.

## Failure semantics

Review generation may fail before writing outputs if the agent identity cannot be established. Individual malformed Request files are isolated inside an otherwise valid collection.

Cancellation validates all safety conditions before replacing the Request atomically. Failure leaves the Request unchanged.
