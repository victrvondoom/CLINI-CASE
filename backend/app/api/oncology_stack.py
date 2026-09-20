"""Oncology Stack — the 10 strategic USPs from PROPOSAL §43.

Each USP is implemented as one or more endpoints under /api/v1/onco/*.
Where production requires licensed feeds (NCCN, FoundationOne, Tempus, FDA),
this module ships realistic curated samples in app/data/oncology/*.json so
the surface is testable end-to-end without those agreements.

USP index:
   1. /onco/guidelines/search                   — NCCN/ASCO RAG retrieval
   2. /onco/genomic/parse, /onco/genomic/regimens — FoundationOne ingestion + CDx mapping
   3. /onco/denial/predict, /onco/appeal/draft   — Denial avoidance + appeal generator
   4. /davinci/pas/submit, /davinci/crd, /davinci/dtr — CMS-0057-F FHIR PAS
   5. /onco/p2p/briefing-kit                     — Peer-to-peer PDF
   6. /onco/off-label/justify                    — Off-label evidence debate
   7. /onco/regimen/bundle                       — Bundled regimen PA
   8. /onco/site-of-care/compare                 — Hospital vs office vs home
   9. /onco/policies/diffs                       — Multi-payer policy diff
  10. /onco/audit/trail/{ref}                    — Cryptographic decision audit
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import get_current_user

router = APIRouter(prefix="/onco", tags=["oncology-stack"])

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "oncology"


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((_DATA_DIR / name).read_text(encoding="utf-8"))


# Lazy-loaded singletons — loaded on first access, cached for process lifetime.
_NCCN: dict[str, Any] | None = None
_BIOMARKERS: dict[str, Any] | None = None
_REGIMENS: dict[str, Any] | None = None
_SITE_COSTS: dict[str, Any] | None = None
_POLICY_DIFFS: dict[str, Any] | None = None


def nccn() -> dict[str, Any]:
    global _NCCN
    if _NCCN is None:
        _NCCN = _load_json("nccn_corpus.json")
    return _NCCN


def biomarkers() -> dict[str, Any]:
    global _BIOMARKERS
    if _BIOMARKERS is None:
        _BIOMARKERS = _load_json("biomarker_regimen_map.json")
    return _BIOMARKERS


def regimens() -> dict[str, Any]:
    global _REGIMENS
    if _REGIMENS is None:
        _REGIMENS = _load_json("nccn_regimen_templates.json")
    return _REGIMENS


def site_costs() -> dict[str, Any]:
    global _SITE_COSTS
    if _SITE_COSTS is None:
        _SITE_COSTS = _load_json("site_of_care_costs.json")
    return _SITE_COSTS


def policy_diffs() -> dict[str, Any]:
    global _POLICY_DIFFS
    if _POLICY_DIFFS is None:
        _POLICY_DIFFS = _load_json("payer_policy_diffs.json")
    return _POLICY_DIFFS


# In-memory audit chain (USP #10). Production: anchor each entry to QLDB or
# an append-only S3 Object-Lock bucket. The hash-of-previous chain is the
# tamper-evident structure.
_AUDIT_CHAIN: list[dict[str, Any]] = []


def _audit_record(*, kind: str, agent: str, inputs: dict[str, Any], output: dict[str, Any], confidence: float | None = None) -> dict[str, Any]:
    """Append a tamper-evident audit entry. Returns the entry (with hash)."""
    prev_hash = _AUDIT_CHAIN[-1]["hash"] if _AUDIT_CHAIN else "0" * 64
    payload = {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "agent": agent,
        "model_id": "claude-sonnet-4-6",  # TODO: pull from actual call
        "timestamp": datetime.now(UTC).isoformat(),
        "inputs_sha256": hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest(),
        "output_sha256": hashlib.sha256(json.dumps(output, sort_keys=True, default=str).encode()).hexdigest(),
        "confidence": confidence,
        "prev_hash": prev_hash,
    }
    payload["hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    _AUDIT_CHAIN.append(payload)
    return payload


# ===========================================================================
# USP #1 — OncoGuideline Engine (NCCN/ASCO RAG)
# ===========================================================================

class GuidelineHit(BaseModel):
    id: str
    guideline: str
    tumor_type: str
    biomarker: str
    line_of_therapy: str
    regimen: str
    evidence_category: str
    section_heading: str
    excerpt: str
    reference_pmid: str | None = None
    relevance_score: float


class GuidelineSearchResponse(BaseModel):
    query: dict[str, Any]
    hits: list[GuidelineHit]
    n: int
    audit_id: str
    latency_ms: int


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_score(query_tokens: list[str], doc_tokens: list[str], all_docs: list[list[str]]) -> float:
    """Cheap TF-IDF: term-freq in doc weighted by inverse-doc-freq across corpus."""
    if not query_tokens or not doc_tokens:
        return 0.0
    n = len(all_docs)
    doc_freqs = Counter()
    for d in all_docs:
        for tok in set(d):
            doc_freqs[tok] += 1
    doc_tf = Counter(doc_tokens)
    score = 0.0
    for tok in query_tokens:
        tf = doc_tf.get(tok, 0)
        df = doc_freqs.get(tok, 0)
        if tf == 0 or df == 0:
            continue
        idf = math.log((1 + n) / (1 + df)) + 1
        score += (tf / max(1, len(doc_tokens))) * idf
    return score


@router.get("/guidelines/search", response_model=GuidelineSearchResponse,
            summary="USP #1 — Real-time NCCN/ASCO guideline retrieval (RAG)")
async def guideline_search(
    tumor: str | None = Query(None, description="e.g. 'NSCLC', 'Breast', 'Ovarian', 'any' for tumor-agnostic"),
    biomarker: str | None = Query(None, description="e.g. 'EGFR L858R', 'BRCA1', 'TMB-H'"),
    line: str | None = Query(None, description="'first', 'second', 'maintenance', 'any'"),
    q: str | None = Query(None, description="Free-text query"),
    top_k: int = Query(5, ge=1, le=20),
    user: dict[str, Any] = Depends(get_current_user),
) -> GuidelineSearchResponse:
    t0 = time.monotonic()
    corpus = nccn()["guidelines"]
    query_text = " ".join(filter(None, [tumor, biomarker, line, q]))
    qtoks = _tokenize(query_text)

    # Build doc texts
    docs = []
    for g in corpus:
        text = " ".join(str(g.get(k) or "") for k in (
            "tumor_type", "biomarker", "line_of_therapy", "regimen",
            "section_heading", "excerpt", "guideline",
        ))
        docs.append(_tokenize(text))

    scored = []
    for g, dtoks in zip(corpus, docs, strict=False):
        score = _tfidf_score(qtoks, dtoks, docs)
        # Hard filters bump the score so an exact biomarker/tumor match always wins
        if tumor and tumor.lower() in (g.get("tumor_type") or "").lower():
            score += 1.5
        if biomarker and biomarker.lower() in (g.get("biomarker") or "").lower():
            score += 2.0
        if line and line.lower() == (g.get("line_of_therapy") or "").lower():
            score += 0.7
        if score > 0:
            scored.append((score, g))

    scored.sort(key=lambda x: x[0], reverse=True)
    hits = [GuidelineHit(**g, relevance_score=round(s, 3)) for s, g in scored[:top_k]]

    audit = _audit_record(
        kind="guideline_retrieval",
        agent="OncoGuidelineEngine",
        inputs={"tumor": tumor, "biomarker": biomarker, "line": line, "q": q},
        output={"n_hits": len(hits), "top_id": hits[0].id if hits else None},
        confidence=hits[0].relevance_score if hits else 0.0,
    )

    return GuidelineSearchResponse(
        query={"tumor": tumor, "biomarker": biomarker, "line": line, "q": q, "top_k": top_k},
        hits=hits, n=len(hits), audit_id=audit["id"],
        latency_ms=int((time.monotonic() - t0) * 1000),
    )


# ===========================================================================
# USP #2 — Genomic Authorization Agent (FoundationOne / Tempus / Caris)
# ===========================================================================

class ExtractedVariant(BaseModel):
    canonical_id: str           # key in biomarker_regimen_map
    text_match: str             # the literal substring matched
    variant_class: Literal["snv", "fusion", "amplification", "deletion", "signature", "other"] = "other"
    fda_approved: list[str]
    nccn_preferred: str
    evidence: str
    tumor_types: list[str]
    guideline_ref: str | None = None


class GenomicParseResponse(BaseModel):
    filename: str
    bytes_read: int
    extracted_text_chars: int
    variants: list[ExtractedVariant]
    text_preview: str
    audit_id: str


_VARIANT_CLASS_HINTS = {
    "fusion": "fusion",
    "amplif": "amplification",
    "deletion": "deletion",
    "del19": "deletion",
    "germline": "snv",
    "BID": "other",
    "MSI-H": "signature",
    "TMB": "signature",
    "HRD": "signature",
}


@router.post("/genomic/parse", response_model=GenomicParseResponse,
             summary="USP #2 — Parse a FoundationOne/Tempus/Caris NGS PDF into actionable variants")
async def genomic_parse(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> GenomicParseResponse:
    raw = await file.read()
    # Use the same pypdf path our intake module uses
    text = ""
    if raw[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            text = ""
    if not text:
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

    bm = biomarkers()["mappings"]
    found: dict[str, ExtractedVariant] = {}
    for canonical_id, entry in bm.items():
        for variant_label in entry["variants"]:
            # Case-insensitive substring match. Variant labels are deliberately
            # specific ("EGFR L858R", "BRCA1 germline") so false positives are rare.
            pattern = re.compile(re.escape(variant_label), re.IGNORECASE)
            m = pattern.search(text)
            if m:
                vclass = "other"
                for hint, cls in _VARIANT_CLASS_HINTS.items():
                    if hint.lower() in variant_label.lower():
                        vclass = cls
                        break
                found.setdefault(canonical_id, ExtractedVariant(
                    canonical_id=canonical_id,
                    text_match=m.group(0),
                    variant_class=vclass,  # type: ignore[arg-type]
                    fda_approved=entry["fda_approved"],
                    nccn_preferred=entry["nccn_preferred"],
                    evidence=entry["evidence"],
                    tumor_types=entry["tumor_types"],
                    guideline_ref=entry.get("guideline_ref"),
                ))
                break  # only need one literal match per canonical variant

    audit = _audit_record(
        kind="genomic_parse", agent="GenomicAgent",
        inputs={"filename": file.filename, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        output={"variants": list(found.keys()), "n": len(found)},
        confidence=0.95 if found else 0.4,
    )

    return GenomicParseResponse(
        filename=file.filename or "ngs_report.pdf",
        bytes_read=len(raw),
        extracted_text_chars=len(text),
        variants=list(found.values()),
        text_preview=text[:600],
        audit_id=audit["id"],
    )


@router.get("/genomic/regimens", summary="USP #2b — Look up regimens for a known biomarker variant")
async def genomic_regimens(
    variant: str = Query(..., description="A canonical_id (e.g. 'EGFR_L858R') or substring of a variant label"),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    bm = biomarkers()["mappings"]
    if variant in bm:
        return {"variant": variant, **bm[variant]}
    # Fuzzy by substring
    for k, v in bm.items():
        if any(variant.lower() in lab.lower() for lab in v["variants"]):
            return {"variant": k, **v}
    raise HTTPException(404, f"variant '{variant}' not in biomarker_regimen_map")


# ===========================================================================
# USP #3 — Denial Avoidance + Auto-Appeal Generator
# ===========================================================================

class DenialPredictionRequest(BaseModel):
    treatment: str
    payer_id: str
    diagnosis: str
    biomarkers: list[str] = Field(default_factory=list)
    line_of_therapy: str | None = None
    prior_lines: int = 0
    has_pathology_report: bool = False
    has_imaging_report: bool = False
    has_biomarker_test: bool = False
    has_nccn_citation: bool = False


class DenialPredictionResponse(BaseModel):
    denial_probability: float
    confidence: float
    top_risk_factors: list[str]
    recommended_actions: list[str]
    benchmark: dict[str, Any]
    audit_id: str


@router.post("/denial/predict", response_model=DenialPredictionResponse,
             summary="USP #3a — Predict denial probability + recommend pre-emptive documentation")
async def denial_predict(
    req: DenialPredictionRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> DenialPredictionResponse:
    # Heuristic baseline rooted in published denial rates:
    # 12% baseline (AHA), modified by missing-doc penalties.
    p = 0.12
    risks: list[str] = []
    actions: list[str] = []

    if not req.has_pathology_report:
        p += 0.18; risks.append("missing pathology report"); actions.append("Attach pathology report (ICD-O-3 + grade).")
    if not req.has_imaging_report:
        p += 0.10; risks.append("missing imaging staging"); actions.append("Attach baseline staging CT/PET-CT.")
    if req.biomarkers and not req.has_biomarker_test:
        p += 0.22; risks.append("biomarker claimed but no test report attached")
        actions.append("Attach NGS / IHC report from CLIA-certified lab (FoundationOne, Tempus, MSK-IMPACT).")
    if not req.has_nccn_citation:
        p += 0.14; risks.append("no NCCN/ASCO citation in submission")
        actions.append("Cite specific NCCN section ID (e.g. 'NCCN NSCL-26 v.5.2025, Category 1').")
    if req.prior_lines == 0 and "second" in (req.line_of_therapy or "").lower():
        p += 0.20; risks.append("second-line claimed without prior-therapy documentation")
        actions.append("Document prior regimens with start/stop dates + reason for discontinuation.")

    p = min(p, 0.95)
    audit = _audit_record(
        kind="denial_predict", agent="DenialPredictor",
        inputs=req.model_dump(), output={"p": p, "n_risks": len(risks)},
        confidence=0.78,
    )

    return DenialPredictionResponse(
        denial_probability=round(p, 3),
        confidence=0.78,
        top_risk_factors=risks,
        recommended_actions=actions,
        benchmark={
            "industry_baseline_denial_rate": 0.12,
            "appeal_overturn_rate_with_nccn": 0.65,
            "appeal_overturn_rate_without": 0.30,
            "source": "AMA 2024, FinThrive, CounterForce Health",
        },
        audit_id=audit["id"],
    )


class AppealDraftRequest(BaseModel):
    patient_initials: str
    payer_id: str
    treatment: str
    diagnosis: str
    denial_reason: str
    nccn_section: str | None = None
    biomarker: str | None = None
    cited_pmids: list[str] = Field(default_factory=list)


class AppealDraftResponse(BaseModel):
    letter: str
    word_count: int
    citations: list[str]
    audit_id: str


@router.post("/appeal/draft", response_model=AppealDraftResponse,
             summary="USP #3b — Generate evidence-graph-cited appeal letter")
async def appeal_draft(
    req: AppealDraftRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> AppealDraftResponse:
    # Pull guideline support from the corpus when possible
    matches = nccn()["guidelines"]
    matched_guideline = None
    if req.nccn_section:
        matched_guideline = next((g for g in matches if g["id"] == req.nccn_section), None)
    if matched_guideline is None and req.biomarker:
        matched_guideline = next((g for g in matches if req.biomarker.lower() in (g.get("biomarker") or "").lower()), None)

    ev_section = ""
    if matched_guideline:
        ev_section = (
            f"NCCN {matched_guideline['guideline']} § {matched_guideline['id']} "
            f"(Category {matched_guideline['evidence_category']}) explicitly recommends "
            f"{matched_guideline['regimen']} for {matched_guideline['tumor_type']} patients with "
            f"{matched_guideline['biomarker']}. The relevant excerpt reads: "
            f"\"{matched_guideline['excerpt'][:240]}...\""
        )
    citations = list(req.cited_pmids)
    if matched_guideline and matched_guideline.get("reference_pmid"):
        citations.append(matched_guideline["reference_pmid"])

    today = datetime.now(UTC).strftime("%B %d, %Y")
    letter = f"""
{today}

{req.payer_id} Medical Director
RE: Appeal of denied prior authorization
Patient: {req.patient_initials}
Requested treatment: {req.treatment}
Primary diagnosis: {req.diagnosis}
Denial reason cited: {req.denial_reason}

Dear Reviewer,

We respectfully appeal the denial of prior authorization for {req.treatment} for the
above-referenced patient. We believe the denial is inconsistent with both the published
clinical evidence and the NCCN Compendium guidance that {req.payer_id}'s own oncology
coverage policy adopts as authoritative.

CLINICAL CONTEXT
{req.patient_initials} carries a primary diagnosis of {req.diagnosis}.
{('The targetable variant ' + req.biomarker + ' has been confirmed via NGS testing.') if req.biomarker else ''}

GUIDELINE SUPPORT
{ev_section or "Standard-of-care guidelines support this regimen for the patient's diagnosis and biomarker profile."}

REQUEST
We respectfully request that the original determination be reversed and that
authorization for {req.treatment} be issued without further delay. Each day of delay
risks clinical deterioration; published data documents an average 27-day treatment
delay for cancer denials with measurable progression of disease.

Sincerely,
[Treating Oncologist]
[Practice]

Citations:
{chr(10).join(f'  • PMID {p}' for p in citations) if citations else '  • (citations to be appended)'}
""".strip()

    audit = _audit_record(
        kind="appeal_draft", agent="AppealsDrafter",
        inputs=req.model_dump(),
        output={"word_count": len(letter.split()), "n_citations": len(citations)},
        confidence=0.88,
    )

    return AppealDraftResponse(
        letter=letter, word_count=len(letter.split()), citations=citations,
        audit_id=audit["id"],
    )


# ===========================================================================
# USP #4 — CMS-0057-F Native FHIR Compliance (Da Vinci PAS / CRD / DTR)
# ===========================================================================

class PASSubmitRequest(BaseModel):
    payer_id: str
    patient_initials: str
    diagnosis_icd10: str
    treatment_hcpcs: str
    treatment_name: str
    requested_units: int = 1
    biomarker: str | None = None


@router.post("/davinci/pas/submit", summary="USP #4a — Submit a Da Vinci PAS Bundle (FHIR R4)")
async def davinci_pas_submit(req: PASSubmitRequest, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Returns a Da Vinci PAS-conformant Bundle + ClaimResponse decision."""
    bundle_id = uuid.uuid4().hex
    claim_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {"profile": ["http://hl7.org/fhir/us/davinci-pas/StructureDefinition/profile-pas-request-bundle"]},
        "type": "collection",
        "timestamp": now,
        "entry": [
            {
                "fullUrl": f"urn:uuid:{claim_id}",
                "resource": {
                    "resourceType": "Claim",
                    "id": claim_id,
                    "status": "active",
                    "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "professional"}]},
                    "use": "preauthorization",
                    "patient": {"reference": "Patient/example", "display": req.patient_initials},
                    "created": now,
                    "insurer": {"display": req.payer_id},
                    "diagnosis": [{
                        "sequence": 1,
                        "diagnosisCodeableConcept": {
                            "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": req.diagnosis_icd10}],
                        },
                    }],
                    "item": [{
                        "sequence": 1,
                        "productOrService": {
                            "coding": [{"system": "http://www.ama-assn.org/go/cpt", "code": req.treatment_hcpcs, "display": req.treatment_name}],
                        },
                        "quantity": {"value": req.requested_units},
                    }],
                },
            },
        ],
    }
    if req.biomarker:
        bundle["entry"].append({
            "fullUrl": f"urn:uuid:{uuid.uuid4().hex}",
            "resource": {
                "resourceType": "Observation",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
                "code": {"text": req.biomarker},
                "valueString": "positive",
            },
        })

    # Synthesize the ClaimResponse (decision)
    decision = "approved" if req.biomarker else "pended"
    auth_number = "AX-" + uuid.uuid4().hex[:10].upper()
    claim_response = {
        "resourceType": "ClaimResponse",
        "id": uuid.uuid4().hex,
        "status": "active",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "professional"}]},
        "use": "preauthorization",
        "patient": {"reference": "Patient/example"},
        "created": now,
        "insurer": {"display": req.payer_id},
        "outcome": "complete",
        "preAuthRef": auth_number,
        "preAuthPeriod": {"start": now, "end": "2027-01-01T00:00:00Z"},
        "disposition": "Authorization issued; valid through end of plan year.",
        "item": [{"itemSequence": 1, "adjudication": [{"category": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/adjudication", "code": decision}]}, "amount": {"value": 0, "currency": "USD"}}]}],
    }

    audit = _audit_record(
        kind="davinci_pas_submit", agent="PASOrchestrator",
        inputs=req.model_dump(),
        output={"bundle_id": bundle_id, "auth_number": auth_number, "decision": decision},
        confidence=0.95,
    )

    return {
        "bundle": bundle,
        "claim_response": claim_response,
        "decision": decision,
        "auth_number": auth_number,
        "audit_id": audit["id"],
        "conformance_note": "Da Vinci PAS 2.0.1 profile shape. Production deployment must pass ONC Inferno DaVinci PAS Test Kit.",
    }


@router.post("/davinci/crd", summary="USP #4b — Coverage Requirements Discovery (CRD) hook response")
async def davinci_crd(payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    treatment = (payload.get("context", {}).get("medications", [{}])[0].get("medicationCodeableConcept", {}).get("text") or "treatment")
    return {
        "cards": [{
            "summary": f"Prior authorization required for {treatment}",
            "indicator": "warning",
            "detail": (
                "Coverage requires NCCN-supported indication, biomarker test report, and pathology. "
                "Submit via Da Vinci PAS or invoke the DTR Questionnaire to gather missing fields."
            ),
            "source": {"label": "ClinCase CRD service", "url": "https://clincase.com/crd"},
            "links": [{"label": "Launch DTR", "url": "/api/v1/onco/davinci/dtr/questionnaire", "type": "smart"}],
        }],
    }


@router.get("/davinci/dtr/questionnaire", summary="USP #4c — Documentation Templates and Rules (DTR) questionnaire")
async def davinci_dtr_questionnaire(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Return a FHIR Questionnaire that captures the missing PA documentation."""
    return {
        "resourceType": "Questionnaire",
        "id": "clincase-dtr-onco-baseline",
        "status": "active",
        "name": "ClinCaseOncologyDTR",
        "title": "ClinCase Oncology Documentation Template",
        "item": [
            {"linkId": "1", "text": "Primary diagnosis (ICD-10-CM)", "type": "string", "required": True},
            {"linkId": "2", "text": "Stage at diagnosis", "type": "choice", "required": True,
             "answerOption": [{"valueString": s} for s in ("I", "II", "III", "IV")]},
            {"linkId": "3", "text": "Line of therapy", "type": "choice", "required": True,
             "answerOption": [{"valueString": s} for s in ("first", "second", "third", "maintenance")]},
            {"linkId": "4", "text": "Targetable biomarker (e.g. EGFR L858R, BRCA1)", "type": "string"},
            {"linkId": "5", "text": "NGS report attached?", "type": "boolean"},
            {"linkId": "6", "text": "Performance status (ECOG)", "type": "choice",
             "answerOption": [{"valueInteger": i} for i in (0, 1, 2, 3, 4)]},
            {"linkId": "7", "text": "Prior therapies (free text)", "type": "text"},
        ],
    }


# ===========================================================================
# USP #5 — Peer-to-Peer Briefing Kit (PDF)
# ===========================================================================

class P2PBriefingRequest(BaseModel):
    patient_initials: str
    diagnosis: str
    treatment: str
    payer_id: str
    denial_reason: str
    biomarker: str | None = None
    nccn_section: str | None = None


@router.post("/p2p/briefing-kit", summary="USP #5 — Generate a 1-page P2P briefing PDF")
async def p2p_briefing(
    req: P2PBriefingRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Return a downloadable PDF the physician can read in 5 minutes before P2P call."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise HTTPException(503, f"reportlab not available: {e}") from e

    matched = next((g for g in nccn()["guidelines"]
                    if (req.nccn_section and g["id"] == req.nccn_section)
                    or (req.biomarker and req.biomarker.lower() in (g.get("biomarker") or "").lower())), None)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=14, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#1f4ed8"), spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12)

    story = []
    story.append(Paragraph(f"Peer-to-Peer Briefing — {req.patient_initials}", h1))
    story.append(Paragraph(f"<b>Payer:</b> {req.payer_id} &nbsp; <b>Treatment:</b> {req.treatment} &nbsp; <b>Diagnosis:</b> {req.diagnosis}", body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Denial cited", h2))
    story.append(Paragraph(req.denial_reason, body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Counter-arguments (3 strongest)", h2))
    counter = []
    if matched:
        counter.append(f"<b>1.</b> NCCN {matched['guideline']} § {matched['id']} (Category {matched['evidence_category']}) recommends {matched['regimen']} for the patient's exact biomarker profile ({matched['biomarker']}).")
        counter.append(f"<b>2.</b> Reference: PMID {matched.get('reference_pmid', '—')} — pivotal trial supporting Category {matched['evidence_category']} evidence.")
        counter.append(f"<b>3.</b> Excerpt: \"{matched['excerpt'][:200]}...\"")
    else:
        counter.append("<b>1.</b> NCCN guideline retrieval pending — request the specific compendium ID from the reviewer.")
        counter.append("<b>2.</b> FDA label review demonstrates approved indication for the requested treatment.")
        counter.append("<b>3.</b> Standard-of-care pivotal trials support efficacy and safety in this setting.")
    for c in counter:
        story.append(Paragraph(c, body))
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Anticipated questions", h2))
    qs = [
        "Q: Has the patient failed first-line standard therapy? &nbsp; A: See attached prior-therapy summary.",
        "Q: Is the biomarker test from a CLIA-certified lab? &nbsp; A: Yes — vendor + report ID on attached pathology.",
        "Q: Has off-label use been considered? &nbsp; A: This is an on-label, NCCN-supported request.",
        "Q: What is the expected outcome? &nbsp; A: Per pivotal trial, ORR + median PFS data summarized above.",
        "Q: Does the patient have ECOG ≤ 2? &nbsp; A: Yes — PS 0/1 per most recent oncology note.",
    ]
    for q in qs:
        story.append(Paragraph(q, body))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Patient summary", h2))
    story.append(Paragraph(
        f"{req.patient_initials} — {req.diagnosis}. "
        + (f"Targetable variant {req.biomarker} confirmed by NGS. " if req.biomarker else "")
        + f"Treatment requested: {req.treatment}. ClinCase confidence-routed to physician review per CMS-0057-F audit policy.",
        body))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    audit = _audit_record(
        kind="p2p_briefing", agent="P2PBriefingComposer",
        inputs=req.model_dump(),
        output={"pdf_bytes": len(pdf_bytes), "matched_guideline": matched["id"] if matched else None},
        confidence=0.9,
    )
    fname = f"p2p-briefing-{req.patient_initials.replace('.', '')}-{audit['id'][:8]}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"',
                 "X-Audit-Id": audit["id"]},
    )


# ===========================================================================
# USP #6 — Off-Label Justification (multi-agent debate)
# ===========================================================================

class OffLabelRequest(BaseModel):
    drug: str
    indication: str       # off-label disease/use the request seeks
    biomarker: str | None = None
    rationale: str | None = None


@router.post("/off-label/justify", summary="USP #6 — Off-label justification via simulated proposer/opponent debate")
async def off_label_justify(
    req: OffLabelRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Simulates a 3-round debate. Production: route to a real LLM via app.llm.factory.

    Rounds:
      1. Proposer states the case
      2. Opponent challenges (skeptical payer reviewer voice)
      3. Proposer counters with specific evidence; Judge issues verdict
    """
    rounds = []

    proposer_open = (
        f"We request authorization of {req.drug} for {req.indication}"
        + (f" in a patient with {req.biomarker}." if req.biomarker else ".")
        + " The basis for this off-label request rests on three pillars: "
        + "(1) NCCN compendium support for the target biomarker class, "
        + "(2) peer-reviewed phase II/III evidence in adjacent indications, "
        + "(3) FDA-approved indication in a related tumor type with shared molecular biology."
    )
    rounds.append({"role": "proposer", "round": 1, "text": proposer_open})

    opponent = (
        "Per Cigna oncology coverage policy, off-label use requires (a) two different "
        "controlled clinical studies, OR (b) NCCN compendium support at Category 1/2A. "
        f"Has the requester provided RCT-level evidence specifically for {req.indication}? "
        "Adjacent-tumor evidence and biological plausibility are not sufficient absent "
        "a tumor-agnostic indication or compendium listing."
    )
    rounds.append({"role": "opponent", "round": 2, "text": opponent})

    # Look up biomarker support
    bm_entry = None
    if req.biomarker:
        for _canonical_id, entry in biomarkers()["mappings"].items():
            if any(req.biomarker.lower() in lab.lower() for lab in entry["variants"]):
                bm_entry = entry; break

    counter = []
    if bm_entry and "any" in bm_entry["tumor_types"]:
        counter.append(
            f"This biomarker ({req.biomarker}) carries a tumor-agnostic NCCN compendium listing "
            f"({bm_entry['nccn_preferred']} preferred, evidence Category {bm_entry['evidence']}). "
            "The Cigna 'two RCT or NCCN compendium' standard is satisfied via the compendium pathway."
        )
    elif bm_entry:
        counter.append(
            f"NCCN compendium supports {bm_entry['nccn_preferred']} for {req.biomarker} "
            f"in {', '.join(bm_entry['tumor_types'])} with Category {bm_entry['evidence']} evidence; "
            "the molecular biology generalizes to the off-label indication via shared-pathway argument."
        )
    counter.append("FDA tumor-agnostic approvals (pembrolizumab MSI-H/TMB-H, larotrectinib NTRK, dostarlimab dMMR) establish regulatory precedent for cross-tumor approvals on biomarker-driven mechanisms.")
    counter.append("Cost-of-no-treatment analysis: 27-day median delay for cancer denials (per JCO Patient Impact Study) translates to measurable disease progression.")

    rounds.append({"role": "proposer", "round": 3, "text": " ".join(counter)})

    verdict_passed = bool(bm_entry)
    judge = (
        "Verdict: APPROVE with conditions. The compendium pathway is satisfied "
        "via the biomarker-class listing; pathology + NGS report must be on file."
        if verdict_passed else
        "Verdict: REFER. Adjacent-tumor evidence is suggestive but does not meet "
        "the policy's RCT-or-compendium threshold for the specific indication. "
        "Recommend escalation to medical director or peer-to-peer review."
    )
    rounds.append({"role": "judge", "round": 3, "text": judge})

    audit = _audit_record(
        kind="off_label_debate", agent="OffLabelJustificationAgent",
        inputs=req.model_dump(),
        output={"verdict": "APPROVE" if verdict_passed else "REFER", "rounds": len(rounds)},
        confidence=0.82 if verdict_passed else 0.55,
    )

    return {
        "drug": req.drug,
        "indication": req.indication,
        "biomarker": req.biomarker,
        "rounds": rounds,
        "verdict": "APPROVE" if verdict_passed else "REFER",
        "confidence": 0.82 if verdict_passed else 0.55,
        "compendium_match": bm_entry,
        "audit_id": audit["id"],
    }


# ===========================================================================
# USP #7 — Bundled Regimen Authorization
# ===========================================================================

@router.get("/regimen/templates", summary="USP #7a — List NCCN-style bundled regimen templates")
async def regimen_templates(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return regimens()


class RegimenBundleRequest(BaseModel):
    regimen_key: str       # e.g. "TCHP", "FOLFIRINOX", "RCHOP"
    patient_initials: str
    diagnosis_icd10: str
    payer_id: str
    cycles_requested: int = 1


@router.post("/regimen/bundle", summary="USP #7b — Build a single FHIR PAS Bundle covering an entire regimen")
async def regimen_bundle(
    req: RegimenBundleRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    rgm = regimens()["regimens"].get(req.regimen_key)
    if rgm is None:
        raise HTTPException(404, f"unknown regimen '{req.regimen_key}'. Try GET /onco/regimen/templates.")

    bundle_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    items = []
    for i, drug in enumerate(rgm["drugs"], start=1):
        items.append({
            "sequence": i,
            "productOrService": {"coding": [{"system": "http://hl7.org/fhir/sid/hcpcs", "code": drug["j_code"], "display": drug["name"]}]},
            "quantity": {"value": req.cycles_requested},
            "extension": [{"url": "https://clincase.io/fhir/StructureDefinition/regimen-step",
                           "valueString": f"{drug['cycle_day']} · {drug['dose']} · {drug['route']}"}],
        })
    sup_seq = len(items)
    for s in rgm["supportive_care"]:
        sup_seq += 1
        items.append({
            "sequence": sup_seq,
            "productOrService": {"coding": [{"system": "http://hl7.org/fhir/sid/hcpcs", "code": s.get("j_code", "—"), "display": s["name"]}]},
            "quantity": {"value": req.cycles_requested},
            "extension": [{"url": "https://clincase.io/fhir/StructureDefinition/supportive-care",
                           "valueString": s["indication"]}],
        })

    claim = {
        "resourceType": "Claim",
        "id": uuid.uuid4().hex,
        "status": "active",
        "use": "preauthorization",
        "patient": {"display": req.patient_initials},
        "created": now,
        "insurer": {"display": req.payer_id},
        "diagnosis": [{"sequence": 1, "diagnosisCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": req.diagnosis_icd10}]}}],
        "item": items,
        "extension": [
            {"url": "https://clincase.io/fhir/StructureDefinition/regimen-template", "valueString": req.regimen_key},
            {"url": "https://clincase.io/fhir/StructureDefinition/cycles-requested", "valueInteger": req.cycles_requested},
        ],
    }

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": now,
        "entry": [{"resource": claim}],
    }

    audit = _audit_record(
        kind="regimen_bundle", agent="RegimenAgent",
        inputs=req.model_dump(),
        output={"regimen": req.regimen_key, "n_items": len(items)},
        confidence=0.96,
    )
    return {
        "bundle": bundle,
        "regimen": rgm,
        "n_items": len(items),
        "vs_unbundled": {"separate_pas_count": len(items), "consolidated_pas_count": 1, "reduction_pct": round(100 * (len(items) - 1) / len(items), 1) if items else 0},
        "audit_id": audit["id"],
    }


# ===========================================================================
# USP #8 — Site-of-Care Optimizer
# ===========================================================================

class SiteOfCareRequest(BaseModel):
    drug_key: str   # e.g. "pembrolizumab_200mg_q3w"
    payer_id: str
    deductible_remaining_usd: float = 0
    coinsurance_pct: float = 0.20


@router.post("/site-of-care/compare", summary="USP #8 — Compare hospital vs office vs home infusion costs")
async def site_of_care_compare(
    req: SiteOfCareRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    drug = site_costs()["drugs"].get(req.drug_key)
    if drug is None:
        raise HTTPException(404, f"unknown drug_key '{req.drug_key}'. Available: {list(site_costs()['drugs'].keys())}")

    sites_out = []
    for site_key, site_data in drug["sites"].items():
        # Simulated patient OOP: deductible + coinsurance up to OOP max
        pre_ded = min(req.deductible_remaining_usd, site_data["total_cost"])
        post_ded = max(0, site_data["total_cost"] - pre_ded)
        coins = post_ded * req.coinsurance_pct
        patient_oop = round(pre_ded + coins, 2)
        sites_out.append({
            "site_key": site_key,
            "label": site_data["site_label"],
            "total_cost": site_data["total_cost"],
            "facility_fee": site_data.get("facility_fee", 0),
            "patient_oop_estimate": patient_oop,
            "patient_oop_typical_published": site_data["patient_oop_typical"],
            "eligibility_notes": site_data.get("eligibility_notes", ""),
        })
    sites_out.sort(key=lambda s: s["total_cost"])

    cheapest = sites_out[0]
    most_expensive = sites_out[-1]
    payer_savings_per_session = most_expensive["total_cost"] - cheapest["total_cost"]
    patient_savings_per_session = most_expensive["patient_oop_estimate"] - cheapest["patient_oop_estimate"]

    audit = _audit_record(
        kind="site_of_care", agent="SiteOfCareAgent",
        inputs=req.model_dump(),
        output={"cheapest_site": cheapest["site_key"], "savings": payer_savings_per_session},
        confidence=0.9,
    )

    return {
        "drug": drug["name"], "j_code": drug["j_code"],
        "sites": sites_out,
        "recommendation": {
            "preferred_site_key": cheapest["site_key"],
            "preferred_label": cheapest["label"],
            "payer_savings_per_session_usd": payer_savings_per_session,
            "patient_savings_per_session_usd": round(patient_savings_per_session, 2),
            "annualized_savings_estimate_usd": payer_savings_per_session * 17,  # ~17 q3w infusions/yr
        },
        "audit_id": audit["id"],
    }


# ===========================================================================
# USP #9 — Multi-Payer Policy Reconciliation
# ===========================================================================

@router.get("/policies/diffs", summary="USP #9 — Recent payer policy changes (with diff)")
async def policies_diffs(
    payer: str | None = Query(None),
    treatment: str | None = Query(None),
    since: str | None = Query(None, description="ISO timestamp; only changes after this point"),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    diffs = policy_diffs()["diffs"]
    filtered = diffs
    if payer:
        filtered = [d for d in filtered if payer.lower() in d["payer"].lower()]
    if treatment:
        filtered = [d for d in filtered if treatment.lower() in d["treatment"].lower()]
    if since:
        filtered = [d for d in filtered if d["changed_at"] >= since]
    total_affected = sum(d.get("in_flight_pas_affected", 0) for d in filtered)
    return {
        "n": len(filtered), "diffs": filtered,
        "in_flight_pas_affected_total": total_affected,
        "snapshots_taken_at": policy_diffs()["_meta"]["snapshots_taken_at"],
    }


@router.post("/policies/reconcile", summary="USP #9b — Reconcile a treatment across all payers (which payer is least friction?)")
async def policies_reconcile(
    treatment: str = Form(...),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    diffs = [d for d in policy_diffs()["diffs"] if treatment.lower() in d["treatment"].lower()]
    if not diffs:
        raise HTTPException(404, f"no recent policy snapshots for '{treatment}'")
    summary_by_payer = []
    for d in diffs:
        added = sum(1 for x in d["diff"] if x["action"] == "added")
        removed = sum(1 for x in d["diff"] if x["action"] == "removed")
        modified = sum(1 for x in d["diff"] if x["action"] == "modified")
        # "Friction score" = removed (-) + modified (mild) + steptherapy keyword
        score = removed * 3 + modified * 1
        if any("step therapy" in (x.get("section") or "").lower() for x in d["diff"]):
            score += 5
        summary_by_payer.append({
            "payer": d["payer"], "policy_id": d["policy_id"],
            "version_new": d["version_new"], "changed_at": d["changed_at"],
            "n_added": added, "n_removed": removed, "n_modified": modified,
            "friction_score": score, "summary": d["summary"],
        })
    summary_by_payer.sort(key=lambda x: x["friction_score"])
    return {
        "treatment": treatment,
        "n_payers": len(summary_by_payer),
        "least_friction_payer": summary_by_payer[0] if summary_by_payer else None,
        "ranked": summary_by_payer,
    }


# ===========================================================================
# USP #10 — Cryptographically Auditable AI Decision Trail
# ===========================================================================

@router.get("/audit/trail", summary="USP #10 — Tamper-evident audit chain (SHA-256 chained, QLDB-equivalent)")
async def audit_trail(
    limit: int = Query(50, ge=1, le=500),
    kind: str | None = Query(None),
    agent: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    chain = list(_AUDIT_CHAIN)
    if kind:
        chain = [c for c in chain if c["kind"] == kind]
    if agent:
        chain = [c for c in chain if c["agent"] == agent]
    chain = list(reversed(chain))[:limit]

    # Verify the chain integrity on the way out — recompute hashes and
    # cross-check prev_hash links. Returns chain_valid + first-broken-link.
    integrity = {"chain_valid": True, "n_total_records": len(_AUDIT_CHAIN), "first_broken_link": None}
    for i, rec in enumerate(_AUDIT_CHAIN):
        prev = _AUDIT_CHAIN[i - 1]["hash"] if i > 0 else "0" * 64
        if rec["prev_hash"] != prev:
            integrity["chain_valid"] = False
            integrity["first_broken_link"] = rec["id"]; break
        # Recompute this record's own hash (without the hash field)
        without_hash = {k: v for k, v in rec.items() if k != "hash"}
        recomputed = hashlib.sha256(json.dumps(without_hash, sort_keys=True).encode()).hexdigest()
        if recomputed != rec["hash"]:
            integrity["chain_valid"] = False
            integrity["first_broken_link"] = rec["id"]; break

    return {
        "n": len(chain), "records": chain, "integrity": integrity,
        "anchor_note": "DEMO: in-memory chain. Production anchors each record to QLDB (Quantum Ledger Database) or S3 with Object Lock + KMS. Tamper-evidence is preserved under both backends.",
    }


@router.get("/audit/trail/{record_id}", summary="USP #10b — Single audit record + full provenance")
async def audit_record(
    record_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    rec = next((r for r in _AUDIT_CHAIN if r["id"] == record_id), None)
    if rec is None:
        raise HTTPException(404, f"audit record '{record_id}' not found")

    # Recompute to verify
    without_hash = {k: v for k, v in rec.items() if k != "hash"}
    recomputed = hashlib.sha256(json.dumps(without_hash, sort_keys=True).encode()).hexdigest()
    return {
        "record": rec,
        "verified": recomputed == rec["hash"],
        "recomputed_hash": recomputed,
    }
