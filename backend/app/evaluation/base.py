from abc import ABC, abstractmethod


class Evaluator(ABC):
    """Scores one actual answer against an expected answer for a question,
    across one or more named metrics (e.g. `{"correctness": 0.9}` for the
    fallback evaluator, or `{"faithfulness": 0.94, "answer_relevancy": 0.92}`
    for a DeepEval-backed evaluator with multiple metrics selected).

    Every score is in [0, 1]: 0 = completely wrong/unrelated, 1 = fully
    correct. Implementations must not raise on a malformed judge response -
    see `AnswerCorrectnessEvaluator` for the fallback-and-log pattern - so a
    caller running many items (e.g. an Experiment) never has one bad
    response abort the whole run.
    """

    @abstractmethod
    async def evaluate(
        self, question: str, expected_answer: str, actual_answer: str
    ) -> dict[str, float]:
        """Return named 0-1 scores for `actual_answer`, one entry per metric
        this evaluator computes."""
        raise NotImplementedError
