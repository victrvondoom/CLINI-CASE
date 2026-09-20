"""IntakeStage base class + IntakeContext (the data flowing through stages).

Stages are declarative: each one names its inputs and outputs. The
orchestrator validates the chain at startup time so a misconfigured
pipeline fails loudly instead of mysteriously.

IntakeContext is a single mutable object that flows through. We picked
mutability over immutability because:
  - Stages frequently add fields without changing existing ones
  - Per-stage timing is appended; an immutable rebuild on every stage
    would be an unnecessary copy
  - Audit fields accumulate naturally
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class IntakeContext:
    """Mutable state that flows through the pipeline.

    `payload` is a free-form dict where each stage writes its outputs
    keyed by stage name. The orchestrator's `assemble` stage at the end
    consumes these to build the final IntakeResult.
    """

    # Inputs
    image_bytes: bytes
    image_format: str
    filename: str
    mime_type: str
    sha256: str
    source: str

    # Stage outputs accumulate here
    payload: dict[str, Any] = field(default_factory=dict)

    # Per-stage timing for audit + observability
    timings_ms: dict[str, int] = field(default_factory=dict)

    # Soft flags any stage can append (folded into IntakeResult.risk_flags)
    risk_flags: list[str] = field(default_factory=list)

    # Hard short-circuit — any stage can set this to skip the rest of the
    # pipeline and route directly to the assemble stage with whatever has
    # accumulated so far. Used by `deduplicate` (cache hit) and `validate`
    # (low-confidence early exit).
    short_circuit: bool = False
    short_circuit_reason: str | None = None

    # Engines chosen by the classify stage; the extract stage iterates
    fallback_chain: list = field(default_factory=list)


class IntakeStage(ABC):
    """Abstract intake stage. Every stage names its IO + implements run()."""

    name: ClassVar[str] = "abstract"

    # Stages declare what they need + produce. The orchestrator validates
    # at boot that every required key is provided by some upstream stage.
    inputs_required: ClassVar[list[str]] = []
    outputs_produced: ClassVar[list[str]] = []

    @abstractmethod
    async def run(self, ctx: IntakeContext) -> None:
        """Mutate ctx with this stage's output. May read ctx.payload[k]
        for k in inputs_required. Must write ctx.payload[k] for k in
        outputs_produced. Should NOT raise — set risk_flag + short_circuit
        instead so the audit chain is preserved."""
        raise NotImplementedError
