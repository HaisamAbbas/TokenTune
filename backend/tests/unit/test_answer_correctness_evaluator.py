import pytest

from app.evaluation.answer_correctness import AnswerCorrectnessEvaluator, _parse_score


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body


class _FakeHttpClient:
    def __init__(self, body: dict) -> None:
        self._body = body

    async def post(self, url: str, json: dict, headers: dict) -> _FakeResponse:
        return _FakeResponse(self._body)


def test_parse_score_valid_integer() -> None:
    assert _parse_score("85") == pytest.approx(0.85)


def test_parse_score_clamps_out_of_range() -> None:
    assert _parse_score("150") == 1.0
    assert _parse_score("-10") == 0.0


def test_parse_score_extracts_number_from_extra_text() -> None:
    assert _parse_score("Score: 60") == pytest.approx(0.6)


def test_parse_score_malformed_falls_back_to_zero() -> None:
    assert _parse_score("I cannot answer that.") == 0.0


@pytest.mark.asyncio
async def test_evaluate_parses_valid_judge_response() -> None:
    body = {"choices": [{"message": {"content": "90"}}]}
    evaluator = AnswerCorrectnessEvaluator(_client=_FakeHttpClient(body))  # type: ignore[arg-type]

    score = await evaluator.evaluate(
        question="Why is the sky blue?",
        expected_answer="Rayleigh scattering.",
        actual_answer="Because of Rayleigh scattering of sunlight.",
    )
    assert score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_evaluate_falls_back_on_malformed_judge_response() -> None:
    body = {"choices": [{"message": {"content": "I refuse to score this."}}]}
    evaluator = AnswerCorrectnessEvaluator(_client=_FakeHttpClient(body))  # type: ignore[arg-type]

    score = await evaluator.evaluate(
        question="Why is the sky blue?",
        expected_answer="Rayleigh scattering.",
        actual_answer="Bananas.",
    )
    assert score == 0.0


@pytest.mark.asyncio
async def test_evaluate_falls_back_on_malformed_response_body() -> None:
    body = {"unexpected": "shape"}
    evaluator = AnswerCorrectnessEvaluator(_client=_FakeHttpClient(body))  # type: ignore[arg-type]

    score = await evaluator.evaluate(
        question="Why is the sky blue?",
        expected_answer="Rayleigh scattering.",
        actual_answer="Bananas.",
    )
    assert score == 0.0
