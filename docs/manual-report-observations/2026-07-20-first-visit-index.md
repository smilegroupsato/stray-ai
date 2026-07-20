# First Visit Index — 2026-07-20

## Scope

The persistent `stray-001` habitat on devbox generated the first Visit Report v0 Phase 2 archive from the four preserved Visit JSON records.

The operation generated static HTML only. It did not start a visit, run a wake check, invoke a model, read venue page content, configure an HTTP server, or write remotely.

## Environment

- host: devbox
- repository branch: `report/visit-index-v0`
- local Python: 3.14.4
- local test result: 26 passed
- GitHub Actions: Python 3.11 and 3.12 passed

## Generated archive

```text
/srv/sgos/data/stray-ai/reports/index.html
/srv/sgos/data/stray-ai/reports/latest.html
/srv/sgos/data/stray-ai/reports/2026-07-20_121935.html
/srv/sgos/data/stray-ai/reports/2026-07-20_120832.html
/srv/sgos/data/stray-ai/reports/2026-07-20_111436.html
/srv/sgos/data/stray-ai/reports/2026-07-20_104432.html
```

The archive loaded four valid Visit JSON records and skipped none.

## Index validation

The report links were ordered newest first:

```text
2026-07-20_121935.html
2026-07-20_120832.html
2026-07-20_111436.html
2026-07-20_104432.html
```

Validation confirmed:

- every report link was relative
- `latest.html` matched the newest named report
- the visitor identity and bounded venue label were present
- venue page names and page content were not copied into the index
- no script element was present
- no hostname, port, server path, or Caddy configuration was embedded

## Preservation

Before and after generation:

```text
Visit JSON:    4 -> 4
Trace files:   1 -> 1
wake records:  1 -> 1
```

SHA-256 manifests confirmed that the visitor profile, memory, state, Visit JSON files, Trace files, and wake records were unchanged.

## Result

Visit Report v0 Phase 2 now provides a static chronological entrance to the recorded visits of one persistent individual. The HTTP layer may later serve the reports directory without changing the generated archive or its relative links.
