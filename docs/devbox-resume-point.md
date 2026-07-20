# Devbox Resume Point

Last updated: 2026-07-20

## Current state

Visit Report v0 Phase 3 and Phase 4 are merged to `main`.

- Phase 3 merge commit: `53a6179cbeeec8e05a917884b460d72f4838fba4`
- Phase 4 merge commit: `dcff16a922fc2b21c2565108cb3ace7ec0e73d39`
- roadmap completion commit: `f457487f30e8d38e2cf87e4030b2f5059dee025c`
- Internal Service Gateway serves `/srv/sgos/data/stray-ai/reports`
- Tailscale report routes were browser-checked successfully
- persistent source records must remain unchanged
- no Visit, wake check, scheduler, or new individual should be started as part of resume

The devbox working tree may still be on `report/multiple-individuals-v0`, even though the authoritative repository state is now `main`.

## First action on the next devbox session

```bash
set -euo pipefail

cd /srv/sgos/repos/stray-ai

git fetch origin
git switch main
git pull --ff-only origin main

bash scripts/setup_devbox.sh
/srv/sgos/data/stray-ai/generate-latest-report.sh
```

Expected test total: `44 passed`.

## Read-only checks

```bash
curl -I http://100.79.124.53/stray-ai/index.html
curl -I http://100.79.124.53/stray-ai/visits.html
curl -I http://100.79.124.53/stray-ai/latest.html
curl -I http://100.79.124.53/stray-ai/map.html
curl -I http://100.79.124.53/stray-ai/individuals/stray-001/index.html
curl -I http://100.79.124.53/stray-ai/individuals/stray-001/map.html
```

All routes should return HTTP 200.

## Browser entrances

- `http://100.79.124.53/stray-ai/index.html` — all-individual entrance
- `http://100.79.124.53/stray-ai/visits.html` — primary individual visit archive
- `http://100.79.124.53/stray-ai/latest.html` — primary compatibility latest report
- `http://100.79.124.53/stray-ai/map.html` — primary compatibility observed venue map
- `http://100.79.124.53/stray-ai/individuals/stray-001/index.html` — namespaced archive

## Next design topic

The next planned design topic is the **Stray AI world map** across visits, commits, venues, and individuals. It is not yet implemented and must remain separate from automatic Visit or wake behavior.
