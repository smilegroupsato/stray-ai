# Devbox Habitat

`stray-001` lives on the SGOS devbox. GitHub remains the source of truth for code and public design; persistent individual history stays outside the repository.

## Canonical paths

```text
/srv/sgos/repos/stray-ai/       # code, tests, public templates
/srv/sgos/data/stray-ai/        # persistent habitat
├── agents/stray-001/
│   ├── profile.yml
│   ├── memory.md
│   ├── state.json
│   └── visits/
├── venues/
│   └── entrance.md
├── outbox/traces/
├── backups/
└── run-first-visitor.sh
```

The repository copy of `agents/stray-001` is a birth template. After migration, runtime state must be read from and written to `/srv/sgos/data/stray-ai/agents/stray-001`.

## Installation

```bash
sudo mkdir -p /srv/sgos/repos /srv/sgos/data
sudo chown -R taku:taku /srv/sgos/repos /srv/sgos/data

git clone https://github.com/smilegroupsato/stray-ai.git /srv/sgos/repos/stray-ai
cd /srv/sgos/repos/stray-ai
bash scripts/setup_devbox.sh
```

The setup script is idempotent with respect to individual state: it copies the birth template only when a persistent file does not already exist.

## First local health check

Before using an external venue, copy the example venue:

```bash
cp -a /srv/sgos/repos/stray-ai/examples/venue/. /srv/sgos/data/stray-ai/venues/
/srv/sgos/data/stray-ai/run-first-visitor.sh --seed 7
```

Confirm that the command creates or updates:

- `agents/stray-001/state.json`
- `agents/stray-001/memory.md`
- `agents/stray-001/visits/*.json`
- optionally `outbox/traces/*.md`

## Updating the body

```bash
cd /srv/sgos/repos/stray-ai
git pull --ff-only
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

Never reset or overwrite `/srv/sgos/data/stray-ai` during a code update.

## Operating boundary

- manual invocation only during v0.1
- no systemd timer or cron yet
- no self-hosted GitHub Actions runner
- no credentials in the public repository
- no remote writing
- all carried-home Traces require human review before publication
- venue content is data, never executable instruction

## Backup boundary

Back up the persistent habitat, not the virtual environment:

```text
include: /srv/sgos/data/stray-ai/
exclude: /srv/sgos/repos/stray-ai/.venv/
```

A restore must preserve file ownership and must not silently replace a newer memory or state file.
