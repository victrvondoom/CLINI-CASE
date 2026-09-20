"""Demo fixture endpoints - one-click case creation for the live demo.

The frontend's Home page lists these and lets the user spin up a case
with two clicks. Fixture FHIR bundles live in `tests/fixtures/`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import db

router = APIRouter(prefix="/demo-fixtures", tags=["demo"])

_FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"

DEMO_FIXTURES: list[dict[str, Any]] = [
    {
        "name": "stage3_her2pos_breast_with_lvef",
        "label": "Stage IIIA HER2+ Breast Cancer (complete workup)",
        "description": "Demo path A — HER2+ patient with full baseline workup including LVEF 62% by echo. Expected verdict APPROVE — every Aetna criterion is met cleanly.",
        "patient_initials": "SD",
        "physician_note": (
            "53yo F with newly diagnosed stage IIIA invasive ductal carcinoma of the "
            "right breast, HER2-positive (IHC 3+), ER and PR negative. ECOG 1. "
            "Baseline transthoracic echocardiogram on 2026-04-15: LVEF 62%, no wall motion "
            "abnormalities, no symptomatic heart failure. BP 122/76. No history of "
            "interstitial lung disease. Treatment plan: neoadjuvant TCHP regimen "
            "(docetaxel + carboplatin + trastuzumab + pertuzumab) starting 2026-04-22."
        ),
        "requested_treatment": {"name": "trastuzumab", "j_code": "J9355"},
        "payer_id": "aetna",
        "expected_verdict": "APPROVE",
    },
    {
        "name": "stage3_her2pos_breast",
        "label": "Stage IIIA HER2+ Breast Cancer (incomplete workup)",
        "description": "Demo path B — HER2+ patient but missing LVEF documentation. Expected verdict REFER — ClinCase flags the gap instead of guessing (humility demo).",
        "patient_initials": "JD",
        "physician_note": (
            "53yo F with stage IIIA invasive ductal carcinoma of the right breast, "
            "HER2-positive (IHC 3+), ER and PR negative. ECOG 1. No prior systemic therapy. "
            "Treatment plan: neoadjuvant trastuzumab in combination with chemotherapy."
        ),
        "requested_treatment": {"name": "trastuzumab", "j_code": "J9355"},
        "payer_id": "aetna",
        "expected_verdict": "REFER",
    },
    {
        "name": "stage3_her2neg_breast",
        "label": "Stage IIIB HER2-NEGATIVE Breast Cancer",
        "description": "Demo path C — HER2-negative patient erroneously requesting trastuzumab. Expected verdict DENY → Appeals Drafter activates and drafts a 600-word formal appeal letter.",
        "patient_initials": "MD",
        "physician_note": (
            "58yo F with stage IIIB invasive ductal carcinoma of the left breast, "
            "HER2-negative (IHC 1+, ISH non-amplified), ER positive (95%). ECOG 1."
        ),
        "requested_treatment": {"name": "trastuzumab", "j_code": "J9355"},
        "payer_id": "aetna",
        "expected_verdict": "DENY",
    },
]


@router.get("")
async def list_fixtures() -> dict[str, Any]:
    """List the curated demo fixtures available to the UI."""
    return {
        "fixtures": [
            {k: v for k, v in f.items()}
            for f in DEMO_FIXTURES
        ]
    }


@router.post("/{name}/create-case")
async def create_case_from_fixture(
    name: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Case row from the named fixture under the user's organization."""
    fixture_meta = next((f for f in DEMO_FIXTURES if f["name"] == name), None)
    if fixture_meta is None:
        raise HTTPException(status_code=404, detail=f"Fixture '{name}' not found")

    fixture_path = _FIXTURES_DIR / f"{name}.json"
    if not fixture_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Fixture file missing on disk: {fixture_path}",
        )
    fhir_bundle = json.loads(fixture_path.read_text(encoding="utf-8"))

    case_id = uuid4().hex[:12]
    await db.execute(
        """INSERT INTO cases (id, organization_id, created_by_user_id,
                              payer_id, patient_initials,
                              requested_treatment_name, requested_j_code,
                              fhir_bundle, physician_note, status)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending')""",
        case_id,
        user["organization_id"],
        user["id"],
        fixture_meta["payer_id"],
        fixture_meta["patient_initials"],
        fixture_meta["requested_treatment"]["name"],
        fixture_meta["requested_treatment"].get("j_code"),
        json.dumps(fhir_bundle),
        fixture_meta["physician_note"],
    )

    return {"case_id": case_id, "fixture": fixture_meta}
