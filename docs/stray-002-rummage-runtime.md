# Stray-002 Rummage Runtime

- ページ作成日時：2026-07-24 16:05 JST
- 最終更新日時：2026-07-25 11:40 JST

## Purpose

Provide `stray-002` with a real, bounded execution path for repository document rummaging. This runtime replaces neither Visit nor the earlier hand-authored first-rummage prototype.

## Two-stage attention

1. The host validates an explicitly supplied route of three to seven repository text documents.
2. The command brain sees only titles and bounded cover excerpts.
3. It chooses zero to three documents for deep reading.
4. The host sends full bounded content only for those selected documents; unselected document content is not repeated in the reflection request.
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
/srv/sgos/data/stray-ai/setup-stray-002-rummage-model.sh
/srv/sgos/data/stray-ai/rummage-stray-002-llm.sh
```

The setup command creates the local derived model
`stray-qwen3.5-9b-16k` from an already available `qwen3.5:9b`, with
`num_ctx 16384`, and verifies the resulting configuration. It never pulls a
model automatically. The rummage launcher uses that derived model and the
local OpenAI-compatible endpoint at `127.0.0.1:11434` by default.

The 16K context is required for the fixed seven-document route. During the
first genuine runtime attempt, the survey request consumed 4,020 tokens under
a 4,096-token context, leaving only 76 completion tokens and producing a
truncated JSON string. Raising only `STRAY_LLM_MAX_TOKENS` cannot enlarge the
model's total context window.

`STRAY_LLM_MODEL` may still be overridden for another reviewed compatible
endpoint, but the operator is responsible for providing at least the same
effective context capacity. The route remains fixed in the launcher for this
runtime. A different route is a separate reviewed change.

## Autonomous opportunity

The manual launcher may be placed behind the opt-in guarded systemd timer
described in [`stray-002-autonomous-rummage.md`](stray-002-autonomous-rummage.md).
The timer provides low-frequency opportunities; the guard remains asleep on a
non-`main` branch, a dirty worktree, a non-resting individual, a cooldown, or a
concurrent run. It neither changes the fixed route nor adds any authority to
the rummage body.

## Safety and failure

- Exact `--confirm-agent-id stray-002` confirmation is mandatory.
- The individual must be resting in its defined home location,
  `damp-underground-library-shelf-gap`; a completed rummage returns there.
- Absolute paths, traversal, symlinks, duplicate files, and unsupported document types are rejected.
- Each document hash is checked again before persistent writes.
- Invalid model JSON, invalid indices, missing deep-reading results, adapter failure, or timeout ends without a completed rummage.
- Adapter failures expose only a bounded stderr diagnostic, so failure causes can be read without emitting an unbounded model response.
- No automatic retry is provided.

## Update History

- 2026-07-25 11:40 JST：Added the opt-in guarded autonomous opportunity layer without expanding the rummage body's authority.
- 2026-07-25 10:24 JST：Recorded the successful first genuine runtime rummage and standardized the verified 16K Ollama model setup.
- 2026-07-24 17:19 JST：Isolated reflection input to selected documents, raised the local model response budget, and exposed bounded adapter diagnostics.
- 2026-07-24 16:32 JST：Aligned runtime location checks with Stray-002's persistent underground shelf-gap habitat.
- 2026-07-24 16:05 JST：Created the executable rummage runtime contract and devbox procedure.
