from __future__ import annotations

import argparse
import json
from pathlib import Path

from .report import generate_report
from .report_source_archive import generate_source_aware_archive
from .report_world_collection import generate_world_report_collection


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai-report")
    parser.add_argument("--visit", type=Path)
    parser.add_argument("--visits-dir", type=Path)
    parser.add_argument("--agents-dir", type=Path)
    parser.add_argument("--primary-agent")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    selected_modes = sum(
        value is not None for value in (args.visit, args.visits_dir, args.agents_dir)
    )
    if selected_modes != 1:
        parser.error("provide exactly one of --visit, --visits-dir, or --agents-dir")

    output_dir = args.output_dir.resolve()

    if args.agents_dir is not None:
        if args.state is not None:
            parser.error("--state is not used with --agents-dir")
        try:
            result = generate_world_report_collection(
                args.agents_dir.resolve(),
                output_dir,
                args.primary_agent,
            )
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
    else:
        if args.primary_agent is not None:
            parser.error("--primary-agent requires --agents-dir")
        state_path = args.state.resolve() if args.state else None
        if args.visits_dir is not None:
            result = generate_source_aware_archive(
                args.visits_dir.resolve(),
                output_dir,
                state_path,
            )
        else:
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

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
