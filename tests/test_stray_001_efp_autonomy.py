from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "autonomous_visit_stray_001_efp.sh"
INSTALLER = REPO_ROOT / "scripts" / "install_stray_001_efp_autonomy.sh"
SNAPSHOT_VISITOR = REPO_ROOT / "scripts" / "visit_stray_001_efp_snapshot_llm.sh"
SNAPSHOT_ID = "a" * 40


def _init_repository(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "stray-test@example.invalid"],
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Stray Test"], cwd=path, check=True)
    (path / "README.md").write_text("body\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "body"], cwd=path, check=True, capture_output=True
    )


def _write_executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _habitat(tmp_path: Path, *, wake_decision: str = "request_visit"):
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    _init_repository(repo)

    agent = data / "agents" / "stray-001"
    agent.mkdir(parents=True)
    state = agent / "state.json"
    state.write_text(
        json.dumps({"status": "resting", "visit_count": 5}),
        encoding="utf-8",
    )

    snapshot = data / "venues" / "eternal-free-party" / SNAPSHOT_ID
    snapshot.mkdir(parents=True)
    for name in ("README.md", "REPOSITORY_CONTEXT.md", "AGENTS.md"):
        (snapshot / name).write_text(f"# {name}\n", encoding="utf-8")

    snapshot_count = data / "snapshot-count"
    snapshot_launcher = data / "snapshot.sh"
    _write_executable(
        snapshot_launcher,
        f"""printf '1\\n' > {snapshot_count}
printf '%s\\n' {snapshot}
""",
    )

    wake_file = agent / "wake_checks" / "wake.json"
    wake_file.parent.mkdir()
    wake_file.write_text("{}\n", encoding="utf-8")
    wake_launcher = data / "wake.sh"
    eligible = "true" if wake_decision == "request_visit" else "false"
    _write_executable(
        wake_launcher,
        f"""printf '%s\\n' '{{
  "decision": "{wake_decision}",
  "eligible": {eligible},
  "brain": {{"status": "accepted"}},
  "wake_file": "{wake_file}"
}}'
""",
    )

    visit_count = data / "visit-count"
    received_snapshot = data / "received-snapshot"
    visit_launcher = data / "visit.sh"
    _write_executable(
        visit_launcher,
        f"""printf '%s\\n' "$1" > {received_snapshot}
printf '1\\n' > {visit_count}
{sys.executable} - {state} <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
state = json.loads(path.read_text(encoding="utf-8"))
state["visit_count"] += 1
state["status"] = "resting"
path.write_text(json.dumps(state), encoding="utf-8")
PY
""",
    )

    report_count = data / "report-count"
    report_launcher = data / "report.sh"
    _write_executable(report_launcher, f"printf '1\\n' > {report_count}\n")

    launchers = {
        "snapshot": snapshot_launcher,
        "wake": wake_launcher,
        "visit": visit_launcher,
        "report": report_launcher,
    }
    evidence = {
        "snapshot_count": snapshot_count,
        "visit_count": visit_count,
        "received_snapshot": received_snapshot,
        "report_count": report_count,
    }
    return repo, data, launchers, evidence


def _run(repo: Path, data: Path, launchers: dict[str, Path], *, interval: int = 43200):
    env = {
        **os.environ,
        "REPO_DIR": str(repo),
        "DATA_DIR": str(data),
        "PYTHON_BIN": sys.executable,
        "STRAY_001_EFP_SNAPSHOT_LAUNCHER": str(launchers["snapshot"]),
        "STRAY_001_EFP_WAKE_LAUNCHER": str(launchers["wake"]),
        "STRAY_001_EFP_VISIT_LAUNCHER": str(launchers["visit"]),
        "STRAY_001_EFP_REPORT_LAUNCHER": str(launchers["report"]),
        "STRAY_001_EFP_MIN_INTERVAL_SECONDS": str(interval),
        "STRAY_001_EFP_SNAPSHOT_TIMEOUT": "30s",
        "STRAY_001_EFP_WAKE_TIMEOUT": "30s",
        "STRAY_001_EFP_VISIT_TIMEOUT": "30s",
        "STRAY_001_EFP_REPORT_TIMEOUT": "30s",
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _decisions(data: Path) -> list[dict[str, object]]:
    path = (
        data
        / "agents"
        / "stray-001"
        / "autonomy"
        / "eternal-free-party"
        / "decisions.jsonl"
    )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_accepted_wake_visits_exact_snapshot_and_returns(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path)

    result = _run(repo, data, launchers)

    assert result.returncode == 0, result.stderr
    assert "visited Eternal Free Party" in result.stdout
    assert evidence["visit_count"].read_text(encoding="utf-8").strip() == "1"
    assert evidence["received_snapshot"].read_text(encoding="utf-8").strip().endswith(
        SNAPSHOT_ID
    )
    assert evidence["report_count"].read_text(encoding="utf-8").strip() == "1"
    state = json.loads(
        (data / "agents" / "stray-001" / "state.json").read_text(encoding="utf-8")
    )
    assert state == {"status": "resting", "visit_count": 6}
    decisions = _decisions(data)
    assert [item["decision"] for item in decisions] == [
        "consider_visit",
        "visit",
        "rest",
    ]
    assert all(item["remote_write_allowed"] is False for item in decisions)


def test_remain_asleep_does_not_visit(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path, wake_decision="remain_asleep")

    result = _run(repo, data, launchers)

    assert result.returncode == 0, result.stderr
    assert "chose not to go" in result.stdout
    assert not evidence["visit_count"].exists()
    assert [item["decision"] for item in _decisions(data)] == [
        "consider_visit",
        "remain_asleep",
    ]


def test_cooldown_prevents_snapshot_and_second_visit(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path)
    first = _run(repo, data, launchers)

    evidence["snapshot_count"].unlink()
    second = _run(repo, data, launchers)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "minimum interval has not elapsed" in second.stdout
    assert not evidence["snapshot_count"].exists()


def test_dirty_repository_keeps_stray_001_resting(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path)
    (repo / "uncommitted.md").write_text("do not cross\n", encoding="utf-8")

    result = _run(repo, data, launchers)

    assert result.returncode == 0
    assert "working tree is not clean" in result.stderr
    assert not evidence["snapshot_count"].exists()


def test_non_resting_individual_does_not_open_an_outing(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path)
    state = data / "agents" / "stray-001" / "state.json"
    state.write_text(json.dumps({"status": "visiting", "visit_count": 5}), encoding="utf-8")

    result = _run(repo, data, launchers)

    assert result.returncode == 0
    assert "currently visiting" in result.stderr
    assert not evidence["snapshot_count"].exists()


def test_failed_visit_has_no_success_marker(tmp_path: Path) -> None:
    repo, data, launchers, _ = _habitat(tmp_path)
    _write_executable(launchers["visit"], "exit 7\n")

    result = _run(repo, data, launchers)

    assert result.returncode == 7
    autonomy = data / "agents" / "stray-001" / "autonomy" / "eternal-free-party"
    assert not (autonomy / "last_success_epoch").exists()
    assert [item["decision"] for item in _decisions(data)] == [
        "consider_visit",
        "visit",
        "rest_after_failure",
    ]


def test_report_failure_does_not_repeat_successful_visit(tmp_path: Path) -> None:
    repo, data, launchers, evidence = _habitat(tmp_path)
    _write_executable(launchers["report"], "exit 9\n")

    first = _run(repo, data, launchers)
    second = _run(repo, data, launchers)

    assert first.returncode == 9
    assert second.returncode == 0
    assert "minimum interval has not elapsed" in second.stdout
    assert evidence["visit_count"].read_text(encoding="utf-8").strip() == "1"
    decisions = [item["decision"] for item in _decisions(data)]
    assert decisions == [
        "consider_visit",
        "visit",
        "rest_after_report_failure",
        "remain_asleep",
    ]


def test_installer_uses_an_irregular_hardened_timer() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "OnActiveSec=5min" in installer
    assert "OnUnitInactiveSec=24h" in installer
    assert "RandomizedDelaySec=48h" in installer
    assert "AccuracySec=30min" in installer
    assert "TimeoutStartSec=20min" in installer
    assert "NoNewPrivileges=true" in installer
    assert "ReadOnlyPaths=$REPO_DIR" in installer
    assert "ReadWritePaths=$DATA_DIR" in installer
    assert "CapabilityBoundingSet=" in installer
    assert 'systemctl enable --now "$TIMER_NAME"' in installer


def test_snapshot_visit_launcher_never_fetches_or_publishes() -> None:
    launcher = SNAPSHOT_VISITOR.read_text(encoding="utf-8")

    assert 'SNAPSHOT_DIR="${1:-}"' in launcher
    assert "snapshot_eternal_free_party.sh" not in launcher
    assert "git clone" not in launcher
    assert "git fetch" not in launcher
    assert "github" not in launcher.lower()
    assert "run-first-visitor.sh" in launcher
    assert "--arrival-path REPOSITORY_CONTEXT.md AGENTS.md" in launcher
