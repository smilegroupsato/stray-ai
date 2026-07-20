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
    parser.add_argument("--outbox", type=Path, default=Path("outbox/traces"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    result = run_visit(agent_dir=args.agent.resolve(), local_root=args.local_root.resolve(), entrance=args.entrance.resolve(), outbox=args.outbox.resolve(), seed=args.seed)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
