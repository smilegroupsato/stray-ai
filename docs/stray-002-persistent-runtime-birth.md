# Stray-002 Persistent Runtime Birth

- ページ作成日時：2026-07-24 12:37 JST
- 最終更新日時：2026-07-24 12:52 JST

## Purpose

Create `stray-002` once under the devbox persistent habitat after explicit human
authorization, while preserving its repository identity and first home-shelf
rummage without waking it, starting a Visit, publishing a Report, or creating a
scheduler.

This birth is the transition from a repository-backed individual definition to
an independently preserved runtime body. It does not make `stray-002` a copy of
`stray-001`.

## Persistent namespace

The birth target is:

```text
/srv/sgos/data/stray-ai/agents/stray-002/
├── birth.json
├── profile.yml
├── memory.md
├── state.json
├── observation-log.md
├── visits/
├── wake_checks/
├── wake_selections/
└── visit_requests/
```

The source templates remain under `agents/stray-002/` in the repository.
Persistent state must never be copied back into the repository as an update
mechanism.

## Birth invariants

The dedicated birth script:

1. requires the existing persistent `stray-001` namespace;
2. validates the `stray-002` profile and initial state;
3. requires `resting`, `visit_count: 0`, and
   `document_rummage_count: 1`;
4. refuses to overwrite any existing `stray-002` path, including a symlink;
5. builds the new body in a staging directory and moves it into place once;
6. records the source commit and template hashes in `birth.json`;
7. verifies that the protected `stray-001` profile, memory, and state hashes
   remain unchanged.

The empty runtime directories establish separate namespaces. They do not
authorize any content to be written into them.

## Execution

After the implementation is merged and the devbox checkout is fixed to the
approved commit:

```bash
cd /srv/sgos/repos/stray-ai
bash scripts/devbox/birth-stray-002-v0.sh
```

The command is intentionally not idempotent. A second invocation fails instead
of treating an existing individual as replaceable setup state.

## Verified birth

The one-time birth completed on the devbox at `2026-07-24 12:50 JST` from
source commit `9291bed8fd9dab0eb77ddea65ddc7d09e5d06669`.

Verification confirmed:

- persistent path:
  `/srv/sgos/data/stray-ai/agents/stray-002`;
- `status: resting`;
- `visit_count: 0`;
- `document_rummage_count: 1`;
- empty `visits/`, `wake_checks/`, `wake_selections/`, and
  `visit_requests/` namespaces;
- no wake, Visit, scheduler, or Report publication effect;
- `stray-001` remained the unchanged primary individual.

The repository-backed first home-shelf rummage remains part of the initial
body. The first rummage that changes the devbox-backed persistent body is a
separate, unapproved operation.

## Remaining boundaries

Persistent birth does not authorize:

- the first devbox-backed document rummage;
- wake judgment or wake selection;
- creation, approval, or execution of a Visit Request;
- Visit Report regeneration or publication;
- automatic snapshot fetch;
- cron, systemd timer, or another scheduler;
- changing `stray-001` as the primary compatibility individual.

Each is a later explicit decision.

## Update History

- 2026-07-24 12:52 JST：Recorded the verified devbox birth, source commit,
  initial persistent state, empty runtime namespaces, and unchanged execution
  boundaries.
- 2026-07-24 12:37 JST：Defined the one-time fail-closed persistent birth
  procedure, namespace, invariants, and post-birth boundaries for `stray-002`.
