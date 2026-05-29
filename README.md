# Wordle Env

This is a standalone Mesocosm/Bench environment you can run locally.

## Files

- `env.py`: the task logic. It defines hidden state, observations, actions, rewards, and termination.
- `adapter.py`: the small HTTP server wrapper. It exposes `/health`, `/reset`, `/step`, `/close`, and optional `/render`.
- `benchanything.json`: the manifest. It tells Mesocosm the observation space, action space, reward, episode limit, and scoring.
- `requirements.txt`: optional extra dependencies. This example does not need any.

## Run The Env Server

I already created `wordle-env/.venv` in this checkout and installed the HTTP server dependencies there. From the repo root, this worked:

```bash
wordle-env/.venv/bin/python wordle-env/adapter.py --port 8765
```

To recreate that setup later:

```bash
python3 -m venv wordle-env/.venv
wordle-env/.venv/bin/python -m pip install swecc-mesocosm
```

If your active Python already has the dependencies installed, this also works from the repo root:

```bash
python3 wordle-env/adapter.py --port 8765
```

From inside this folder:

```bash
python3 adapter.py --port 8765
```

If you move this folder outside the `swecc-core` repo, first install the CLI/package:

```bash
pip install swecc-mesocosm
```

## Test The HTTP Contract

```bash
curl -sS http://localhost:8765/health

curl -sS -X POST http://localhost:8765/reset \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo","seed":42}'

curl -sS -X POST http://localhost:8765/step \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo","action":{"guess":"crane"}}'

curl -sS -X POST http://localhost:8765/close \
  -H 'Content-Type: application/json' \
  -d '{"episode_id":"demo"}'
```

## Run A Local Bench

Using the venv in this folder, open two terminals.

Terminal 1:

```bash
.venv/bin/python adapter.py
```

Terminal 2:

```bash
.venv/bin/mesocosm run local --model ollama/qwen2.5-coder:14b --episodes 1 --seeds 42
```

`mesocosm run local` uses Ollama and does not submit anything to the hosted platform.
You can swap the model for any local Ollama model you have pulled, such as
`ollama/llama3.2`.
