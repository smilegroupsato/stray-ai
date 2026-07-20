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

Coordinates are resolved only from the host-created `SNAPSHOT.txt` beside a recorded visit location.

The resolver requires:

- an accepted `https://github.com/<owner>/<repository>` source URL
- a 40- or 64-character hexadecimal commit
- a snapshot directory whose name matches that commit
- one unambiguous trusted snapshot identity across the recorded entrance, arrival path, and step locations

Untrusted, malformed, missing, ambiguous, or incompatible metadata produces no external link.

## Generated links

The archive index retains its local relative Report link and adds a separate venue repository link where trusted coordinates exist.

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

The top `Stray AI · Visit Report v0` label links to the relative path `index.html`. Every individual Report, including local-only records without source coordinates, can therefore return to the archive entrance without depending on a host name, port, or HTTP server configuration.

## Boundaries

Report generation performs no network request and does not validate the current remote repository state.

It does not modify:

- Visit JSON
- memory
- profile
- state
- Trace files
- wake-check records

No absolute local `/srv/...` path is emitted into the generated source-coordinate interface. Old, local-only, and non-snapshot Visit records continue to render without fabricated external links.
