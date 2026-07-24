# Stray-002 Rummage Runtime

- ページ作成日時：2026-07-24 16:05 JST
- 最終更新日時：2026-07-24 16:05 JST

## Purpose

Provide `stray-002` with a real, bounded execution path for repository document rummaging. This runtime replaces neither Visit nor the earlier hand-authored first-rummage prototype.

## Two-stage attention

1. The host validates an explicitly supplied route of three to seven repository text documents.
2. The command brain sees only titles and bounded cover excerpts.
3. It chooses zero to three documents for deep reading.
4. The host sends full bounded content only for those selected documents.
5. The brain returns deep-reading residues, margin notes, an optional sunlit thought, up to five memories, and at most one Trace.

The host never gives the brain a filesystem path to choose, a command tool, a URL tool, Git authority, or repository write authority. Repository contents remain untrusted data.

## Persistent effects

One successful run writes:

```text
agents/stray-002/
├── rummages/YYYY-MM-DD_HHMMSS.json
├── memory.md
├── observation-log.md
└── state.json
```

The JSON event is the structured source. `memory.md` and `observation-log.md` are readable projections. `state.json` increments both the overall `document_rummage_count` and the separate `runtime_rummage_count`.

The runtime explicitly records that it did not:

- create a Visit
- invoke wake
- create a scheduler
- edit repository content

Report generation remains a later, separate command. When generated, `individuals/stray-002/rummages.html` presents the route, deep readings, notes, memories, sunlit thought, and Trace.

## Devbox execution

After installing the current checkout with `scripts/setup_devbox.sh`:

```bash
export STRAY_LLM_MODEL="qwen3.5:9b"
/srv/sgos/data/stray-ai/rummage-stray-002-llm.sh
```

The launcher uses the local OpenAI-compatible endpoint at `127.0.0.1:11434` by default. The route is fixed in the launcher for the first runtime execution. A different route is a separate reviewed change.

## Safety and failure

- Exact `--confirm-agent-id stray-002` confirmation is mandatory.
- The individual must be resting and have no current location.
- Absolute paths, traversal, symlinks, duplicate files, and unsupported document types are rejected.
- Each document hash is checked again before persistent writes.
- Invalid model JSON, invalid indices, missing deep-reading results, adapter failure, or timeout ends without a completed rummage.
- No automatic retry is provided.

## Update History

- 2026-07-24 16:05 JST：Created the executable rummage runtime contract and devbox procedure.
