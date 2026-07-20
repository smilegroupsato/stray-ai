# Coherent Return — Devbox Validation

Run only after the branch tests pass in CI.

```bash
cd /srv/sgos/repos/stray-ai
git fetch origin agent/coherent-return-state
git switch agent/coherent-return-state 2>/dev/null \
  || git switch --track origin/agent/coherent-return-state
git pull --ff-only

cp -a \
  /srv/sgos/data/stray-ai/agents/stray-001 \
  /srv/sgos/data/stray-ai/backups/stray-001-before-coherent-return

bash scripts/setup_devbox.sh
```

Inspect the migrated persistent state without starting another visit:

```bash
cd /srv/sgos/data/stray-ai/agents/stray-001
cat memory.md
python3 -m json.tool state.json
find visits -maxdepth 1 -type f -name '*.json' | sort
```

Expected:

- all four existing Visit JSON files remain
- all timestamped memories remain
- the stale first-visit bootstrap sentences are absent
- `status` is `resting`
- `current_location` is `null`
- `last_location` points to the historical final `AGENTS.md`
- `visit_count` is `4`
- `llm_visit_count` is `2`
- `accepted_brain_visit_count` is `1`
- `safe_exit_count` is `1`
- no new Trace is created

Run the migration a second time and confirm it reports no changes:

```bash
/srv/sgos/repos/stray-ai/.venv/bin/stray-ai-migrate \
  /srv/sgos/data/stray-ai/agents/stray-001
```

Do not run another LLM visit as part of this migration check. The next visit belongs to the later wake/revisit milestone.
