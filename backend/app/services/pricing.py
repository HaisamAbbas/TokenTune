from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

PRICING_FILE = Path(__file__).resolve().parent.parent / "core" / "pricing.yaml"


@lru_cache(maxsize=1)
def _load_pricing_table() -> dict[str, dict[str, float]]:
    with PRICING_FILE.open() as f:
        return yaml.safe_load(f) or {}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    table = _load_pricing_table()
    rates = table.get(model)
    if rates is None:
        return None
    input_rate = Decimal(str(rates["input_per_1k"]))
    output_rate = Decimal(str(rates["output_per_1k"]))
    return (Decimal(input_tokens) / 1000) * input_rate + (Decimal(output_tokens) / 1000) * output_rate
