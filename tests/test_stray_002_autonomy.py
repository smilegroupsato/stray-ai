from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "autonomous_rummage_stray_002.sh"
INSTALLER = REPO_ROOT / "scripts" / "install_stray_002_autonomy.sh"


def _init_repository(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "stray-test@example.invalid"],
        cwd=path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Stray Test"], cwd=path, check=True)
    (path / "README.md").write_text("shelf\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "shelf"], cwd=path, check=True, capture_output=True)


def _habitat(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    _init_repository(repo)
    agent = data / "agents" / "stray-002"
    agent.mkdir(parents=True)
    (agent / "state.json").write_text(
        json.dumps(
            {
                "status": "resting",
                "current_location": "damp-underground-library-shelf-gap",
            }
        ),
        encoding="utf-8",
    )
    count = data / "run-count"
    launcher = tmp_path / "fake-rummage.sh"
    launcher.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
count=0
if [[ -f {count} ]]; then
  count="$(<{count})"
fi
printf '%s\\n' "$((count + 1))" > {count}
""",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    report_count = data / "report-count"
    report_launcher = data / "generate-latest-report.sh"
    report_launcher.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
count=0
if [[ -f {report_count} ]]; then
  count="$(<{report_count})"
fi
printf '%s\\n' "$((count + 1))" > {report_count}
""",
        encoding="utf-8",
    )
    report_launcher.chmod(0o755)
    return repo, data, launcher, count


def _run(repo: Path, data: Path, launcher: Path, *, interval: int = 72000):
    env = {
        **os.environ,
        "REPO_DIR": str(repo),
        "DATA_DIR": str(data),
        "PYTHON_BIN": sys.executable,
        "STRAY_AUTONOMY_RUMMAGE_LAUNCHER": str(launcher),
        "STRAY_AUTONOMY_REPORT_LAUNCHER": str(data / "generate-latest-report.sh"),
        "STRAY_AUTONOMY_MIN_INTERVAL_SECONDS": str(interval),
        "STRAY_AUTONOMY_RUN_TIMEOUT": "30s",
        "STRAY_AUTONOMY_REPORT_TIMEOUT": "30s",
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_autonomous_opportunity_runs_once_and_records_return(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)

    result = _run(repo, data, launcher)

    assert result.returncode == 0, result.stderr
    assert count.read_text(encoding="utf-8").strip() == "1"
    assert (data / "report-count").read_text(encoding="utf-8").strip() == "1"
    autonomy = data / "agents" / "stray-002" / "autonomy"
    assert (autonomy / "last_success_epoch").read_text(encoding="utf-8").strip().isdigit()
    decisions = [
        json.loads(line)
        for line in (autonomy / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["decision"] for item in decisions] == ["rummage", "rest"]
    assert decisions[-1]["reason"] == "rummage_complete_report_refreshed"


def test_cooldown_prevents_an_immediate_second_rummage(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    first = _run(repo, data, launcher)

    second = _run(repo, data, launcher)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "minimum interval has not elapsed" in second.stdout
    assert count.read_text(encoding="utf-8").strip() == "1"
    assert (data / "report-count").read_text(encoding="utf-8").strip() == "1"


def test_dirty_repository_keeps_stray_002_resting(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    (repo / "uncommitted.md").write_text("do not cross\n", encoding="utf-8")

    result = _run(repo, data, launcher)

    assert result.returncode == 0
    assert "working tree is not clean" in result.stderr
    assert not count.exists()
    assert not (data / "agents" / "stray-002" / "autonomy").exists()


def test_non_main_branch_keeps_stray_002_resting(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    subprocess.run(["git", "switch", "-c", "agent/other-work"], cwd=repo, check=True)

    result = _run(repo, data, launcher)

    assert result.returncode == 0
    assert "repository is not on main" in result.stderr
    assert not count.exists()


def test_non_resting_state_does_not_open_an_autonomy_run(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    state = data / "agents" / "stray-002" / "state.json"
    state.write_text(json.dumps({"status": "rummaging"}), encoding="utf-8")

    result = _run(repo, data, launcher)

    assert result.returncode == 0
    assert "currently rummaging" in result.stderr
    assert not count.exists()
    assert not (data / "agents" / "stray-002" / "autonomy").exists()


def test_failed_rummage_is_recorded_without_a_success_marker(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    launcher.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    launcher.chmod(0o755)

    result = _run(repo, data, launcher)

    assert result.returncode == 7
    autonomy = data / "agents" / "stray-002" / "autonomy"
    assert not (autonomy / "last_success_epoch").exists()
    decisions = [
        json.loads(line)
        for line in (autonomy / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["decision"] for item in decisions] == ["rummage", "rest_after_failure"]


def test_report_failure_does_not_repeat_a_successful_rummage(tmp_path: Path) -> None:
    repo, data, launcher, count = _habitat(tmp_path)
    report_launcher = data / "generate-latest-report.sh"
    report_launcher.write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8")
    report_launcher.chmod(0o755)

    first = _run(repo, data, launcher)
    second = _run(repo, data, launcher)

    assert first.returncode == 9
    assert "individual page refresh failed" in first.stderr
    assert second.returncode == 0
    assert "minimum interval has not elapsed" in second.stdout
    assert count.read_text(encoding="utf-8").strip() == "1"
    autonomy = data / "agents" / "stray-002" / "autonomy"
    assert (autonomy / "last_success_epoch").is_file()
    decisions = [
        json.loads(line)
        for line in (autonomy / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["decision"] for item in decisions] == [
        "rummage",
        "rest_after_report_failure",
        "remain_asleep",
    ]


def test_installer_uses_a_bounded_low_frequency_timer() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "OnActiveSec=5min" in installer
    assert "OnUnitInactiveSec=24h" in installer
    assert "RandomizedDelaySec=30min" in installer
    assert "TimeoutStartSec=15min" in installer
    assert "NoNewPrivileges=true" in installer
    assert "ReadWritePaths=$DATA_DIR" in installer
    assert 'systemctl enable --now "$TIMER_NAME"' in installer
