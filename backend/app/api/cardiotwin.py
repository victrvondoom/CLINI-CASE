"""CardioTwin API — cardiovascular risk visualisation & vessel-level prediction.

Mounted at /api/v1/cardiotwin. Every route is authenticated (same `get_current_user` dependency as the rest
of ClinCase). Predictions are stateless: nothing about the submitted patient is persisted — only a
SHA-256 of the input and the model provenance are logged, mirroring OncoTwin's audit conventions.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.cardiotwin import CARDIOTWIN_VERSION
from app.cardiotwin.features import LeakageError, RecordValidationError
from app.cardiotwin.model import (
    EVALUATION_PATH,
    SAFETY_NOTICE,
    SCENARIOS_PATH,
    CardioModel,
    ModelArtifactError,
    load_json_artifact,
    load_model,
)
from app.cardiotwin.schema import (
    FEATURES,
    GROUP_LABELS,
    SOURCE_DATASET,
    VESSEL_NAMES,
    CounterfactualRequest,
    PredictRequest,
    SensitivityRequest,
)
from app.oncotwin.observability import METRICS

log = structlog.get_logger()
router = APIRouter(prefix="/cardiotwin", tags=["cardiotwin"])


def _model_or_503() -> CardioModel:
    try:
        return load_model()
    except ModelArtifactError as e:
        raise HTTPException(503, str(e)) from e


def _invalid(e: Exception) -> HTTPException:
    problems = getattr(e, "problems", [str(e)])
    return HTTPException(422, {"error": type(e).__name__, "problems": problems})


@router.get("/overview")
async def overview(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    m = _model_or_503()
    return {
        "name": "CardioTwin",
        "tagline": "Cardiovascular risk visualization and vessel-level prediction",
        "cardiotwin_version": CARDIOTWIN_VERSION,
        "model": m.version_info(),
        "headline_metrics": {t: m.targets[t]["cv_summary"] for t in ("CAD", "LAD", "LCX", "RCA")},
        "vessels": VESSEL_NAMES,
        "dataset": SOURCE_DATASET,
        "safety_notice": SAFETY_NOTICE,
        "terminology": {
            "cad": "Predicted CAD probability (angiographic CAD label in the training data)",
            "vessel": "Estimated vessel-level stenosis probability (>=50% narrowing label)",
            "not_claimed": [
                "lesion location, length or morphology",
                "heart-attack or mortality risk",
                "a diagnosis",
            ],
        },
    }


@router.get("/features")
async def features(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "groups": [{"id": g, "label": lbl} for g, lbl in GROUP_LABELS.items()],
        "features": [f.to_public() for f in FEATURES],
    }


@router.get("/scenarios")
async def scenarios(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    data = load_json_artifact(SCENARIOS_PATH)
    if data is None:
        raise HTTPException(
            503, "CardioTwin scenarios not generated — run `python -m app.cardiotwin.training`."
        )
    return data


@router.post("/predict")
async def predict(
    req: PredictRequest, _: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    m = _model_or_503()
    t0 = time.perf_counter()
    try:
        res = m.predict(req.features, scenario_id=req.scenario_id)
    except (RecordValidationError, LeakageError) as e:
        METRICS.inc("cardiotwin_predictions_total", outcome="rejected")
        raise _invalid(e) from e
    METRICS.inc(
        "cardiotwin_predictions_total",
        outcome="ok",
        representativeness=res["representativeness"]["status"],
    )
    METRICS.observe_ms("cardiotwin_predict_ms", (time.perf_counter() - t0) * 1000)
    log.info(
        "cardiotwin.predict",
        input_sha256=res["provenance"]["input_sha256"],
        model_version=m.version,
        artifact_sha256=m.sha256,
        representativeness=res["representativeness"]["status"],
    )
    return res


@router.post("/counterfactual")
async def counterfactual(
    req: CounterfactualRequest, _: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    m = _model_or_503()
    try:
        res = m.counterfactual(req.features, req.perturbations)
    except (RecordValidationError, LeakageError) as e:
        raise _invalid(e) from e
    METRICS.inc("cardiotwin_counterfactuals_total")
    return res


@router.post("/sensitivity")
async def sensitivity(
    req: SensitivityRequest, _: dict[str, Any] = Depends(get_current_user)
) -> dict[str, Any]:
    m = _model_or_503()
    try:
        return m.sensitivity(req.features, req.feature, req.points)
    except (RecordValidationError, LeakageError) as e:
        raise _invalid(e) from e


@router.get("/model")
async def model_card(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return _model_or_503().card()


@router.get("/evaluation")
async def evaluation(_: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    _model_or_503()
    data = load_json_artifact(EVALUATION_PATH)
    if data is None:
        raise HTTPException(
            503, "CardioTwin evaluation report missing — run `python -m app.cardiotwin.training`."
        )
    return data
