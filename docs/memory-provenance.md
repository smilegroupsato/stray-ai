# Memory provenance v0

Memory provenance separates what the visitor remembered from when the system recorded it and which Visit produced it.

## Boundary

`memory.md` remains the human-readable continuity document used by the visitor's bounded brain context.

`memory_records.jsonl` is an append-only structured companion kept inside the individual agent directory. It does not replace `memory.md`, mutate Visit JSON, or publish anything remotely.

The authoritative time of a memory record is the Visit completion time stored in `recorded_at`. A timestamp that appears inside `text` is model-authored content and is not treated as system time.

## Schema

Each line of `memory_records.jsonl` is one JSON object:

```json
{
  "schema": "stray-memory-v1",
  "memory_id": "2026-07-21_130524:01",
  "text": "The remembered text, unchanged apart from existing whitespace and length bounds.",
  "recorded_at": "2026-07-21T13:06:40+09:00",
  "source_visit": "visits/2026-07-21_130524.json",
  "source_step": 3,
  "model_authored_time": null
}
```

Fields:

- `memory_id` is stable within one Visit and memory ordinal.
- `text` is the selected memory text.
- `recorded_at` is system-recorded Visit completion time.
- `source_visit` is a relative link to the preserved Visit JSON.
- `source_step` identifies the step that selected the memory when known.
- `model_authored_time` remains `null` in v0. Timestamps embedded in `text` are never parsed or promoted.

## Historical backfill

Existing Visit files are not edited.

The idempotent agent migration reads each preserved Visit's `memories_added` and creates missing structured records. Historical records use the Visit's `ended_at` as `recorded_at` and set `source_step` to `null`, because older Visit JSON did not preserve step-level memory provenance.

The migration does not rewrite `memory.md`. It only creates or extends `memory_records.jsonl` with missing records.

## New Visits

A new Visit continues to:

1. preserve selected text in `memory.md`
2. preserve the same text in `memories_added` inside the Visit JSON
3. add one structured provenance record with Visit and step coordinates

Memory selection limits, silence, forgetting, bounded venue access, and Trace behavior remain unchanged.

## Failure behavior

Malformed existing memory records are not silently overwritten. The provenance layer fails closed rather than discarding or guessing structured history.

No scheduler, automatic Visit, wake check, snapshot refresh, or remote write is introduced by this schema.
