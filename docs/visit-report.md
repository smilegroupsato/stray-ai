# Visit Report v0

Visit Report turns one persistent visit record into a standalone HTML page that can be opened in any browser.

## What it shows

- the ordered route through the venue
- how the visit ended
- whether a Trace came home
- memories selected during the visit
- the visitor's current status, visit count, fatigue, and location
- the source visit-record filename

The report contains no remote assets, JavaScript, or external service calls.

## Devbox paths

```text
/srv/sgos/data/stray-ai/reports/
├── 2026-07-20_104432.html
└── latest.html
```

`latest.html` is replaced after each successful report generation. Timestamped reports remain as visit history.

## Automatic generation

After `scripts/setup_devbox.sh` is rerun, `run-first-visitor.sh` generates an HTML report after every successful visit.

```bash
/srv/sgos/data/stray-ai/run-first-visitor.sh --seed 7
```

The visit remains valid even if report rendering fails. The launcher prints a warning instead of deleting or rolling back the visit record.

## Generate the current report without another visit

```bash
/srv/sgos/data/stray-ai/generate-latest-report.sh
```

## Open from a desktop connected through Tailscale

Start a temporary read-only-style static file server bound to the devbox Tailscale address:

```bash
cd /srv/sgos/data/stray-ai/reports
python3 -m http.server 8765 --bind 100.79.124.53
```

Then open the devbox Tailscale address on port `8765` and select `latest.html`. Stop the server with `Ctrl+C` after viewing.

Do not bind this temporary server to a public interface or forward the port from the router.
