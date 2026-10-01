"""Single source of truth for model price estimates (USD per 1M tokens, on-demand list prices).

Used by the gateway audit log, the framework's ModelSpec defaults, agent metrics and the twin's cost
reconciliation. Update prices here only. Family-level (haiku vs sonnet-class); a per-model override belongs
in the model registry once account pricing is verified.
"""

from __future__ import annotations

STANDARD = (3.0, 15.0)  # sonnet-class
LITE = (1.0, 5.0)  # haiku-class


def price_per_mtok(model_id: str | None) -> tuple[float, float]:
    return LITE if model_id and "haiku" in model_id.lower() else STANDARD


def cost_usd(model_id: str | None, input_tokens: int, output_tokens: int) -> float:
    pin, pout = price_per_mtok(model_id)
    return input_tokens * pin / 1_000_000.0 + output_tokens * pout / 1_000_000.0
