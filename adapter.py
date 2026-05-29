from __future__ import annotations

import argparse

from bench_common.env_sdk import serve
from env import WordleEnv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Wordle benchmark env server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"WordleEnv adapter listening at http://{args.host}:{args.port}")
    print(f"Health check: http://localhost:{args.port}/health")
    serve(WordleEnv, host=args.host, port=args.port)
