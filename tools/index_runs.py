#!/usr/bin/env python3
"""Build showcase/data/runs.json from showcase/data/runs/*.json.

Each per-run file is a full `mesocosm run export` payload. The index keeps just
enough metadata to render the picker on the showcase UI.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "showcase" / "data" / "runs"
INDEX_PATH = ROOT / "showcase" / "data" / "runs.json"


def summarize(payload: dict, source: Path) -> dict | None:
    run = payload.get("run") or {}
    run_id = run.get("id") or payload.get("run_id")
    if not run_id:
        print(f"skip {source.name}: missing run.id", file=sys.stderr)
        return None

    agent_config = (run.get("config") or {}).get("agent_config") or {}
    scores = run.get("scores") or run.get("aggregate_scores") or {}
    episodes = payload.get("episodes") or []

    return {
        "id": run_id,
        "domain": payload.get("domain_name") or payload.get("domain_id"),
        "model": agent_config.get("model"),
        "status": run.get("status"),
        "scores": scores,
        "episodes": len(episodes),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "exported_at": payload.get("exported_at"),
        "file": f"runs/{source.name}",
    }


def main() -> int:
    if not RUNS_DIR.exists():
        print(f"no runs directory at {RUNS_DIR}", file=sys.stderr)
        return 1

    entries: list[dict] = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError as err:
            print(f"skip {path.name}: invalid json ({err})", file=sys.stderr)
            continue
        summary = summarize(payload, path)
        if summary:
            entries.append(summary)

    entries.sort(key=lambda e: e.get("created_at") or "", reverse=True)

    index = {
        "schema_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runs": entries,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {len(entries)} runs to {INDEX_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
