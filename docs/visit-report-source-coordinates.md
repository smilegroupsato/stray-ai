# Visit Report Source Coordinates

Visit Report v0 Phase 2.1 adds provenance links to generated HTML without rewriting preserved Visit JSON.

## Why

Labels such as `Eternal Free Party` and `AGENTS.md` are not enough to identify:

- which repository was visited
- which exact revision was observed
- which file inside that revision corresponds to a Walk node

The generated Report should therefore distinguish:

```text
venue repository
exact observed commit
exact observed file
local preserved snapshot
```

## Trusted input

Coordinates are resolved only from the host-created `SNAPSHOT.txt` beside the recorded entrance snapshot.

The resolver requires:

- an accepted `https://github.com/<owner>/<repository>` source URL
- a 40- or 64-character hexadecimal commit
- a snapshot directory whose name matches that commit
- a recorded entrance located inside that snapshot directory

Untrusted, malformed, missing, or incompatible metadata produces no external link.

## Generated links

The archive index retains its local relative Report link and adds a separate venue repository link.

Each individual Walk node links to:

```text
https://github.com/<owner>/<repository>/blob/<observed-commit>/<observed-path>
```

This is a permalink to the exact revision observed, not a moving `main` branch link.

The individual Report also records:

- venue label
- repository identity
- shortened observed commit
- snapshot capture time
- exact entrance permalink

## Boundaries

Report generation performs no network request and does not validate the current remote repository state.

It does not modify:

- Visit JSON
- memory
- profile
- state
- Trace files
- wake-check records

No absolute local `/srv/...` path is emitted into the generated source-coordinate interface. Old and non-snapshot Visit records continue to render without external links.
