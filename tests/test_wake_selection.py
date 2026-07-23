from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stray_ai.wake_selection import WakeSelectorCommand, run_wake_selection

_JST = ZoneInfo("Asia/Tokyo")
_NOW = datetime(2026, 7, 23, 12, 0, tzinfo=_JST)


def _habitat(tmp_path: Path, *, eligible: bool = True) -> tuple[Path, Path, Path]:
    agent = tmp_path / "synthetic-agent"
    agent.mkdir()
    (agent / "visits").mkdir()
    rest = _NOW - timedelta(hours=24 if eligible else 1)
    (agent / "profile.yml").write_text(
        "id: synthetic-stray\nwake:\n  minimum_rest_hours: 12\n"
        "  maximum_fatigue_to_consider: 0.5\n",
        encoding="utf-8",
    )
    (agent / "state.json").write_text(
        json.dumps(
            {
                "id": "synthetic-stray",
                "status": "resting",
                "current_location": None,
                "rest_started_at": rest.isoformat(),
                "fatigue": 0.2,
                "visit_count": 2,
                "unresolved_impulses": ["notice an opaque difference"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (agent / "memory.md").write_text("# Memory\nSECRET MEMORY TEXT\n", encoding="utf-8")
    venues = tmp_path / "venues"
    venues.mkdir()
    registry = tmp_path / "venues.yml"
    _registry(registry)
    return agent, venues, registry


def _registry(path: Path, *, reverse: bool = False, disabled_b: bool = False) -> None:
    entries = [
        {"venue_id": "venue-a", "display_name": "PRIVATE LABEL A", "selection_enabled": True},
        {
            "venue_id": "venue-b",
            "display_name": "PRIVATE LABEL B",
            "selection_enabled": not disabled_b,
        },
    ]
    if reverse:
        entries.reverse()
    path.write_text(
        "schema_version: 0.1\nvenues:\n"
        + "".join(
            f"  - venue_id: {entry['venue_id']}\n"
            f"    display_name: {entry['display_name']}\n"
            f"    selection_enabled: {str(entry['selection_enabled']).lower()}\n"
            for entry in entries
        ),
        encoding="utf-8",
    )


def _snapshot(venues: Path, venue: str, snapshot: str) -> Path:
    path = venues / venue / snapshot
    path.mkdir(parents=True)
    return path


def _visit(agent: Path, filename: str, venue: str, snapshot: str) -> None:
    (agent / "visits" / filename).write_text(
        json.dumps({"entrance": f"/synthetic/{venue}/{snapshot}/README.md"}),
        encoding="utf-8",
    )


def _selector(tmp_path: Path, source: str, *, timeout: float = 5) -> WakeSelectorCommand:
    script = tmp_path / f"selector-{len(list(tmp_path.glob('selector-*')))}.py"
    script.write_text(source, encoding="utf-8")
    return WakeSelectorCommand(
        [sys.executable, str(script)], label="synthetic-model", timeout_seconds=timeout
    )


def _run(
    agent: Path,
    venues: Path,
    registry: Path,
    candidates: list[str] | None = None,
    **kwargs: object,
) -> dict[str, object]:
    checked_at = kwargs.pop("now", _NOW)
    return run_wake_selection(
        agent_dir=agent,
        registry_path=registry,
        venues_root=venues,
        explicit_candidates=candidates,
        now=checked_at,  # type: ignore[arg-type]
        **kwargs,
    )


def test_body_gate_blocks_before_selector_invocation(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path, eligible=False)
    _snapshot(venues, "venue-a", "snap-a")
    marker = tmp_path / "invoked"
    selector = _selector(
        tmp_path,
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('yes')\n",
    )
    result = _run(agent, venues, registry, ["venue-a=snap-a"], selector=selector)
    assert result["decision"] == "remain_asleep"
    assert result["source"] == "deterministic_gate"
    assert result["selector"]["status"] == "not_invoked"  # type: ignore[index]
    assert not marker.exists()


def test_no_candidates_and_deterministic_changed_or_unchanged_sleep(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    assert _run(agent, venues, registry)["decision"] == "remain_asleep"
    _snapshot(venues, "venue-a", "old")
    _snapshot(venues, "venue-a", "new")
    _visit(agent, "01.json", "venue-a", "old")
    unchanged = _run(agent, venues, registry, ["venue-a=old"])
    changed = _run(agent, venues, registry, ["venue-a=new"])
    assert unchanged["candidates"][0]["changed"] is False  # type: ignore[index]
    assert changed["candidates"][0]["changed"] is True  # type: ignore[index]
    assert changed["decision"] == "remain_asleep"


def test_explicit_selector_choice_payload_is_sorted_and_private(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap-a")
    _snapshot(venues, "venue-b", "snap-b")
    capture = tmp_path / "payload.json"
    selector = _selector(
        tmp_path,
        f"""
import json, sys
from pathlib import Path
value = json.load(sys.stdin)
Path({str(capture)!r}).write_text(json.dumps(value))
print(json.dumps({{
 "decision":"select_venue","selected_venue_id":"venue-b",
 "observation":"opaque choice","reason":"bounded","reason_code":"unresolved_impulse"
}}))
""",
    )
    result = _run(
        agent,
        venues,
        registry,
        ["venue-b=snap-b", "venue-a=snap-a"],
        selector=selector,
    )
    assert result["decision"] == "select_venue"
    assert result["selected_venue_id"] == "venue-b"
    assert [item["venue_id"] for item in result["candidates"]] == ["venue-a", "venue-b"]  # type: ignore[index]
    payload_text = capture.read_text(encoding="utf-8")
    assert "SECRET MEMORY TEXT" not in payload_text
    assert "PRIVATE LABEL" not in payload_text
    assert str(tmp_path) not in payload_text
    assert "http" not in payload_text
    assert "command" not in payload_text


def test_registry_and_input_order_do_not_affect_candidate_order(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap-a")
    _snapshot(venues, "venue-b", "snap-b")
    first = _run(agent, venues, registry, ["venue-b=snap-b", "venue-a=snap-a"])
    _registry(registry, reverse=True)
    second = _run(
        agent, venues, registry, ["venue-a=snap-a", "venue-b=snap-b"],
        now=_NOW + timedelta(seconds=1),
    )
    assert first["candidates"] == second["candidates"]


def test_alternating_history_is_same_venue_only_and_no_history_unavailable(
    tmp_path: Path,
) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "a2")
    _snapshot(venues, "venue-b", "b1")
    _visit(agent, "01.json", "venue-a", "a1")
    _visit(agent, "02.json", "venue-b", "b1")
    result = _run(agent, venues, registry, ["venue-a=a2", "venue-b=b1"])
    assert result["candidates"][0]["previous_snapshot_id"] == "a1"  # type: ignore[index]
    assert result["candidates"][1]["previous_snapshot_id"] == "b1"  # type: ignore[index]
    (agent / "visits" / "02.json").unlink()
    result = _run(
        agent, venues, registry, ["venue-b=b1"], now=_NOW + timedelta(seconds=1)
    )
    fact = result["candidates"][0]  # type: ignore[index]
    assert fact["comparison_available"] is False
    assert fact["comparison_scope"] == "same_venue_no_history"
    assert fact["changed"] is False


@pytest.mark.parametrize(
    "candidate",
    [
        "venue-a=snap/escape",
        "venue-a=/absolute",
        "venue-a=..",
        "../venue=snap",
        "venue-a=.",
    ],
)
def test_unsafe_candidate_ids_fail_closed(tmp_path: Path, candidate: str) -> None:
    agent, venues, registry = _habitat(tmp_path)
    result = _run(agent, venues, registry, [candidate])
    assert result["candidate_validation"]["status"] == "rejected"  # type: ignore[index]
    assert result["decision"] == "remain_asleep"


def test_duplicate_unknown_disabled_missing_and_symlink_fail_closed(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap")
    outside = tmp_path / "outside"
    outside.mkdir()
    (venues / "venue-a" / "link").symlink_to(outside, target_is_directory=True)
    cases = [
        ["venue-a=snap", "venue-a=snap"],
        ["unknown=snap"],
        ["venue-a=missing"],
        ["venue-a=link"],
    ]
    for index, candidates in enumerate(cases):
        result = _run(
            agent, venues, registry, candidates, now=_NOW + timedelta(seconds=index)
        )
        assert result["candidate_validation"]["status"] == "rejected"  # type: ignore[index]
    _registry(registry, disabled_b=True)
    result = _run(agent, venues, registry, ["venue-b=snap"], now=_NOW + timedelta(seconds=5))
    assert result["candidate_validation"]["status"] == "rejected"  # type: ignore[index]


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        "schema_version: 9\nvenues: []\n",
        "schema_version: 0.1\nvenues: nope\n",
        "schema_version: 0.1\nvenues:\n  - nope\n",
        (
            "schema_version: 0.1\nvenues:\n  - venue_id: duplicate\n"
            "    display_name: A\n    selection_enabled: true\n"
            "  - venue_id: duplicate\n    display_name: B\n    selection_enabled: true\n"
        ),
    ],
)
def test_malformed_registry_fails_closed(tmp_path: Path, text: str) -> None:
    agent, venues, registry = _habitat(tmp_path)
    registry.write_text(text, encoding="utf-8")
    result = _run(agent, venues, registry)
    assert result["candidate_validation"]["status"] == "rejected"  # type: ignore[index]
    assert result["decision"] == "remain_asleep"


def test_current_symlinks_and_safe_omissions(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap-a")
    (venues / "venue-a" / "current").symlink_to("snap-a")
    result = _run(agent, venues, registry, use_current_snapshots=True)
    assert result["candidates"][0]["candidate_snapshot_id"] == "snap-a"  # type: ignore[index]
    assert result["current_snapshot_omissions"] == [
        {"venue_id": "venue-b", "reason": "usable current symlink absent"}
    ]


@pytest.mark.parametrize(
    "body",
    [
        "print('not json')",
        "print('{\"decision\":\"wake\"}')",
        (
            "print('{\"decision\":\"remain_asleep\",\"selected_venue_id\":null,"
            "\"observation\":\"x\",\"reason\":\"x\",\"reason_code\":\"bad\"}')"
        ),
        (
            "print('{\"decision\":\"select_venue\",\"selected_venue_id\":\"unknown\","
            "\"observation\":\"x\",\"reason\":\"x\",\"reason_code\":\"no_specific_reason\"}')"
        ),
        "raise SystemExit(2)",
        (
            "import json\nprint(json.dumps({'decision':'remain_asleep',"
            "'selected_venue_id':None,'observation':'x'*361,'reason':'x',"
            "'reason_code':'rest_preferred'}))"
        ),
    ],
)
def test_bad_selector_outputs_fail_closed(tmp_path: Path, body: str) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap")
    result = _run(
        agent,
        venues,
        registry,
        ["venue-a=snap"],
        selector=_selector(tmp_path, body),
    )
    assert result["decision"] == "remain_asleep"
    assert result["selector"]["status"] == "rejected"  # type: ignore[index]


def test_timeout_fails_closed(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap")
    selector = WakeSelectorCommand(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        label="slow",
        timeout_seconds=0.01,
    )
    result = _run(agent, venues, registry, ["venue-a=snap"], selector=selector)
    assert result["selector"]["status"] == "rejected"  # type: ignore[index]


def test_unique_records_and_all_other_files_are_byte_identical(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "snap")
    protected_dirs = ["wake_checks", "traces", "visit_requests", "reports"]
    for name in protected_dirs:
        directory = agent / name
        directory.mkdir()
        (directory / "evidence.txt").write_text(name, encoding="utf-8")
    before = {
        path.relative_to(agent): path.read_bytes()
        for path in agent.rglob("*")
        if path.is_file()
    }
    first = _run(agent, venues, registry, ["venue-a=snap"])
    second = _run(agent, venues, registry, ["venue-a=snap"])
    assert first["selection_file"] != second["selection_file"]
    for relative, content in before.items():
        assert (agent / relative).read_bytes() == content
    assert len(list((agent / "wake_selections").glob("*.json"))) == 2


def test_equal_candidates_have_no_order_fallback(tmp_path: Path) -> None:
    agent, venues, registry = _habitat(tmp_path)
    _snapshot(venues, "venue-a", "same")
    _snapshot(venues, "venue-b", "same")
    result = _run(agent, venues, registry, ["venue-b=same", "venue-a=same"])
    assert result["decision"] == "remain_asleep"
    assert result["selected_venue_id"] is None


def test_setup_launchers_keep_selection_separate() -> None:
    setup = Path("scripts/setup_devbox.sh").read_text(encoding="utf-8")
    for launcher in ("select-wake-venue.sh", "select-wake-venue-llm.sh"):
        assert launcher in setup
    selection_block = setup.split('cat > "$DATA_DIR/select-wake-venue.sh"', 1)[1]
    forbidden = [
        "snapshot_eternal",
        "stray-ai-wake ",
        "stray-ai-prepare-visit",
        "stray-ai-approve-visit",
        "stray-ai-execute-approved-visit",
        "stray-ai-report",
    ]
    assert not any(command in selection_block for command in forbidden)
