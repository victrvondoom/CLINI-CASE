"""Kiro IDE spec exporter.

Kiro is AWS's spec-driven agentic IDE (GA late 2025; in GovCloud regions
since Feb 2026). Each agent is described by THREE markdown files:

    .kiro/specs/<agent>/requirements.md   — user stories + EARS acceptance criteria
    .kiro/specs/<agent>/design.md         — architecture, schemas, interfaces
    .kiro/specs/<agent>/tasks.md          — checkable build tasks

Kiro Hooks fire on file events to regenerate / lint / test code from the
specs. This package exports `.kiro/specs/<agent>/*.md` for every parent
and sub-agent in `AGENT_MANIFEST`, automatically.

Why this exists for the demo:
  • Kiro is the AWS-blessed agentic-IDE workflow as of 2026.
  • AWS's only published Kiro reference for healthcare is "drug discovery
    agent in three weeks" (life sciences). NO payer/PA reference yet.
  • ClinCase publishing 28 .kiro specs (7 parents + 21 sub-agents) in one
    repo is the credible "spec-to-prod" story for healthcare PA.
  • A new oncologist-side specialty (cardiology, behavioral health) is
    THREE markdown files — Kiro Hooks scaffold the rest.

The exporter is idempotent: re-running it overwrites the `.kiro/specs/`
tree to mirror the current `AGENT_MANIFEST`. Hand edits to those files
are clobbered — that's by design. Edit the agent's source code (the spec
is generated from it).
"""
from app.integrations.kiro.exporter import (
    export_kiro_specs,
    kiro_spec_for_agent,
)

__all__ = ["export_kiro_specs", "kiro_spec_for_agent"]
