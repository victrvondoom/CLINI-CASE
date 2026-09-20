"""Seed ~100 synthetic cases under org_demo with realistic distributions.

Generates cases, decisions, and (where applicable) appeals + reviewer_actions
so the /cases, /cohorts, /reviewer, and /compliance pages have statistically
real data. No LLM calls — pure DB inserts.

Run:
    cd backend && .venv/Scripts/python.exe scripts/seed_cohort.py
"""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg

from app.config import settings

random.seed(42)  # deterministic for reproducible demos

# =============================================================================
# Distribution targets (matches Cohorts insight cards)
# =============================================================================

TARGET_TOTAL = 100

VERDICT_MIX = [
    ("APPROVE", "approved",  0.62),
    ("DENY",    "denied",    0.10),
    ("REFER",   "referred",  0.15),
    # Status-only (no verdict) — running / pending / appealed / overturned
]
STATUS_ONLY_MIX = [
    ("running",    0.03),
    ("pending",    0.02),
    ("appealed",   0.06),
    ("overturned", 0.02),
]

PAYER_MIX = [
    ("aetna",  0.42),
    ("uhc",    0.26),
    ("bcbs",   0.18),
    ("anthem", 0.14),
]

TREATMENT_MIX = [
    ("trastuzumab",                "J9355"),
    ("trastuzumab",                "J9355"),  # weighted higher
    ("trastuzumab",                "J9355"),
    ("osimertinib",                "J9335"),
    ("osimertinib",                "J9335"),
    ("pembrolizumab",              "J9271"),
    ("pembrolizumab",              "J9271"),
    ("olaparib",                   "J9305"),
    ("dabrafenib + trametinib",    "J9999"),
    ("T-DXd",                      "J9358"),
    ("ribociclib",                 "J9999"),
    ("enzalutamide",               "J9180"),
    ("lorlatinib",                 "J9999"),
    ("brentuximab vedotin",        "J9042"),
    ("nivolumab",                  "J9299"),
    ("bevacizumab",                "J9035"),
]

DIAGNOSES = [
    ("C50.911", "Stage IIIA breast cancer",       "IIIA"),
    ("C50.912", "Stage IIIB breast cancer",       "IIIB"),
    ("C50.911", "Stage IV breast cancer",         "IV"),
    ("C34.91",  "NSCLC stage IIIB",                "IIIB"),
    ("C34.10",  "NSCLC stage IV",                  "IV"),
    ("C18.9",   "Colon adenocarcinoma stage II",   "II"),
    ("C56.9",   "Ovarian cancer stage III",        "III"),
    ("C43.9",   "Melanoma stage IV",               "IV"),
    ("C61",     "Prostate cancer stage IV",        "IV"),
    ("C81.91",  "Hodgkin lymphoma stage II",       "II"),
    ("C64.9",   "Renal cell carcinoma stage IV",   "IV"),
    ("C71.9",   "Glioblastoma stage IV",           "IV"),
]

PATIENT_INITIALS = [
    "S.D.", "M.D.", "R.K.", "P.N.", "T.O.", "L.W.", "K.M.", "A.B.",
    "F.E.", "H.S.", "C.R.", "B.T.", "Y.J.", "N.G.", "V.D.", "Z.O.",
    "Q.L.", "X.M.", "G.P.", "I.A.", "O.K.", "U.R.", "E.S.", "W.J.",
    "D.C.", "J.H.", "T.F.", "R.P.", "M.S.", "K.L.", "B.W.", "C.G.",
]


def weighted_choice(weights: list[tuple]) -> tuple:
    """Return one tuple from a list of (item..., weight) using roulette wheel."""
    total = sum(w[-1] for w in weights)
    r = random.uniform(0, total)
    upto = 0.0
    for w in weights:
        upto += w[-1]
        if upto >= r:
            return w[:-1] if len(w) > 2 else w[0]
    return weights[-1][:-1] if len(weights[-1]) > 2 else weights[-1][0]


def choose_verdict_status() -> tuple[str | None, str]:
    """Return (verdict, status) tuple. Verdict is None for status-only outcomes."""
    r = random.random()
    cumulative = 0.0
    for verdict, status, weight in VERDICT_MIX:
        cumulative += weight
        if r < cumulative:
            return (verdict, status)
    for status, weight in STATUS_ONLY_MIX:
        cumulative += weight
        if r < cumulative:
            return (None, status)
    return ("APPROVE", "approved")


def make_minimal_fhir_bundle(patient_initial: str, diagnosis: tuple) -> dict:
    """Tiny FHIR bundle just to satisfy NOT NULL. Not used at LLM level."""
    icd10, desc, stage = diagnosis
    return {
        "resourceType": "Bundle",
        "id": f"seed-{uuid4().hex[:8]}",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "p1",
                    "gender": "female" if patient_initial[0] in "SMPLAFHCYNZQEDGIB" else "male",
                },
            },
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "dx1",
                    "code": {
                        "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": icd10}],
                        "text": desc,
                    },
                    "stage": [{"summary": {"text": stage}}],
                },
            },
        ],
    }


def random_timestamp(days_back_min: int, days_back_max: int) -> datetime:
    """Random timestamp in the last N days, with realistic working-hours bias."""
    days_back = random.uniform(days_back_min, days_back_max)
    base = datetime.now(timezone.utc) - timedelta(days=days_back)
    # Bias toward business hours (9 AM - 5 PM UTC)
    hour = random.choices(
        list(range(24)),
        weights=[1, 1, 1, 1, 1, 2, 4, 8, 12, 18, 22, 24, 22, 20, 18, 14, 10, 6, 4, 3, 2, 2, 1, 1],
    )[0]
    return base.replace(hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59))


async def seed():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        # Ensure org_demo exists (migration handles, but be safe)
        await conn.execute(
            """INSERT INTO organizations (id, name, slug)
               VALUES ('org_demo', 'Aerofyta Health Sciences', 'aerofyta')
               ON CONFLICT (id) DO NOTHING"""
        )

        # Skip if we already seeded
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM cases WHERE id LIKE 'seed_%'",
        )
        if existing >= TARGET_TOTAL - 5:
            print(f"Already seeded ({existing} cases). Skipping.")
            return

        approved_count = 0
        denied_count = 0
        referred_count = 0
        appealed_count = 0
        running_count = 0

        for i in range(TARGET_TOTAL):
            case_id = f"seed_{uuid4().hex[:10]}"
            payer = weighted_choice([(p, w) for p, w in PAYER_MIX])
            treatment, j_code = random.choice(TREATMENT_MIX)
            diagnosis = random.choice(DIAGNOSES)
            patient = random.choice(PATIENT_INITIALS)
            verdict, status = choose_verdict_status()
            created_at = random_timestamp(0, 90)

            fhir = make_minimal_fhir_bundle(patient, diagnosis)
            note = (
                f"{random.randint(38, 78)}yo {'F' if patient[0] in 'SMPLAFHCYNZQEDGIB' else 'M'} "
                f"with {diagnosis[1].lower()}. ECOG 1. Requesting {treatment}."
            )

            await conn.execute(
                """INSERT INTO cases (id, organization_id, created_at,
                                      payer_id, patient_initials,
                                      requested_treatment_name, requested_j_code,
                                      fhir_bundle, physician_note, status)
                   VALUES ($1, 'org_demo', $2, $3, $4, $5, $6, $7, $8, $9)
                   ON CONFLICT (id) DO NOTHING""",
                case_id, created_at, payer, patient,
                treatment, j_code, json.dumps(fhir), note, status,
            )

            # Insert decision if we have a verdict
            if verdict is not None:
                confidence = (
                    random.uniform(0.85, 0.99) if verdict == "APPROVE"
                    else random.uniform(0.40, 0.65) if verdict == "REFER"
                    else random.uniform(0.85, 0.98)  # DENY
                )
                rationale = {
                    "APPROVE": f"All Aetna criteria met for {treatment}. Biomarker confirmed, baseline workup complete, ECOG within range.",
                    "DENY":    f"Biomarker mismatch — {treatment} is not indicated for this patient's molecular profile.",
                    "REFER":   f"Documentation gap detected — {treatment} requires additional baseline data before authorization.",
                }[verdict]
                citations = [
                    {"kind": "clinical", "text": "Patient evidence", "pointer": "obs-1"},
                    {"kind": "policy",   "text": "Policy criterion", "pointer": f"policy:{payer}#initial"},
                ]
                await conn.execute(
                    """INSERT INTO decisions (case_id, verdict, rationale,
                                              citations_json, confidence,
                                              created_at)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    case_id, verdict, rationale, json.dumps(citations),
                    round(confidence, 2), created_at + timedelta(seconds=random.randint(60, 600)),
                )

            # Insert appeal if appealed status
            if status == "appealed":
                await conn.execute(
                    """INSERT INTO appeals (case_id, appeal_body,
                                            structured_arguments_json,
                                            created_at)
                       VALUES ($1, $2, $3, $4)""",
                    case_id,
                    f"Formal first-level appeal regarding denial of {treatment}. Clinical evidence supports overturn...",
                    json.dumps([{
                        "contested_criterion": "Biomarker requirement",
                        "payer_position": "Documentation insufficient",
                        "counter_position": "IHC report on file confirms eligibility",
                        "cited_evidence": ["Pathology dated 2026-02-15"],
                        "cited_policy_text": "Policy 0048 §1",
                        "cited_guideline": "NCCN Guideline v4.2024",
                    }]),
                    created_at + timedelta(hours=random.randint(2, 48)),
                )

            # Reviewer action for some referred cases
            if status == "referred" and random.random() < 0.4:
                await conn.execute(
                    """INSERT INTO reviewer_actions (case_id, reviewer_id, action,
                                                     note, created_at)
                       VALUES ($1, 'user_demoreviewer', 'add_note', $2, $3)""",
                    case_id,
                    "Awaiting additional documentation",
                    created_at + timedelta(hours=random.randint(1, 24)),
                )

            # Update counts
            if status == "approved": approved_count += 1
            elif status == "denied": denied_count += 1
            elif status == "referred": referred_count += 1
            elif status == "appealed": appealed_count += 1
            elif status == "running": running_count += 1

        print(f"Seeded {TARGET_TOTAL} cases under org_demo:")
        print(f"  approved:   {approved_count}")
        print(f"  denied:     {denied_count}")
        print(f"  referred:   {referred_count}")
        print(f"  appealed:   {appealed_count}")
        print(f"  running:    {running_count}")

        # Summary metrics
        total_cases = await conn.fetchval(
            "SELECT COUNT(*) FROM cases WHERE organization_id = 'org_demo'",
        )
        approval_rate = await conn.fetchval(
            """SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'approved')
                            / NULLIF(COUNT(*), 0), 1)
               FROM cases WHERE organization_id = 'org_demo'""",
        )
        print(f"\nOrg total: {total_cases} cases · {approval_rate}% approval rate")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
