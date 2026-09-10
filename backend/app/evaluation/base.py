from abc import ABC, abstractmethod


class Evaluator(ABC):
    """Scores one actual answer against an expected answer for a question.

    Score is always in [0, 1]: 0 = completely wrong/unrelated, 1 = fully
    correct. Implementations must not raise on a malformed judge response -
    see `AnswerCorrectnessEvaluator` for the fallback-and-log pattern - so a
    caller running many items (e.g. an Experiment) never has one bad
    response abort the whole run.
    """

    @abstractmethod
    async def evaluate(self, question: str, expected_answer: str, actual_answer: str) -> float:
        """Return a 0-1 correctness score for `actual_answer`."""
        raise NotImplementedError
