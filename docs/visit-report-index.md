# Visit Report v0 — Phase 2 Index

Phase 2 adds a static entrance to the preserved Visit records of one individual.

The index is an observation window, not a dashboard. It has no controls, starts no visit, wakes no individual, and sends nothing remotely.

## Generated files

Archive mode reads the local Visit JSON directory:

```text
/srv/sgos/data/stray-ai/agents/stray-001/visits/
```

and writes only generated HTML under:

```text
/srv/sgos/data/stray-ai/reports/
```

The result is:

```text
reports/
├── index.html
├── latest.html
├── YYYY-MM-DD_HHMMSS.html
└── ...
```

`index.html` links to named reports with relative URLs. It does not know the HTTP host, port, server, URL prefix, or whether it is opened directly from the filesystem.

## Generation

```bash
stray-ai-report \
  --visits-dir /srv/sgos/data/stray-ai/agents/stray-001/visits \
  --state /srv/sgos/data/stray-ai/agents/stray-001/state.json \
  --output-dir /srv/sgos/data/stray-ai/reports
```

The existing devbox launcher runs the same archive mode:

```text
/srv/sgos/data/stray-ai/generate-latest-report.sh
```

A normal single-visit report generation also refreshes the archive after the Visit JSON has been preserved.

## What the index observes

The index includes:

- visitor identity
- current lifecycle status
- persistent and visible Visit counts
- latest recorded visit
- started time
- conservative venue label derived from the entrance path
- backend and model
- exit result
- place count
- memory count
- Trace presence

It does not include venue page content or wake-check records.

## Failure boundary

One malformed or semantically unusable Visit JSON does not prevent valid records from rendering. Its filename is returned in `skipped_visit_files` and is not copied into HTML.

An empty Visit directory still produces a truthful `index.html`. It removes a stale generated `latest.html` rather than presenting an old page as current.

## HTTP independence

Caddy or another internal HTTP service may later serve the reports directory. That deployment is separate from the report generator.

No server process, listener, firewall rule, public URL, JavaScript, remote asset, analytics request, or remote write is introduced by Phase 2.
