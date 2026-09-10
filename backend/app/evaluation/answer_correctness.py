import logging
import re

import httpx

from app.core.config import settings
from app.evaluation.base import Evaluator

logger = logging.getLogger(__name__)

# Fallback score used whenever the judge's response can't be parsed into a
# number, so one bad LLM response degrades a single item's score rather than
# aborting the whole experiment run (see Evaluator docstring).
_FALLBACK_SCORE = 0.0

_JUDGE_PROMPT = """You are grading how correct an AI-generated answer is compared to a known-correct expected answer.

Question: {question}

Expected answer: {expected_answer}

Actual answer: {actual_answer}

Score how correct the actual answer is on a scale from 0 to 100, where:
- 100 means the actual answer is fully correct and captures the same key facts as the expected answer.
- 0 means the actual answer is completely wrong, unrelated, or missing.
- Partial credit for partially correct or incomplete answers.

Respond with ONLY the integer score (0-100), no other text."""

# Matches the first integer in the response, optionally preceded by other
# text (judges sometimes add a stray "Score: " prefix despite instructions).
_SCORE_PATTERN = re.compile(r"-?\d+")


def _parse_score(raw_text: str) -> float:
    """Parse a judge response into a 0-1 score.

    Designed to be robust rather than strict: extracts the first integer in
    the response and normalizes 0-100 -> 0-1, clamping out-of-range values.
    Falls back to `_FALLBACK_SCORE` (with a logged warning) for anything
    that doesn't parse, rather than raising.
    """
    match = _SCORE_PATTERN.search(raw_text)
    if match is None:
        logger.warning("AnswerCorrectnessEvaluator: could not parse judge response: %r", raw_text)
        return _FALLBACK_SCORE

    try:
        score = float(match.group())
    except ValueError:
        logger.warning("AnswerCorrectnessEvaluator: could not parse judge response: %r", raw_text)
        return _FALLBACK_SCORE

    normalized = score / 100
    return max(0.0, min(1.0, normalized))


class AnswerCorrectnessEvaluator(Evaluator):
    """LLM-as-judge evaluator, routed through the same litellm-proxy / GLM
    setup the sample app itself uses (see `litellm-config.yml`)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        _client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url or settings.litellm_base_url
        self.api_key = api_key or settings.litellm_api_key
        self.model = model or settings.judge_model
        self._client = _client

    async def evaluate(self, question: str, expected_answer: str, actual_answer: str) -> float:
        prompt = _JUDGE_PROMPT.format(
            question=question, expected_answer=expected_answer, actual_answer=actual_answer
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self.base_url}/v1/chat/completions", json=payload, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/chat/completions", json=payload, headers=headers
                    )
            response.raise_for_status()
            body = response.json()
            raw_text = body["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            logger.warning("AnswerCorrectnessEvaluator: judge call failed: %s", exc)
            return _FALLBACK_SCORE

        return _parse_score(raw_text)
