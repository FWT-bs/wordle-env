from __future__ import annotations

import argparse
import base64
import math
from typing import Any

import uvicorn
from env import WordleEnv
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


class ResetRequest(BaseModel):
    episode_id: str
    seed: int | None = None
    scenario_params: dict[str, Any] = Field(default_factory=dict)


class StepRequest(BaseModel):
    episode_id: str
    action: Any


class CloseRequest(BaseModel):
    episode_id: str


class RenderRequest(BaseModel):
    episode_id: str
    mode: str = "json"


EPISODES: dict[str, WordleEnv] = {}


def _jsonable(data: Any) -> Any:
    if isinstance(data, bytes):
        return base64.b64encode(data).decode("ascii")
    return jsonable_encoder(data)


def _reward(value: Any) -> float:
    reward = float(value)
    if not math.isfinite(reward):
        raise ValueError(f"reward must be finite, got {value!r}")
    return reward


def create_app() -> FastAPI:
    app = FastAPI(title="Wordle Env", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def ui() -> str:
        return UI_HTML

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "env": "WordleEnv", "episodes": len(EPISODES)}

    @app.post("/reset")
    def reset(req: ResetRequest) -> dict[str, Any]:
        old = EPISODES.pop(req.episode_id, None)
        if old is not None:
            old.close()

        env = WordleEnv()
        EPISODES[req.episode_id] = env

        try:
            observation = env.reset(seed=req.seed, **req.scenario_params)
        except Exception as exc:
            EPISODES.pop(req.episode_id, None)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "data": _jsonable(observation),
            "content_type": "application/json",
            "system_prompt": None,
        }

    @app.post("/step")
    def step(req: StepRequest) -> dict[str, Any]:
        env = EPISODES.get(req.episode_id)
        if env is None:
            raise HTTPException(
                status_code=404,
                detail=f"No active episode '{req.episode_id}'. Call /reset first.",
            )

        try:
            action = env.parse_action(req.action)
            result = env.step(action)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return {
            "observation": {
                "data": _jsonable(result.observation),
                "content_type": getattr(result, "content_type", "application/json"),
            },
            "reward": _reward(result.reward),
            "terminated": bool(result.terminated),
            "truncated": bool(result.truncated),
            "info": _jsonable(result.info),
            "system_prompt": result.system_prompt,
        }

    @app.post("/close")
    def close(req: CloseRequest) -> dict[str, Any]:
        env = EPISODES.pop(req.episode_id, None)
        if env is not None:
            env.close()
        return {}

    @app.post("/render")
    def render(req: RenderRequest) -> dict[str, Any]:
        env = EPISODES.get(req.episode_id)
        if env is None:
            raise HTTPException(status_code=404, detail="Episode not found")
        data = env.render(mode=req.mode)
        content_type = "text/plain" if isinstance(data, str) else "application/json"
        return {"data": _jsonable(data), "content_type": content_type}

    return app


UI_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wordle Env</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1f18;
      --panel: #132a21;
      --line: #25483a;
      --text: #f1f6ed;
      --muted: #9eb8a8;
      --green: #5aa469;
      --yellow: #c9a64d;
      --gray: #48564e;
      --empty: #1b3429;
      --danger: #d67668;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0;
      display: grid;
      grid-template-columns: minmax(320px, 440px) 1fr;
      gap: 24px;
      align-items: start;
    }

    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }

    .subtle { color: var(--muted); }

    .panel {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 18px;
    }

    .board {
      display: grid;
      gap: 8px;
      margin-top: 18px;
    }

    .row {
      display: grid;
      grid-template-columns: repeat(5, 58px);
      gap: 8px;
    }

    .tile {
      width: 58px;
      height: 58px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--empty);
      color: var(--text);
      font-size: 28px;
      font-weight: 800;
      text-transform: uppercase;
    }

    .tile.green { background: var(--green); border-color: var(--green); }
    .tile.yellow { background: var(--yellow); border-color: var(--yellow); color: #1f1b10; }
    .tile.gray { background: var(--gray); border-color: var(--gray); }

    .controls {
      display: grid;
      gap: 10px;
      margin-top: 18px;
    }

    .control-row {
      display: flex;
      gap: 10px;
    }

    input {
      min-width: 0;
      width: 100%;
      height: 44px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #091711;
      color: var(--text);
      padding: 0 12px;
      font-size: 16px;
    }

    button {
      height: 44px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #d7ead9;
      color: #0d1f18;
      padding: 0 14px;
      font-weight: 700;
      cursor: pointer;
    }

    button.secondary {
      background: transparent;
      color: var(--text);
    }

    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }

    .status {
      min-height: 24px;
      margin-top: 12px;
      color: var(--muted);
    }

    .status.error { color: var(--danger); }
    .status.win { color: #a6e7ad; }

    .words {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }

    .word {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }

    pre {
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 520px;
      overflow: auto;
      margin: 0;
      color: #c7dbc9;
      font-size: 13px;
      line-height: 1.5;
    }

    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      .row { grid-template-columns: repeat(5, minmax(42px, 1fr)); }
      .tile {
        width: 100%;
        height: auto;
        aspect-ratio: 1;
        font-size: 23px;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="panel">
      <h1>Wordle Env</h1>
      <div class="subtle" id="episode"></div>
      <div class="board" id="board"></div>

      <form class="controls" id="guess-form">
        <div class="control-row">
          <input id="guess" maxlength="5" autocomplete="off" spellcheck="false" placeholder="crane" />
          <button id="submit" type="submit">Guess</button>
        </div>
        <div class="control-row">
          <input id="seed" inputmode="numeric" placeholder="seed" />
          <button class="secondary" id="reset" type="button">Reset</button>
        </div>
      </form>

      <div class="status" id="status"></div>
    </section>

    <section class="panel">
      <h1>State</h1>
      <div class="subtle">Candidate words</div>
      <div class="words" id="words"></div>
      <div style="height: 18px"></div>
      <div class="subtle">POST /render</div>
      <pre id="json"></pre>
    </section>
  </main>

  <script>
    const episodeId = "ui-" + Math.random().toString(16).slice(2);
    let terminal = false;

    const els = {
      board: document.querySelector("#board"),
      words: document.querySelector("#words"),
      json: document.querySelector("#json"),
      status: document.querySelector("#status"),
      episode: document.querySelector("#episode"),
      guess: document.querySelector("#guess"),
      seed: document.querySelector("#seed"),
      submit: document.querySelector("#submit"),
      form: document.querySelector("#guess-form"),
      reset: document.querySelector("#reset"),
    };

    els.episode.textContent = "episode_id: " + episodeId;

    async function post(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
      }
      return response.json();
    }

    async function reset() {
      terminal = false;
      els.status.className = "status";
      els.status.textContent = "New episode.";
      els.submit.disabled = false;
      const seedText = els.seed.value.trim();
      const body = { episode_id: episodeId };
      if (seedText) body.seed = Number(seedText);
      const response = await post("/reset", body);
      renderObservation(response.data);
      await renderEndpoint();
      els.guess.focus();
    }

    async function step(guess) {
      const response = await post("/step", {
        episode_id: episodeId,
        action: { guess },
      });
      renderObservation(response.observation.data);
      terminal = response.terminated || response.truncated;
      if (terminal) {
        els.submit.disabled = true;
        const won = response.info && response.info.won === "1.0";
        els.status.className = won ? "status win" : "status error";
        els.status.textContent = won
          ? "Solved in " + response.info.guesses_used + "."
          : "Done. Answer: " + (response.info.answer || response.observation.data.answer || "?");
      } else {
        els.status.className = "status";
        els.status.textContent = "Reward: " + response.reward + ". Keep going.";
      }
      await renderEndpoint();
    }

    async function renderEndpoint() {
      const response = await post("/render", { episode_id: episodeId, mode: "json" });
      els.json.textContent = JSON.stringify(response.data, null, 2);
      renderBoard(response.data.board || []);
    }

    function renderObservation(obs) {
      const words = obs.candidate_words || [];
      els.words.innerHTML = words.map((word) => `<span class="word">${word}</span>`).join("");
      if (obs.history) renderBoard(historyToBoard(obs.history, obs.max_guesses || 6));
    }

    function historyToBoard(history, maxGuesses) {
      const rows = history.map((row) => {
        if (!row.valid) return { valid: false, guess: row.guess, tiles: [] };
        return { valid: true, guess: row.guess, tiles: row.feedback };
      });
      while (rows.length < maxGuesses) {
        rows.push({
          valid: true,
          guess: "",
          tiles: Array.from({ length: 5 }, () => ({ letter: "", mark: "empty" })),
        });
      }
      return rows;
    }

    function renderBoard(rows) {
      els.board.innerHTML = rows.map((row) => {
        if (!row.valid) {
          return `<div class="row">${Array.from({ length: 5 }, (_, i) => {
            const letter = (row.guess || "")[i] || "";
            return `<div class="tile gray">${letter}</div>`;
          }).join("")}</div>`;
        }
        const tiles = row.tiles || [];
        return `<div class="row">${tiles.map((tile) => {
          const cls = tile.mark || "empty";
          return `<div class="tile ${cls}">${tile.letter || ""}</div>`;
        }).join("")}</div>`;
      }).join("");
    }

    els.form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (terminal) return;
      const guess = els.guess.value.trim().toLowerCase();
      if (!guess) return;
      try {
        await step(guess);
        els.guess.value = "";
      } catch (error) {
        els.status.className = "status error";
        els.status.textContent = error.message;
      }
    });

    els.reset.addEventListener("click", () => {
      reset().catch((error) => {
        els.status.className = "status error";
        els.status.textContent = error.message;
      });
    });

    reset().catch((error) => {
      els.status.className = "status error";
      els.status.textContent = error.message;
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Wordle benchmark env server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"WordleEnv adapter listening at http://{args.host}:{args.port}")
    print(f"UI: http://localhost:{args.port}/")
    print(f"Health check: http://localhost:{args.port}/health")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
