"""Document rendering — turn structured agent output into payer-ready artifacts.

Bounded responsibility (per AAOSA doctrine): this layer converts already-
typed Pydantic models into PDF bytes. It does NOT reach into agent state,
DB queries, or LLM clients — input → bytes, period.

Modules:
  appeal_pdf  — render the AppealDraft (from Appeals Drafter agent) into a
                payer-ready business letter PDF. ReportLab Platypus.
"""
from app.render.appeal_pdf import render_appeal_pdf

__all__ = ["render_appeal_pdf"]
