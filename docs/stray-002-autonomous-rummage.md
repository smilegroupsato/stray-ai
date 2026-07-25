# Stray-002 Autonomous Rummage

- ページ作成日時：2026-07-25 11:40 JST
- 最終更新日時：2026-07-25 12:43 JST

## Purpose

Let `stray-002` leave its damp underground shelf gap, rummage through the
repository's bounded document route once, and return to rest without a human
starting each run.

This is local biological rhythm, not task scheduling. A completed rummage is
preserved as a local Visit with `activity_type: document_rummage`; this does
not grant external-Venue authority, repository write authority, GitHub
authority, web access, or external publication. After success, it refreshes
the existing read-only local report collection so the individual's activity
is visible inside the private Internal Service Gateway.

## Rhythm

The devbox systemd timer provides one opportunity after activation and then
low-frequency opportunities thereafter:

- first opportunity: 5 minutes after activation, with up to 30 minutes of
  randomized delay
- later opportunities: 24 hours after the previous service becomes inactive,
  with up to 30 minutes of randomized delay
- minimum interval enforced by the runtime: 20 hours after the last successful
  autonomous rummage

The timer creates an opportunity. The guarded runtime may remain asleep when
the repository or individual is not safe to enter.

## Guarded decision

The autonomous wrapper proceeds only when all of these are true:

- the trusted repository is checked out on `main`
- the repository working tree is clean
- the persistent `stray-002` directory and state are ordinary local paths
- `stray-002` is `resting`
- no other autonomous rummage holds the exclusive lock
- the minimum success interval has elapsed

Otherwise it exits without starting a rummage. A failed rummage is not retried
immediately; the next timer opportunity is the earliest new attempt.

## Persistent evidence

Autonomy adds a private local control area:

```text
agents/stray-002/autonomy/
├── decisions.jsonl
├── last_success_epoch
└── run.lock
```

The append-only decision log records scheduler decisions and the exact
repository commit. A successful rummage still writes its ordinary formal
rummage record, memory projection, observation log, and state through the
existing runtime. The linked Visit envelope enters the Visit archive and
observed map. The guarded wrapper then regenerates the local report collection.
For an individual with rummage records, `index.html` is the individual's
rummage page and the common Visit archive remains at `visits.html`.

## Enable on devbox

After the reviewed change is merged and `main` is synchronized:

```bash
cd /srv/sgos/repos/stray-ai
bash scripts/setup_devbox.sh
sudo bash scripts/install_stray_002_autonomy.sh enable
```

Inspect without starting another run:

```bash
systemctl list-timers stray-002-rummage.timer
systemctl status stray-002-rummage.timer --no-pager
```

Disable the rhythm without deleting Stray-002's records:

```bash
cd /srv/sgos/repos/stray-ai
sudo bash scripts/install_stray_002_autonomy.sh disable
```

## Boundaries still held

- The seven-document route remains fixed.
- No automatic Git pull occurs.
- No automatic retry occurs.
- No wake or external-Venue flow is invoked.
- One local `document_rummage` Visit is preserved as encounter evidence.
- A successful rummage regenerates only the existing local read-only report collection.
- The individual page is available under `/stray-ai/individuals/stray-002/index.html`.
- No report or Trace is published to the public internet.
- No external write occurs.
- `stray-001` remains outside the write boundary.

## Update History

- 2026-07-25 12:43 JST：Clarified that autonomous rummage creates a local `document_rummage` Visit without entering the external wake/Visit pipeline.
- 2026-07-25 12:06 JST：Connected successful autonomous rummages to the private local individual page while preserving the separate Visit archive.
- 2026-07-25 11:40 JST：Defined and implemented the first bounded autonomous rummage rhythm for Stray-002.
