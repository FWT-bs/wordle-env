# Wordle Env

A standalone Mesocosm/Bench environment for a small Wordle-style task.

The agent gets six tries to guess a hidden five-letter word from a small
candidate list. After every guess, the environment returns Wordle-style
feedback:

- `green`: correct letter, correct position
- `yellow`: correct letter, wrong position
- `gray`: letter is not in the answer

## Required Files

These files should live at the root of the GitHub repo:

- `env.py`: task logic. Defines hidden state, observations, actions, rewards, and termination.
- `adapter.py`: starts the HTTP server that exposes `/health`, `/reset`, `/step`, `/close`, and optional `/render`.
- `benchanything.json`: manifest for the binding vow, action space, reward, episode limit, and scoring.
- `requirements.txt`: optional task dependencies. This example does not need any.

Do not commit `.venv/`, `data/`, or `__pycache__/`.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install swecc-mesocosm
```

## Run The Environment Server

```bash
.venv/bin/python adapter.py --port 8765
```

Open the visual UI at:

```text
http://localhost:8765/
```

In another terminal, you can also check the HTTP contract:

```bash
curl -sS http://localhost:8765/health

curl -sS -X POST http://localhost:8765/reset \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo","seed":42}'

curl -sS -X POST http://localhost:8765/step \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo","action":{"guess":"crane"}}'

curl -sS -X POST http://localhost:8765/render \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo","mode":"json"}'

curl -sS -X POST http://localhost:8765/close \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo"}'
```

## Run A Local Bench

Start the adapter in terminal 1:

```bash
.venv/bin/python adapter.py
```

Run a local Ollama bench in terminal 2:

```bash
.venv/bin/mesocosm run local --model ollama/qwen2.5-coder:14b --episodes 1 --seeds 42
```

Swap the model for any local Ollama model you have pulled, such as
`ollama/llama3.2`.

## Submit Through The UI

Push this folder as its own public GitHub repo. The repo root should contain
`benchanything.json`, `adapter.py`, `env.py`, and `requirements.txt`.

Then open the Mesocosm UI, submit the GitHub repo URL as a developer
environment, wait for it to become ready, and create a run from that environment.

## Showcase UI

The repo also has a static replay UI in `showcase/`.

Local preview:

```bash
python3 -m http.server 8080 -d showcase
```

Open:

```text
http://localhost:8080/
```

After a prod run completes, export it into the UI:

```bash
.venv/bin/mesocosm run export RUN_ID -o showcase/data/replay.json
```

## Publish Multiple Runs To GitHub Pages

The showcase can list any number of runs. Each run lives in its own JSON file
under `showcase/data/runs/`, and `showcase/data/runs.json` is a lightweight
index that the UI reads on load.

After every prod run:

```bash
.venv/bin/mesocosm run export RUN_ID -o showcase/data/runs/RUN_ID.json
python3 tools/index_runs.py
git add showcase/data/runs/RUN_ID.json showcase/data/runs.json
git commit -m "Add run RUN_ID"
git push
```

The `Deploy showcase to GitHub Pages` workflow then publishes `showcase/` to
GitHub Pages on push to `main`. Open:

```text
https://FWT-bs.github.io/wordle-env/
```

The Runs panel on the left lists every run in the index. The URL parameter
`?run=RUN_ID` still works for direct deep links; if the run is not in the local
index, the UI falls back to fetching it from the live API.

To enable Pages, in the repo settings set `Pages → Build and deployment →
Source` to `GitHub Actions`.
