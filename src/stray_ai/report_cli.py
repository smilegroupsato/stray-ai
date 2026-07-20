from __future__ import annotations

import argparse
import json
from pathlib import Path

from .report import generate_report
from .report_sources import generate_source_aware_archive


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-report")
    parser.add_argument("--visit", type=Path)
    parser.add_argument("--visits-dir", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    state_path = args.state.resolve() if args.state else None
    output_dir = args.output_dir.resolve()

    if args.visits_dir is not None:
        result = generate_source_aware_archive(
            args.visits_dir.resolve(),
            output_dir,
            state_path,
        )
    elif args.visit is not None:
        visit_path = args.visit.resolve()
        report_path, _ = generate_report(
            visit_path,
            output_dir,
            state_path,
        )
        archive = generate_source_aware_archive(
            visit_path.parent,
            output_dir,
            state_path,
        )
        result = {
            "report_file": str(report_path),
            **archive,
        }
    else:
        parser.error("provide --visit or --visits-dir")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
