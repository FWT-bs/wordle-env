#!/usr/bin/env python3
"""Pull every bench run you can see and drop it into the showcase.

Discovers run ids from your teams and the Wordle domain, exports each one to
`showcase/data/runs/<run_id>.json` (the same payload `mesocosm run export`
writes), then rebuilds `showcase/data/runs.json` via tools/index_runs.py.

Auth comes from the same place the CLI uses:
  * env `SWECC_BENCH_TOKEN`, else
  * the credentials file (`SWECC_BENCH_CREDENTIALS` or
    `~/.config/swecc/bench_credentials.json`), written by `mesocosm auth login`.

Usage:
  python3 tools/pull_runs.py                 # discover + export everything
  python3 tools/pull_runs.py RUN_ID ...      # also include explicit run ids

Stdlib only, so it runs with any python3 (no venv activation needed).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "showcase" / "data" / "runs"
INDEXER = ROOT / "tools" / "index_runs.py"

# Wordle domain id (matches showcase/index.html DEFAULT_DOMAIN_ID). This is the
# prod domain created by `mesocosm env submit` for the FWT-bs/wordle-env repo.
WORDLE_DOMAIN_ID = "85ec56ce-8e26-40d9-bfbb-879097f8d958"

DEFAULT_BENCH_URL = "https://api.swecc.org/bench"


def credentials_path() -> Path:
    override = os.environ.get("SWECC_BENCH_CREDENTIALS")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "swecc" / "bench_credentials.json"


def load_auth() -> tuple[str, str]:
    """Return (bench_url, token). Exits with a login hint if no usable token."""
    token = os.environ.get("SWECC_BENCH_TOKEN")
    bench_url = (
        os.environ.get("MESOCOSM_BASE_URL")
        or os.environ.get("SWECC_BENCH_URL")
        or os.environ.get("BENCH_API_URL")
    )
    creds: dict = {}
    path = credentials_path()
    if path.exists():
        try:
            creds = json.loads(path.read_text())
        except json.JSONDecodeError:
            creds = {}
    token = token or creds.get("token")
    bench_url = bench_url or creds.get("bench_url") or DEFAULT_BENCH_URL
    if not token:
        sys.exit(
            "No bench token found.\n"
            "  Log in first:  .venv/bin/mesocosm auth login\n"
            f"  (looked in {path} and $SWECC_BENCH_TOKEN)"
        )
    return bench_url.rstrip("/"), token


class ApiError(Exception):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"{status} for {url}: {body[:200]}")
        self.status = status


def api_get(bench_url: str, token: str, path: str):
    url = f"{bench_url}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        raise ApiError(err.code, url, body) from None


def as_runs(payload) -> list[dict]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        runs = payload.get("runs")
        if isinstance(runs, list):
            return [r for r in runs if isinstance(r, dict)]
    return []


def discover_run_ids(bench_url: str, token: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(run_id):
        if run_id and run_id not in seen:
            seen.add(run_id)
            ids.append(run_id)

    # 1. Every run your account can see (no filter) — the primary source.
    try:
        for run in as_runs(api_get(bench_url, token, "/v1/runs")):
            add(run.get("id"))
    except ApiError as err:
        print(f"  /v1/runs query failed ({err.status})", file=sys.stderr)

    # 2. Runs visible on the Wordle domain specifically (belt and suspenders).
    try:
        for run in as_runs(api_get(bench_url, token, f"/v1/runs?domain_id={WORDLE_DOMAIN_ID}")):
            add(run.get("id"))
    except ApiError as err:
        print(f"  domain runs query failed ({err.status})", file=sys.stderr)

    # 2. Runs scoped to each team you belong to.
    try:
        teams = api_get(bench_url, token, "/v1/teams")
        team_list = teams if isinstance(teams, list) else teams.get("teams", [])
        for team in team_list:
            team_id = team.get("id") or team.get("team_id")
            if not team_id:
                continue
            try:
                for run in as_runs(api_get(bench_url, token, f"/v1/teams/{team_id}/runs")):
                    add(run.get("id"))
            except ApiError as err:
                print(f"  team {team_id} runs failed ({err.status})", file=sys.stderr)
    except ApiError as err:
        print(f"  team list failed ({err.status})", file=sys.stderr)

    # 3. Run ids already on disk (so re-runs refresh them even if discovery misses).
    if RUNS_DIR.exists():
        for path in RUNS_DIR.glob("*.json"):
            add(path.stem)

    return ids


def export_run(bench_url: str, token: str, run_id: str) -> dict | None:
    try:
        return api_get(bench_url, token, f"/v1/runs/{run_id}/export")
    except ApiError as err:
        print(f"  ! export {run_id[:8]} failed ({err.status})", file=sys.stderr)
        return None


def trace_summary(payload: dict) -> tuple[int, int]:
    """(episodes_with_traces, total_trace_steps) for the report."""
    traces = payload.get("traces") or {}
    with_traces = sum(1 for v in traces.values() if v)
    steps = sum(len(v) for v in traces.values() if isinstance(v, list))
    return with_traces, steps


def main() -> int:
    bench_url, token = load_auth()

    me = {}
    try:
        me = api_get(bench_url, token, "/v1/me")
    except ApiError as err:
        if err.status in (401, 403):
            sys.exit(
                "Token rejected (expired or invalid). Re-run:\n"
                "  .venv/bin/mesocosm auth login"
            )
        raise
    if me.get("type") == "anonymous" or not (me.get("user_id") or me.get("guest_session_id")):
        sys.exit(
            "Not authenticated (whoami is anonymous). Re-run:\n"
            "  .venv/bin/mesocosm auth login"
        )
    print(f"Authenticated as {me.get('username') or me.get('type')} (id {me.get('user_id')}).")

    explicit = [a for a in sys.argv[1:] if a.strip()]
    run_ids = list(dict.fromkeys(explicit + discover_run_ids(bench_url, token)))
    if not run_ids:
        print("No runs found. Create one with `mesocosm run create` first.")
        return 0

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Exporting {len(run_ids)} run(s) into {RUNS_DIR.relative_to(ROOT)} ...")

    exported = 0
    for run_id in run_ids:
        payload = export_run(bench_url, token, run_id)
        if payload is None:
            continue
        (RUNS_DIR / f"{run_id}.json").write_text(json.dumps(payload, indent=2) + "\n")
        run = payload.get("run") or {}
        eps = payload.get("episodes") or []
        with_traces, steps = trace_summary(payload)
        model = ((run.get("config") or {}).get("agent_config") or {}).get("model") or "?"
        traces_note = f"{with_traces}/{len(eps)} eps with traces ({steps} steps)" if eps else "no episodes"
        print(f"  ok {run_id[:8]}  {run.get('status','?'):9}  {model:34}  {traces_note}")
        exported += 1

    print(f"Exported {exported}/{len(run_ids)} run(s).")

    # Rebuild the lightweight index the UI reads on load.
    result = subprocess.run([sys.executable, str(INDEXER)])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
