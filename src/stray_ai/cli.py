from __future__ import annotations

import argparse
import json
from pathlib import Path

from .visitor import run_visit


def main() -> None:
    parser = argparse.ArgumentParser(prog="stray-ai")
    parser.add_argument("--agent", type=Path, default=Path("agents/stray-001"))
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--entrance", type=Path, required=True)
    parser.add_argument("--arrival-path", type=Path, nargs="*", default=[])
    parser.add_argument("--outbox", type=Path, default=Path("outbox/traces"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    local_root = args.local_root.resolve()
    arrival_path = [
        (path if path.is_absolute() else local_root / path).resolve()
        for path in args.arrival_path
    ]
    result = run_visit(
        agent_dir=args.agent.resolve(),
        local_root=local_root,
        entrance=args.entrance.resolve(),
        arrival_path=arrival_path,
        outbox=args.outbox.resolve(),
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
