from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any


def _allow_running_from_swecc_core_checkout() -> None:
    """Let this example run before swecc-mesocosm is installed locally."""
    repo_common = Path(__file__).resolve().parents[1] / "services" / "bench" / "common"
    if repo_common.exists():
        sys.path.insert(0, str(repo_common))


try:
    from bench_common.env_sdk import BaseEnv, StepResult
except ModuleNotFoundError:
    _allow_running_from_swecc_core_checkout()
    from bench_common.env_sdk import BaseEnv, StepResult


ANSWERS = [
    "apple",
    "brave",
    "crane",
    "delta",
    "flame",
    "grape",
    "light",
    "mango",
    "plant",
    "river",
    "sharp",
    "stone",
    "table",
    "tiger",
    "train",
    "vivid",
    "water",
    "whale",
    "zebra",
]


class WordleEnv(BaseEnv):
    """A small Wordle-like benchmark: guess a hidden five-letter word."""

    def __init__(self) -> None:
        self._rng = random.Random()
        self._secret: str | None = None
        self._max_guesses = 6
        self._guesses_used = 0
        self._history: list[dict[str, Any]] = []

    def reset(self, seed: int | None = None, **params: Any) -> dict[str, Any]:
        self._rng.seed(seed)

        forced_answer = params.get("answer")
        if isinstance(forced_answer, str) and forced_answer.lower() in ANSWERS:
            self._secret = forced_answer.lower()
        else:
            self._secret = self._rng.choice(ANSWERS)

        self._guesses_used = 0
        self._history = []
        return self._observation()

    def parse_action(self, action: Any) -> str:
        """Accept either {"guess": "crane"} or just "crane"."""
        if isinstance(action, dict):
            action = action.get("guess", "")
        return str(action).strip().lower()

    def step(self, action: Any) -> StepResult:
        if self._secret is None:
            raise RuntimeError("Call reset() before step()")

        guess = self.parse_action(action)
        self._guesses_used += 1

        if not self._is_valid_guess(guess):
            self._history.append(
                {
                    "guess": guess,
                    "valid": False,
                    "feedback": [],
                    "message": "Guess must be exactly five alphabetic characters.",
                }
            )
            out_of_guesses = self._guesses_used >= self._max_guesses
            return StepResult(
                observation=self._observation(reveal_answer=out_of_guesses),
                reward=0.0,
                terminated=out_of_guesses,
                truncated=False,
                info=self._info(won=False),
            )

        feedback = self._score_guess(guess, self._secret)
        won = guess == self._secret
        out_of_guesses = self._guesses_used >= self._max_guesses
        done = won or out_of_guesses

        self._history.append(
            {
                "guess": guess,
                "valid": True,
                "feedback": [
                    {"letter": letter, "mark": mark} for letter, mark in zip(guess, feedback)
                ],
            }
        )

        return StepResult(
            observation=self._observation(reveal_answer=done),
            reward=1.0 if won else 0.0,
            terminated=done,
            truncated=False,
            info=self._info(won=won),
        )

    def render(self, mode: str = "text") -> str:
        rows = []
        for row in self._history:
            if not row["valid"]:
                rows.append(f"{row['guess']}: invalid")
                continue
            marker = {"green": "G", "yellow": "Y", "gray": "-"}
            marks = " ".join(marker[item["mark"]] for item in row["feedback"])
            rows.append(f"{row['guess']}: {marks}")
        return "\n".join(rows) or "No guesses yet."

    def _observation(self, *, reveal_answer: bool = False) -> dict[str, Any]:
        obs: dict[str, Any] = {
            "instructions": (
                "Guess the hidden five-letter word. Submit an action like "
                "{\"guess\": \"crane\"}."
            ),
            "guesses_remaining": max(0, self._max_guesses - self._guesses_used),
            "history": self._history,
        }
        if reveal_answer and self._secret is not None:
            obs["answer"] = self._secret
        return obs

    def _info(self, *, won: bool) -> dict[str, str]:
        return {
            "won": "1.0" if won else "0.0",
            "guesses_used": str(self._guesses_used),
            "answer": self._secret or "",
        }

    @staticmethod
    def _is_valid_guess(guess: str) -> bool:
        return len(guess) == 5 and guess.isalpha()

    @staticmethod
    def _score_guess(guess: str, secret: str) -> list[str]:
        marks = ["gray"] * 5
        remaining = list(secret)

        for i, letter in enumerate(guess):
            if letter == secret[i]:
                marks[i] = "green"
                remaining[i] = ""

        for i, letter in enumerate(guess):
            if marks[i] == "green":
                continue
            if letter in remaining:
                marks[i] = "yellow"
                remaining[remaining.index(letter)] = ""

        return marks
