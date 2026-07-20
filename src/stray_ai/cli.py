from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .brain import CommandBrain
from .visitor import run_visit


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai")
    parser.add_argument("--agent", type=Path, default=Path("agents/stray-001"))
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--entrance", type=Path, required=True)
    parser.add_argument("--arrival-path", type=Path, nargs="*", default=[])
    parser.add_argument("--outbox", type=Path, default=Path("outbox/traces"))
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--brain",
        choices=("mock", "command"),
        default=os.environ.get("STRAY_BRAIN_BACKEND", "mock"),
    )
    parser.add_argument(
        "--brain-command",
        default=os.environ.get("STRAY_BRAIN_COMMAND"),
    )
    parser.add_argument(
        "--brain-label",
        default=os.environ.get("STRAY_BRAIN_LABEL", "unnamed-model"),
    )
    parser.add_argument(
        "--brain-timeout",
        type=float,
        default=float(os.environ.get("STRAY_BRAIN_TIMEOUT", "45")),
    )
    args = parser.parse_args()

    local_root = args.local_root.resolve()
    arrival_path = [
        (path if path.is_absolute() else local_root / path).resolve()
        for path in args.arrival_path
    ]
    brain = None
    if args.brain == "command":
        if not args.brain_command:
            parser.error("--brain command requires --brain-command or STRAY_BRAIN_COMMAND")
        brain = CommandBrain.from_string(
            args.brain_command,
            label=args.brain_label,
            timeout_seconds=args.brain_timeout,
        )

    result = run_visit(
        agent_dir=args.agent.resolve(),
        local_root=local_root,
        entrance=args.entrance.resolve(),
        arrival_path=arrival_path,
        outbox=args.outbox.resolve(),
        seed=args.seed,
        brain=brain,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
