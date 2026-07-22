from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .visit_request_admin import (
    VisitRequestAdminError,
    build_review_collection,
    render_review_html,
)

_PUBLISHED_RELATIVE_PATH = Path("request-review/index.html")
_FORBIDDEN_HTML_MARKERS = (
    "/srv/",
    "snapshot_root",
    "brain_command",
    "<button",
    "<form",
    "javascript:",
    "file://",
)


class GatewayRequestReviewError(RuntimeError):
    pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _safe_destination(report_root: Path) -> tuple[Path, Path]:
    if not report_root.is_dir():
        raise GatewayRequestReviewError("report root must be an existing directory")
    root = report_root.resolve()
    review_dir = root / _PUBLISHED_RELATIVE_PATH.parent
    if review_dir.exists() and review_dir.is_symlink():
        raise GatewayRequestReviewError("request-review directory must not be a symlink")
    review_dir.mkdir(parents=True, exist_ok=True)
    resolved_dir = review_dir.resolve()
    try:
        resolved_dir.relative_to(root)
    except ValueError as exc:
        raise GatewayRequestReviewError("request-review directory escapes the report root") from exc
    destination = resolved_dir / _PUBLISHED_RELATIVE_PATH.name
    if destination.exists() and destination.is_symlink():
        raise GatewayRequestReviewError("published index must not be a symlink")

    json_files = sorted(
        path.relative_to(root).as_posix()
        for path in resolved_dir.glob("*.json*")
        if path.is_file()
    )
    if json_files:
        raise GatewayRequestReviewError(
            "Gateway Request review directory contains JSON-like files: "
            + ", ".join(json_files)
        )
    return root, destination


def _assert_safe_html(rendered: str) -> None:
    lowered = rendered.lower()
    found = [marker for marker in _FORBIDDEN_HTML_MARKERS if marker.lower() in lowered]
    if found:
        raise GatewayRequestReviewError(
            "rendered Request review failed the Gateway safety check: " + ", ".join(found)
        )
    if "このページは読み取り専用です" not in rendered:
        raise GatewayRequestReviewError("rendered Request review lost its read-only notice")


def publish_gateway_request_review(
    *,
    agent_dir: Path,
    report_root: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    try:
        collection = build_review_collection(
            agent_dir=agent_dir.resolve(),
            generated_at=generated_at,
        )
        rendered = render_review_html(collection)
    except VisitRequestAdminError as exc:
        raise GatewayRequestReviewError(str(exc)) from exc

    _assert_safe_html(rendered)
    _, destination = _safe_destination(report_root)
    _atomic_write_text(destination, rendered)

    return {
        "published": True,
        "html_output": str(destination),
        "gateway_path": "/stray-ai/request-review/index.html",
        "request_count": collection["request_count"],
        "status_counts": collection["status_counts"],
        "boundaries": {
            "read_only": True,
            "venue_content_read": False,
            "contains_controls": False,
            "json_published": False,
            "automatic_publish": False,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stray-ai-publish-request-review")
    parser.add_argument("--agent", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    try:
        result = publish_gateway_request_review(
            agent_dir=args.agent,
            report_root=args.report_root,
        )
    except GatewayRequestReviewError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
