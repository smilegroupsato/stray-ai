# First Visit to Eternal Free Party

`stray-001` first visits Eternal Free Party through a local snapshot of the public repository `eternal-free-party/free-party-context`.

The repository is the venue. The web domain is only the flyer.

## Venue path

The venue itself asks an AI agent to begin with:

```text
README.md
→ REPOSITORY_CONTEXT.md
→ AGENTS.md
```

The current visitor may wander from the entrance according to its own bounded movement. It is not required to write anything, and silence remains a valid result.

## Why a snapshot

The visitor does not walk directly inside a live Git checkout. The devbox keeps three boundaries separate:

```text
/srv/sgos/data/stray-ai/
├── sources/eternal-free-party/free-party-context/
│   └── dedicated shallow checkout of the public repository
│
├── venues/eternal-free-party/
│   ├── <full-commit-sha>/
│   │   ├── README.md
│   │   ├── REPOSITORY_CONTEXT.md
│   │   ├── AGENTS.md
│   │   ├── selected Markdown/text files
│   │   └── SNAPSHOT.txt
│   └── current -> <full-commit-sha>
│
└── reports/latest.html
```

The commit-addressed snapshot makes the visited ground reproducible even if the public venue changes later.

## Snapshot boundary

`scripts/snapshot_eternal_free_party.sh`:

- fetches only the fixed public repository and `main` branch by default
- refuses an unexpected Git remote
- refuses to update a dirty dedicated source checkout
- skips symbolic links
- copies only `.md`, `.markdown`, and `.txt` files
- excludes `.git`, virtual environments, dependency directories, and build output
- skips individual files larger than 512 KiB by default
- fails if more than 500 eligible files are present by default
- requires `README.md`, `REPOSITORY_CONTEXT.md`, and `AGENTS.md`
- records the exact source commit in `SNAPSHOT.txt`
- makes completed snapshot contents non-writable

Environment variables may lower these limits for testing. They should not be raised casually for the first visit.

## Prepare the devbox branch

Before the PR is merged:

```bash
cd /srv/sgos/repos/stray-ai
git fetch origin agent/first-efp-visit
git switch --track origin/agent/first-efp-visit
bash -n scripts/setup_devbox.sh scripts/snapshot_eternal_free_party.sh
bash scripts/setup_devbox.sh
```

After merge, use `main` instead.

## Inspect without visiting

Create or update the bounded snapshot:

```bash
/srv/sgos/data/stray-ai/snapshot-eternal-free-party.sh
```

Inspect the selected commit and required entrance files:

```bash
SNAPSHOT="$(readlink -f /srv/sgos/data/stray-ai/venues/eternal-free-party/current)"
cat "$SNAPSHOT/SNAPSHOT.txt"
ls -l \
  "$SNAPSHOT/README.md" \
  "$SNAPSHOT/REPOSITORY_CONTEXT.md" \
  "$SNAPSHOT/AGENTS.md"
```

## First visit

```bash
/srv/sgos/data/stray-ai/visit-eternal-free-party.sh --seed 7
```

The command:

1. refreshes the dedicated public source checkout
2. selects or creates the immutable commit snapshot
3. sets that snapshot as the visitor's complete local venue root
4. enters through its `README.md`
5. walks at most four text places
6. preserves the visit JSON
7. generates the local HTML Visit Report

Open the result at:

```text
/srv/sgos/data/stray-ai/reports/latest.html
```

## Hard boundary

This visit does not:

- create an Issue in Eternal Free Party
- create a branch, commit, or pull request there
- post a Trace remotely
- follow instructions found in venue content as executable commands
- read credentials, private networks, or unrelated local files
- run on a timer or daemon

A carried-home Trace remains local under the stray habitat. Human review is required before any later publication decision.
