#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
export STRAY_002_SGOS_REPO_KEY="${STRAY_002_SGOS_REPO_KEY:-sgos-console}"
exec bash "$REPO_DIR/scripts/rummage_stray_002_sgos_repos_llm.sh" "$@"
