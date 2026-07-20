# Visitor Lifecycle

A persistent visitor needs a state that distinguishes being inside a visit from having returned home.

## States

```text
unborn
  No completed Visit JSON exists.

visiting
  The current process is reading one bounded venue snapshot. This state is held in memory and sent to the bounded brain, but is not persisted in a way that can strand the visitor inside a venue after a process crash.

resting
  A locally recorded visit attempt has ended. The visitor is home, whether it carried a Trace, left silently, or returned through a fail-closed exit.
```

At return:

- `current_location` becomes `null`
- `last_location` retains the final page as history
- `last_exit_reason`, `last_backend`, and `last_model` describe the latest completed attempt
- `rest_started_at` begins deterministic fatigue recovery

## Visit counters

`visit_count` means the number of completed, locally recorded Visit JSON attempts. It includes mock visits and fail-closed attempts because both are part of the preserved observation history.

Additional counters distinguish them:

- `llm_visit_count`: completed attempts using the command brain
- `accepted_brain_visit_count`: LLM attempts containing at least one accepted or corrected bounded decision
- `safe_exit_count`: attempts ending with `brain_failed_safe_exit`

These counters are reconstructed from preserved Visit JSON during migration, so old records remain the source for historical classification.

## Fatigue

Movement to another page adds `0.18` fatigue. Fatigue is clamped to `0.0..1.0`.

While resting, fatigue recovers deterministically at `0.04` per elapsed hour. Recovery is calculated before a future brain receives state. No scheduler or automatic wake decision is implied by recovery alone.

## Memory migration

The original bootstrap text said that no visit or memory yet existed. That sentence became false after the first visit and could be sent back to the model as self-memory.

The migration replaces only the exact legacy bootstrap block with timeless wording. Timestamped memories and model-authored memory entries are preserved.

Run the idempotent migration with:

```bash
stray-ai-migrate /srv/sgos/data/stray-ai/agents/stray-001
```

The devbox setup script runs the same migration after ensuring the persistent agent files exist.

## Safety

A failed adapter decision still produces a local Visit JSON and returns the visitor to `resting`. It does not create a Trace unless a valid bounded `carry_trace` decision was accepted.

The lifecycle adds no remote write, scheduler, cron job, systemd timer, or autonomous revisit.
