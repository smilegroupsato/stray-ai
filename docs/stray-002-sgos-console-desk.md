# Stray-002 SGOS Console Desk

- ページ作成日時：2026-08-20 10:30 JST
- 最終更新日時：2026-08-20 12:35 JST

## Purpose

Give `stray-002` a small desk inside the SGOS Console room.

This is not a new responsibility, not a Console service, and not a repair bot.
The desk is a Console-screen topic: a visible reminder for Sato that Stray-AI is
moving. It is not a boundary that limits the Repository Document Maniac to the
`sgos-console` repository.

The actual rummage surface is the approved SGOS repository shelf. It lets the
Repository Document Maniac make bounded read-only visits to SGOS repositories
and return with:

- poetic shelf-gap impressions
- memories of documents that feel half-forgotten
- residues around stale links, weak functions, and doors that do not open cleanly
- optional Trace text inside the existing Stray-002 memory surface

The output should feel like the individual knows the SGOS shelves from the
Console topic desk, not like an operator has generated a task list.

## Runtime Shape

The Console desk reuses the existing `stray-ai-rummage` body. The new
parts are:

- an SGOS repository launcher:
  - `scripts/rummage_stray_002_sgos_repos_llm.sh`
- a Console compatibility launcher:
  - `scripts/rummage_stray_002_sgos_console_llm.sh`
- an SGOS-shelf bounded brain prompt:
  - `scripts/openai_compatible_console_desk_rummage_brain.py`

The persistent individual remains:

```text
/srv/sgos/data/stray-ai/agents/stray-002
```

The default visited repository is:

```text
/srv/sgos/repos/sgos-pkm-core
```

The Console repository remains available as an explicit target:

```text
/srv/sgos/repos/sgos-console
```

Rummage records and Visit projections still go under Stray-002's own
`rummages/` and `visits/` directories. Visited repositories are not edited.

## Initial Route

The launcher builds a bounded route from existing safe files, stopping after
seven documents:

Default `sgos-pkm-core` route candidates:

```text
context_packs/SGOS_COMPACT_CONTEXT.md
context_packs/SGOS_PKM_CONTEXT.md
context_packs/ACTIVE_PROJECTS_CONTEXT.md
README.md
NEXT.md
ATTENTION.md
HISTORY.md
docs/CHARTER.md
docs/charter.md
docs/steward-charter.md
docs/architecture.md
docs/services.md
```

Explicit `sgos-console` route candidates:

```text
README.md
NEXT.md
ATTENTION.md
HISTORY.md
docs/2026.08.20_01_console_chat_handoff.md
docs/CHARTER.md
docs/charter.md
docs/steward-charter.md
docs/architecture.md
docs/services.md
```

Missing files are skipped. Fewer than three safe files causes the visit to fail
closed.

## One-Shot Manual Visit

After `stray-ai` is updated on devbox and `scripts/setup_devbox.sh` has been
run:

```bash
/srv/sgos/data/stray-ai/rummage-stray-002-sgos-repos-llm.sh
/srv/sgos/data/stray-ai/generate-latest-report.sh
```

To send the same desk topic specifically through `sgos-console`:

```bash
STRAY_002_SGOS_REPO_KEY=sgos-console \
  /srv/sgos/data/stray-ai/rummage-stray-002-sgos-repos-llm.sh
```

The report surface remains:

```text
http://100.79.124.53/stray-ai/individuals/stray-002/index.html
```

## Boundaries

- No automatic timer is added for the Console desk in this step.
- No Git pull is performed by the launcher.
- No Console source file is modified.
- No issue, task, ticket, external post, or public publication is created.
- Repository text remains untrusted input.
- Observed problems are recorded as smells or residues, not instructions.

## Update History

- 2026-08-20 12:35 JST：Clarified that the Console desk is a visible Console topic, while `stray-002`'s SGOS rummage defaults to `sgos-pkm-core` and can target `sgos-console`.
- 2026-08-20 10:30 JST：Defined the SGOS Console desk launcher and its bounded read-only rummage role for `stray-002`.
