# Bounded LLM Brain

The visitor's body remains deterministic even when a language model is connected.

```text
host body
├── chooses the bounded venue snapshot
├── reads only local Markdown/text files
├── enforces the four-place limit
├── enumerates valid local links
├── validates every model response
├── writes state, memory, Visit JSON, Trace, and HTML locally
└── never gives the model a remote-write tool

model brain
├── notices one page at a time
├── chooses one numbered local link, silence, or one carried-home Trace
├── proposes short memories
└── returns JSON only
```

## Decision protocol

The core sends one JSON request over stdin to a subprocess adapter. The adapter must return one JSON object over stdout.

```json
{
  "action": "follow_link | leave_silently | carry_trace",
  "link_index": 0,
  "observation": "what drew attention",
  "memories": ["short memory"],
  "trace": "short local Trace or null"
}
```

The model never supplies a filesystem path or URL. `link_index` can only select from candidates that the host already resolved inside the current immutable venue snapshot.

Invalid JSON, an invalid action, an out-of-range link, a timeout, or an adapter process failure becomes a rejected decision. The visitor leaves safely, preserves the Visit JSON, and produces an HTML report showing the failure.

## Included adapter

`scripts/openai_compatible_brain.py` calls a configured `/chat/completions` endpoint. It can point at a local model server or a remote compatible API.

Configuration is read only from the process environment:

```text
STRAY_LLM_MODEL          required model identifier
STRAY_LLM_BASE_URL       default: http://127.0.0.1:11434/v1
STRAY_LLM_API_KEY        optional for local; required for remote endpoints
OPENAI_API_KEY           accepted as an alternative key variable
STRAY_LLM_TEMPERATURE    default: 0.7
STRAY_LLM_MAX_TOKENS     default: 600
STRAY_LLM_HTTP_TIMEOUT   default: 40 seconds
STRAY_LLM_JSON_MODE      set to 1 only when the endpoint supports JSON mode
```

The adapter does not print or persist credentials.

## Prepare the branch on devbox

Before the PR is merged:

```bash
cd /srv/sgos/repos/stray-ai
git fetch origin agent/bounded-llm-brain
git switch --track origin/agent/bounded-llm-brain \
  || git switch agent/bounded-llm-brain
git pull --ff-only

bash -n scripts/setup_devbox.sh scripts/snapshot_eternal_free_party.sh
bash scripts/setup_devbox.sh
```

The setup creates two separate launchers:

```text
/srv/sgos/data/stray-ai/visit-eternal-free-party.sh
/srv/sgos/data/stray-ai/visit-eternal-free-party-llm.sh
```

The first remains deterministic `mock`. The second enables the command brain.

## Local compatible endpoint

Set the model identifier expected by the local server:

```bash
export STRAY_LLM_BASE_URL="http://127.0.0.1:11434/v1"
export STRAY_LLM_MODEL="YOUR_LOCAL_MODEL"

/srv/sgos/data/stray-ai/visit-eternal-free-party-llm.sh
```

No API key is required when the endpoint hostname is `localhost`, `127.0.0.1`, or `::1`.

## Remote compatible endpoint

Set the endpoint, model, and key in the current shell. Do not place the key in the public repository or persistent habitat scripts.

```bash
export STRAY_LLM_BASE_URL="https://YOUR_ENDPOINT/v1"
export STRAY_LLM_MODEL="YOUR_MODEL"
read -rsp "API key: " STRAY_LLM_API_KEY
export STRAY_LLM_API_KEY
echo

/srv/sgos/data/stray-ai/visit-eternal-free-party-llm.sh
unset STRAY_LLM_API_KEY
```

## What to inspect

After the visit:

```text
/srv/sgos/data/stray-ai/reports/latest.html
```

The report shows:

- backend and model label
- route through the venue
- observation at each model-controlled step
- accepted, corrected, or rejected decision status
- safe adapter error text without credentials
- memories and carried-home Trace

A carried-home Trace is still local. Human review is required before any publication decision.
