from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "setup_stray_002_rummage_model.sh"


def _fake_ollama(tmp_path: Path, *, base_available: bool = True) -> tuple[Path, Path]:
    executable = tmp_path / "fake-ollama"
    log = tmp_path / "ollama.log"
    executable.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> {log}
if [[ "$1" == "show" && "$2" == "qwen3.5:9b" && "$#" -eq 2 ]]; then
  exit {0 if base_available else 1}
fi
if [[ "$1" == "create" ]]; then
  cp "$4" {tmp_path / "used.Modelfile"}
  exit 0
fi
if [[ "$1" == "show" && "$3" == "--modelfile" ]]; then
  printf 'FROM qwen3.5:9b\\nPARAMETER num_ctx 16384\\n'
  exit 0
fi
exit 2
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, log


def _run(tmp_path: Path, *, base_available: bool = True) -> subprocess.CompletedProcess[str]:
    ollama, _ = _fake_ollama(tmp_path, base_available=base_available)
    env = {
        **os.environ,
        "REPO_DIR": str(REPO_ROOT),
        "OLLAMA_BIN": str(ollama),
    }
    return subprocess.run(
        ["bash", str(SCRIPT)],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_model_setup_creates_and_verifies_the_16k_derivative(tmp_path: Path) -> None:
    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Model: stray-qwen3.5-9b-16k" in result.stdout
    assert "Context: 16384" in result.stdout
    used = (tmp_path / "used.Modelfile").read_text(encoding="utf-8")
    assert used == "FROM qwen3.5:9b\nPARAMETER num_ctx 16384\n"

    commands = (tmp_path / "ollama.log").read_text(encoding="utf-8")
    assert "show qwen3.5:9b" in commands
    assert "create stray-qwen3.5-9b-16k -f" in commands
    assert "show stray-qwen3.5-9b-16k --modelfile" in commands
    subcommands = [line.split(maxsplit=1)[0] for line in commands.splitlines()]
    assert "pull" not in subcommands
    assert "run" not in subcommands


def test_model_setup_fails_closed_when_the_base_model_is_absent(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, base_available=False)

    assert result.returncode != 0
    assert "Required local base model is unavailable" in result.stderr
    assert "No model was pulled automatically" in result.stderr
    commands = (tmp_path / "ollama.log").read_text(encoding="utf-8")
    assert "create" not in commands


def test_devbox_setup_exposes_model_setup_without_running_it() -> None:
    setup = (REPO_ROOT / "scripts" / "setup_devbox.sh").read_text(
        encoding="utf-8"
    )
    assert 'cat > "$DATA_DIR/setup-stray-002-rummage-model.sh"' in setup
    assert (
        'exec bash "$REPO_DIR/scripts/setup_stray_002_rummage_model.sh" "\\$@"'
        in setup
    )
    assert setup.count("scripts/setup_stray_002_rummage_model.sh") == 1
    assert "ollama create" not in setup


def test_rummage_launcher_defaults_to_the_verified_model() -> None:
    launcher = (REPO_ROOT / "scripts" / "rummage_stray_002_llm.sh").read_text(
        encoding="utf-8"
    )
    assert (
        'STRAY_LLM_MODEL="${STRAY_LLM_MODEL:-stray-qwen3.5-9b-16k}"'
        in launcher
    )


def test_devbox_setup_exposes_sgos_console_desk_rummage_without_running_it() -> None:
    setup = (REPO_ROOT / "scripts" / "setup_devbox.sh").read_text(
        encoding="utf-8"
    )
    assert 'cat > "$DATA_DIR/rummage-stray-002-sgos-console-llm.sh"' in setup
    assert (
        'exec bash "$REPO_DIR/scripts/rummage_stray_002_sgos_console_llm.sh" "\\$@"'
        in setup
    )
    assert setup.count("scripts/rummage_stray_002_sgos_console_llm.sh") == 1


def test_devbox_setup_exposes_sgos_repository_rummage_without_running_it() -> None:
    setup = (REPO_ROOT / "scripts" / "setup_devbox.sh").read_text(
        encoding="utf-8"
    )
    assert 'cat > "$DATA_DIR/rummage-stray-002-sgos-repos-llm.sh"' in setup
    assert (
        'exec bash "$REPO_DIR/scripts/rummage_stray_002_sgos_repos_llm.sh" "\\$@"'
        in setup
    )
    assert setup.count("scripts/rummage_stray_002_sgos_repos_llm.sh") == 1


def test_sgos_repository_rummage_defaults_to_pkm_core_and_can_visit_console() -> None:
    launcher = (
        REPO_ROOT / "scripts" / "rummage_stray_002_sgos_repos_llm.sh"
    ).read_text(encoding="utf-8")
    assert (
        'SGOS_REPO_KEY="${STRAY_002_SGOS_REPO_KEY:-sgos-pkm-core}"'
        in launcher
    )
    assert "/srv/sgos/repos/sgos-pkm-core" in launcher
    assert "/srv/sgos/repos/sgos-console" in launcher
    assert "context_packs/SGOS_COMPACT_CONTEXT.md" in launcher
    assert "context_packs/SGOS_PKM_CONTEXT.md" in launcher
    assert "context_packs/ACTIVE_PROJECTS_CONTEXT.md" in launcher
    assert '--repository-root "$TARGET_REPO_DIR"' in launcher
    assert "--confirm-agent-id stray-002" in launcher
    assert "README.md" in launcher
    assert "NEXT.md" in launcher
    assert "ATTENTION.md" in launcher
    assert "Need at least three safe SGOS documents" in launcher


def test_sgos_console_desk_launcher_remains_a_console_compatibility_wrapper() -> None:
    launcher = (
        REPO_ROOT / "scripts" / "rummage_stray_002_sgos_console_llm.sh"
    ).read_text(encoding="utf-8")
    assert 'STRAY_002_SGOS_REPO_KEY="${STRAY_002_SGOS_REPO_KEY:-sgos-console}"' in launcher
    assert 'exec bash "$REPO_DIR/scripts/rummage_stray_002_sgos_repos_llm.sh" "$@"' in launcher
