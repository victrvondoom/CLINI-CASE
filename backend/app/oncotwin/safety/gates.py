"""Safety gates — no AI-generated clinical statement reaches a clinician unless it passes.

  1 schema        the candidate is well-formed (pydantic): text, cited evidence
                  ids, as-of day, optional probability in [0, 1]
  2 evidence      every cited resource id exists in the record AS OF the day,
                  and every number in the text is traceable to the evidence
                  payload (tolerant of rounding / % formatting) — a fabricated
                  value or observation fails
  3 freshness     if model-signal data are stale or incomplete, the text must
                  carry a reliability caveat
  4 uncertainty   a quoted risk must come with its interval or confidence; low
                  confidence forbids confident wording
  5 safety        no diagnosis, no treatment orders, no causal claims, no
                  unwarranted certainty
  + model         the model artifact's integrity (SHA-256) must be verified

On any failure the statement is NOT shown; a non-confident fallback that names
the failed gates is shown instead, and the failure is metered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.oncotwin.observability import METRICS
from app.oncotwin.records import PatientRecord

STALE_HOURS = 36.0
STRUCTURAL_NUMBERS = {"0", "1", "2", "3", "7", "24", "72", "80", "95", "1.5"}
CAVEAT = re.compile(r"reliab|incomplete|stale|missing|limited data|data gap", re.I)
INTERVAL = re.compile(r"interval|confidence|±|\d\s*%?\s*[–-]\s*\d", re.I)
CONFIDENT = re.compile(r"\b(clearly|strongly (?:indicates|suggests)|high confidence|definitely|certain(?:ly)?)\b", re.I)
PROHIBITED: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:is|are|was)\s+diagnosed\b|\bdiagnos(?:is|ed)\s+(?:of|with)\b|\bthe patient has (?:sepsis|pneumonia|"
                r"febrile neutropenia|neutropenic fever|an infection|dehydration)\b", re.I), "diagnostic claim"),
    (re.compile(r"\b(?:administer|prescribe|start|begin|give|order)\s+(?:the\s+)?(?:empiric\s+)?(?:antibiotics?|g-csf|"
                r"pegfilgrastim|filgrastim|iv fluids|fluids|chemotherapy|a dose)\b", re.I), "treatment order"),
    (re.compile(r"\b(?:caused|causes|causing)\b|\bdue to\b|\bas a result of\b|\bresulted in\b", re.I), "causal claim"),
    (re.compile(r"\b(?:guarantee[ds]?|will (?:be admitted|develop|deteriorate|die)|certain to)\b", re.I), "unwarranted certainty"),
]
_ID_TOKENS = re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+\b|\b[A-Z]\d{2}(?:\.\d+)?\b|\bv\d+(?:\.\d+)*\b")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")


class StatementCandidate(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=500)
    as_of_day: int = Field(ge=1)
    risk: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str = Field(default="deterministic", pattern="^(deterministic|llm)$")


@dataclass
class EvidenceContext:
    as_of_day: int
    allowed_ids: set[str]
    allowed_numbers: set[str]
    newest_signal_hours: float | None
    completeness: float
    confidence_label: str
    model_integrity: bool
    notes: list[str] = field(default_factory=list)


def _variants(v: float) -> set[str]:
    out: set[str] = set()
    for x in (v, abs(v)):
        out |= {f"{x:.0f}", f"{x:.1f}", f"{x:.2f}", f"{x:.3f}".rstrip("0").rstrip("."), f"{x:g}"}
        if 0 <= x <= 1:
            out |= {f"{100 * x:.0f}", f"{100 * x:.1f}"}
    return out


def _collect_numbers(obj: Any, acc: set[str], depth: int = 0) -> None:
    if depth > 12 or isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        acc |= _variants(float(obj))
    elif isinstance(obj, str):
        acc |= {m.replace(",", "") for m in _NUMBER.findall(_ID_TOKENS.sub(" ", obj))}
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, acc, depth + 1)
    elif isinstance(obj, list | tuple):
        for v in obj[:400]:
            _collect_numbers(v, acc, depth + 1)


def build_context(record: PatientRecord, as_of_day: int, evidence_payloads: list[Any], *,
                  newest_signal_hours: float | None, completeness: float, confidence_label: str,
                  model_integrity: bool) -> EvidenceContext:
    ids = {o.id for o in record.observations if o.day <= as_of_day} | {e.id for e in record.events if e.day <= as_of_day}
    nums: set[str] = set(STRUCTURAL_NUMBERS) | {str(d) for d in range(1, as_of_day + 1)}
    for p in evidence_payloads:
        _collect_numbers(p, nums)
    return EvidenceContext(as_of_day, ids, nums, newest_signal_hours, completeness, confidence_label, model_integrity)


def check(candidate: dict[str, Any], ctx: EvidenceContext) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []

    def gate(name: str, ok: bool, detail: str) -> None:
        gates.append({"gate": name, "passed": bool(ok), "detail": detail})

    try:
        c = StatementCandidate(**candidate)
        gate("schema", True, "well-formed statement")
    except ValidationError as e:
        gate("schema", False, f"invalid statement: {e.errors()[0]['msg']}")
        return _result(str(candidate.get("text", "")), gates, str(candidate.get("source", "unknown")))

    unknown_ids = [i for i in c.evidence_ids if i not in ctx.allowed_ids]
    found = [m.replace(",", "") for m in _NUMBER.findall(_ID_TOKENS.sub(" ", c.text))]
    unsupported = sorted({n for n in found if n not in ctx.allowed_numbers
                          and n.rstrip("0").rstrip(".") not in ctx.allowed_numbers})
    ok_ev = not unknown_ids and not unsupported
    gate("evidence", ok_ev, "all cited resources exist as of the day and every number is traceable to the evidence"
         if ok_ev else "; ".join(x for x in (
             f"unknown or future evidence ids: {unknown_ids[:5]}" if unknown_ids else "",
             f"numbers not found in the evidence: {unsupported[:8]}" if unsupported else "") if x))

    stale = ctx.newest_signal_hours is None or ctx.newest_signal_hours > STALE_HOURS or ctx.completeness < 0.5
    caveat = bool(CAVEAT.search(c.text))
    gate("freshness", (not stale) or caveat, "inputs fresh" if not stale else (
        "stale/incomplete inputs — reliability caveat present" if caveat
        else "stale or incomplete inputs but no reliability caveat in the statement"))

    quotes_risk = c.risk is not None or re.search(r"\d\s*%", c.text) is not None
    unc_ok = (not quotes_risk or bool(INTERVAL.search(c.text))) and not (
        ctx.confidence_label == "low" and CONFIDENT.search(c.text))
    gate("uncertainty", unc_ok, "uncertainty stated" if unc_ok else
         "a risk is quoted without its interval/confidence, or confident wording is used under low confidence")

    hits = [label for pat, label in PROHIBITED if pat.search(c.text)]
    gate("safety", not hits, "no diagnosis, orders, causal claims or certainty" if not hits
         else f"prohibited: {', '.join(hits)}")
    gate("model_integrity", ctx.model_integrity, "model artifact SHA-256 verified" if ctx.model_integrity
         else "model artifact integrity NOT verified")
    return _result(c.text, gates, c.source)


def _result(text: str, gates: list[dict[str, Any]], source: str) -> dict[str, Any]:
    failed = [g for g in gates if not g["passed"]]
    for g in gates:
        METRICS.inc("oncotwin_safety_gate_total", gate=g["gate"], outcome="pass" if g["passed"] else "fail", source=source)
    return {
        "passed": not failed, "gates": gates, "source": source, "action": "display" if not failed else "fallback",
        "display_text": text if not failed else (
            "No confident statement can be shown — failed safety gate(s): "
            + "; ".join(f"{g['gate']} ({g['detail']})" for g in failed)
            + ". Review the underlying data and evidence directly."),
    }
