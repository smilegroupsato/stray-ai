#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-enable}"
REPO_DIR="${REPO_DIR:-/srv/sgos/repos/stray-ai}"
DATA_DIR="${DATA_DIR:-/srv/sgos/data/stray-ai}"
SERVICE_USER="${STRAY_SERVICE_USER:-${SUDO_USER:-taku}}"
SERVICE_NAME="stray-001-efp-outing.service"
TIMER_NAME="stray-001-efp-outing.timer"
SYSTEMD_DIR="/etc/systemd/system"

if (( EUID != 0 )); then
  echo "Run with sudo: sudo bash $0 $ACTION" >&2
  exit 1
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Service user does not exist: $SERVICE_USER" >&2
  exit 1
fi
if [[ ! "$REPO_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] ||
  [[ ! "$DATA_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]]; then
  echo "Repository and data paths must be simple absolute paths." >&2
  exit 1
fi
SERVICE_GROUP="$(id -gn "$SERVICE_USER")"

case "$ACTION" in
  enable)
    if [[ ! -d "$REPO_DIR" || -L "$REPO_DIR" ]]; then
      echo "Repository root is missing or unsafe: $REPO_DIR" >&2
      exit 1
    fi
    if [[ ! -d "$DATA_DIR/agents/stray-001" || -L "$DATA_DIR/agents/stray-001" ]]; then
      echo "Persistent stray-001 is missing or unsafe." >&2
      exit 1
    fi

    SERVICE_TMP="$(mktemp)"
    TIMER_TMP="$(mktemp)"
    trap 'rm -f "$SERVICE_TMP" "$TIMER_TMP"' EXIT

    cat >"$SERVICE_TMP" <<EOF
[Unit]
Description=Stray-001 invited autonomous visit to Eternal Free Party
After=network-online.target
Wants=network-online.target
ConditionPathIsDirectory=$REPO_DIR
ConditionPathIsDirectory=$DATA_DIR/agents/stray-001

[Service]
Type=oneshot
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$REPO_DIR
ExecStart=/usr/bin/bash $REPO_DIR/scripts/autonomous_visit_stray_001_efp.sh
TimeoutStartSec=20min
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0027
Nice=10
IOSchedulingClass=idle
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectHostname=true
ProtectClock=true
ReadOnlyPaths=$REPO_DIR
ReadWritePaths=$DATA_DIR
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
CapabilityBoundingSet=
AmbientCapabilities=
EOF

    cat >"$TIMER_TMP" <<EOF
[Unit]
Description=Give Stray-001 irregular invited EFP outing opportunities

[Timer]
OnActiveSec=5min
OnUnitInactiveSec=24h
RandomizedDelaySec=48h
AccuracySec=30min
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
EOF

    install -o root -g root -m 0644 "$SERVICE_TMP" "$SYSTEMD_DIR/$SERVICE_NAME"
    install -o root -g root -m 0644 "$TIMER_TMP" "$SYSTEMD_DIR/$TIMER_NAME"
    systemctl daemon-reload
    systemctl enable --now "$TIMER_NAME"
    systemctl --no-pager list-timers "$TIMER_NAME"
    ;;
  disable)
    systemctl disable --now "$TIMER_NAME"
    systemctl reset-failed "$SERVICE_NAME" || true
    echo "Stray-001 EFP autonomy timer disabled."
    ;;
  *)
    echo "Usage: sudo bash $0 [enable|disable]" >&2
    exit 2
    ;;
esac
