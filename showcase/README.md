# Wordle Showcase UI

This static page replays a Mesocosm run export for the Wordle environment.

## Local Preview

```bash
cd /Users/fwt/Documents/bench/wordle-env
python3 -m http.server 8080 -d showcase
```

Open:

```text
http://localhost:8080/
```

## Use A Real Run

After a prod run completes:

```bash
.venv/bin/mesocosm run export RUN_ID -o showcase/data/replay.json
```

Then commit and push `showcase/data/replay.json`.

You can also open the page with a public run id:

```text
https://FWT-bs.github.io/wordle-env/showcase/?run=RUN_ID
```
