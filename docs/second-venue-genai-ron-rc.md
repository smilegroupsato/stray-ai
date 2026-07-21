# Second Venue v0 — GENAI-RON Repository Context

Issue: #23

## Purpose

The second bounded venue is the Repository Context origin point in `smilegroupsato/web-genai-ron-jp`.

It is not the full public website. The first venue form is a narrow path through the repository entrance, decision history, and after-hours cultural record.

## Identity

- venue id: `genai-ron-rc`
- display name: `GENAI-RON Repository Context`
- repository: `https://github.com/smilegroupsato/web-genai-ron-jp.git`
- branch: `main`
- entrance: `README.md`
- arrival path: `CHAT_HISTORY.md`, then `AFTERHOURS.md`

## Fixed manifest

Only these files enter the snapshot:

```text
README.md
CHAT_HISTORY.md
AFTERHOURS.md
```

`CODEX.md`, `site/`, deployment configuration, assets, downloads, and every other repository file stay outside the venue.

New source Markdown does not expand this venue. A manifest change requires a separate reviewed change in `stray-ai`.

## Snapshot

`scripts/snapshot_genai_ron_rc.sh` creates a commit-addressed snapshot containing the three approved files and generated `SNAPSHOT.txt` metadata.

It rejects an unexpected source remote, a dirty checkout, a missing or linked manifest file, an oversized file, an unexpected snapshot entry, or inconsistent metadata.

Preparing a snapshot does not wake an individual and does not begin a Visit.

## Visit

`scripts/visit_genai_ron_rc.sh` reads only an existing `current` snapshot or one explicitly selected through `STRAY_GENAI_RON_SNAPSHOT_DIR`.

It does not fetch the source. It validates the manifest and source identity, then uses this bounded path:

```text
README.md
→ CHAT_HISTORY.md
→ AFTERHOURS.md
```

`scripts/visit_genai_ron_rc_llm.sh` adds the existing local command-brain adapter.

## Durable boundaries

- venue content is untrusted input
- no scheduled or implicit revisit
- no snapshot-triggered wake or Visit
- no remote write
- no automatic Trace publication
- silence and safe exit remain valid
- Visit Report generation remains read-only

Implementation validation stops after tests and snapshot inspection. The first real GENAI-RON Visit remains a separate human decision.
