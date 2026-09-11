from app.evaluation.base import Evaluator

# Maps the short metric names an Experiment can request (see
# schemas.experiment.EvaluatorSelection) to the DeepEval metric class that
# implements them. Deliberately a small starter set, not all 50+ DeepEval
# metrics - add entries here as developers ask for specific ones; the
# platform doesn't need to pre-wire every metric DeepEval ships.
_METRIC_NAME_MAP = {
    "correctness": "GEval",
    "faithfulness": "FaithfulnessMetric",
    "answer_relevancy": "AnswerRelevancyMetric",
    "contextual_precision": "ContextualPrecisionMetric",
    "contextual_recall": "ContextualRecallMetric",
}


class DeepEvalEvaluator(Evaluator):
    """Evaluator backed by the `deepeval` package (an optional extra - see
    sdk/pyproject.toml's decision to NOT bundle it, and backend's own
    optional-dependency group). Instantiating this without `deepeval`
    installed raises ImportError immediately with an actionable message,
    rather than failing confusingly deep inside `evaluate()`.

    Per the finalized SDK spec: DeepEval owns quality scoring only - this
    class is a thin adapter from the platform's (question, expected_answer,
    actual_answer) shape into DeepEval's `LLMTestCase` + `metric.measure()`,
    never a competing quality judgment of its own.
    """

    def __init__(self, metric_names: list[str]) -> None:
        try:
            import deepeval.metrics as deepeval_metrics
            from deepeval.test_case import LLMTestCase
        except ImportError as exc:
            raise ImportError(
                "DeepEvalEvaluator requires the 'deepeval' package - install it "
                "with `pip install deepeval` (or the backend's `deepeval` extra) "
                "before selecting a DeepEval-backed evaluator for an experiment."
            ) from exc

        self._LLMTestCase = LLMTestCase
        self._metrics = []
        for name in metric_names:
            class_name = _METRIC_NAME_MAP.get(name)
            if class_name is None:
                raise ValueError(
                    f"Unknown DeepEval metric name {name!r} - supported: "
                    f"{sorted(_METRIC_NAME_MAP)}"
                )
            metric_cls = getattr(deepeval_metrics, class_name, None)
            if metric_cls is None:
                raise ImportError(
                    f"deepeval.metrics has no {class_name!r} - is your installed "
                    "deepeval version compatible with this mapping?"
                )
            self._metrics.append((name, metric_cls()))

    async def evaluate(
        self, question: str, expected_answer: str, actual_answer: str
    ) -> dict[str, float]:
        test_case = self._LLMTestCase(
            input=question, actual_output=actual_answer, expected_output=expected_answer
        )
        scores: dict[str, float] = {}
        for name, metric in self._metrics:
            try:
                if hasattr(metric, "a_measure"):
                    await metric.a_measure(test_case)
                else:
                    metric.measure(test_case)
                scores[name] = float(metric.score)
            except Exception:  # noqa: BLE001 - a bad DeepEval metric run must not abort the item
                scores[name] = 0.0
        return scores
