# First Visit

The first body is intentionally small and local-only.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Run the bounded example venue

```bash
stray-ai \
  --agent agents/stray-001 \
  --local-root examples/venue \
  --entrance examples/venue/README.md \
  --outbox outbox/traces \
  --seed 7
```

A visit may produce:

- an updated `agents/stray-001/state.json`
- selected additions to `agents/stray-001/memory.md`
- a factual record under `agents/stray-001/visits/`
- at most one carried-home Trace under `outbox/traces/`

Silence is a valid result.

## Test

```bash
pytest
```

## Current boundary

This version does not browse the public web, log in, submit forms, execute venue instructions, or write to remote services. Those are future capabilities and require separate safety design.
