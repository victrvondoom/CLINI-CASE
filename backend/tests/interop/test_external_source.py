"""Offline tests for the external Water Quality Portal curation path (no network).

Rows below are hand-written TEST rows that follow the WQP column schema; they are not WQP data.
"""

import json
import sys
from pathlib import Path

import pytest

from app.interop import service
from app.interop.models import Job, Source

sys.path.insert(0, str(Path(__file__).parents[2]))
from scripts import fetch_external_water_data as fx  # noqa: E402

RESULT_COLUMNS = [
    "OrganizationIdentifier", "OrganizationFormalName", "ActivityIdentifier",
    "ActivityStartDate", "ActivityStartTime/Time", "ActivityStartTime/TimeZoneCode",
    "MonitoringLocationIdentifier", "ResultIdentifier", "ResultDetectionConditionText",
    "CharacteristicName", "ResultSampleFractionText", "ResultMeasureValue",
    "ResultMeasure/MeasureUnitCode", "MeasureQualifierCode", "ResultStatusIdentifier",
    "ResultAnalyticalMethod/MethodIdentifier", "ResultAnalyticalMethod/MethodName",
    "LaboratoryName", "AnalysisStartDate", "ProviderName",
]  # fmt: skip
STATION = {
    "MonitoringLocationIdentifier": "TEST-SITE-1",
    "MonitoringLocationName": "TEST CREEK NEAR NOWHERE",
    "MonitoringLocationTypeName": "Stream",
}


def row(rid, fraction, value="1.5", unit="ug/l", **extra):
    base = dict.fromkeys(RESULT_COLUMNS, "")
    base.update(
        OrganizationIdentifier="TEST-ORG",
        OrganizationFormalName="TEST Org",
        ActivityIdentifier="act-" + rid,
        ActivityStartDate="2023-01-09",
        **{"ActivityStartTime/Time": "12:43:00", "ActivityStartTime/TimeZoneCode": "PST"},
        MonitoringLocationIdentifier="TEST-SITE-1",
        ResultIdentifier=rid,
        CharacteristicName="Arsenic",
        ResultSampleFractionText=fraction,
        ResultMeasureValue=value,
        **{"ResultMeasure/MeasureUnitCode": unit},
        ResultStatusIdentifier="Preliminary",
        **{
            "ResultAnalyticalMethod/MethodIdentifier": "M1",
            "ResultAnalyticalMethod/MethodName": "TEST method",
        },
        LaboratoryName="TEST Lab",
        AnalysisStartDate="2023-02-16",
        ProviderName="TEST",
    )
    base.update(extra)
    return base


ROWS = [
    row("R1", "Dissolved", "0.67"),
    row("R2", "Total", "4.0"),
    row("R3", "Unfiltered", "9"),  # no explicit fraction -> skipped
    row("R4", "Total", "", **{"ResultDetectionConditionText": "Not Detected"}),
    row("R5", "Dissolved", "2", unit="mg/l"),
    row("R6", "Total", "3", MeasureQualifierCode="U"),
]
URLS = {"result": "https://example.invalid/r", "station": "https://example.invalid/s"}
DOC = fx.curate(
    RESULT_COLUMNS, ROWS, list(STATION), STATION,
    retrieval_date="2026-10-02T00:00:00Z", urls=URLS, limit=10,
)  # fmt: skip
DOC_MAPPED = {
    "sample_no", "sample_location", "water_source", "sample_time", "lab", "units", "kind",
    "collector", "report_reference", "method", "report_time",
}  # fmt: skip
VALUE_FIELDS = {"arsenic_dissolved", "total_arsenic"}


async def analyze(payload):
    job = Job(
        organization_id="org-a",
        source=Source(source_system=fx.SOURCE_NAME, original_record_id="x", payload=payload),
    )
    await service.analyze(job, False)
    return job


def test_explicit_fraction_rule_and_skips():
    by_id = {r["source_row"]["ResultIdentifier"]: r["gateway_source"]["payload"] for r in DOC["records"]}
    assert set(by_id) == {"R1", "R2"}
    assert by_id["R1"]["arsenic_dissolved"] == 0.67 and "total_arsenic" not in by_id["R1"]
    assert by_id["R2"]["total_arsenic"] == 4.0 and "arsenic_dissolved" not in by_id["R2"]
    assert all("arsenic" not in p for p in by_id.values())
    assert len(DOC["skipped_before_limit"]) == 4


def test_provenance_and_transformations_present():
    rec = DOC["records"][0]
    assert rec["source"] == fx.SOURCE_NAME and "USGS" in rec["publisher"]
    assert rec["retrieval_date"] == "2026-10-02T00:00:00Z"
    assert rec["query_urls"] == URLS
    assert rec["source_schema"]["result_columns"] == RESULT_COLUMNS
    assert rec["source_row"] == ROWS[0]  # verbatim original
    assert rec["station_row"] == STATION
    for t in rec["transformations"]:
        assert set(t) == {"source_field", "target_field", "rule"} and t["rule"]
    targets = {t["target_field"] for t in rec["transformations"]}
    assert set(rec["gateway_source"]["payload"]) == targets
    assert rec["gateway_source"]["payload"]["sample_time"] == "2023-01-09T20:43:00Z"
    assert rec["gateway_source"]["synthetic"] is False


def test_unknown_timezone_is_skipped_not_guessed():
    doc = fx.curate(
        RESULT_COLUMNS, [row("R9", "Total", **{"ActivityStartTime/TimeZoneCode": "XYZ"})],
        list(STATION), STATION, retrieval_date="t", urls=URLS, limit=5,
    )  # fmt: skip
    assert doc["records"] == []


def test_query_is_deterministic():
    assert fx.result_params("S", "01-01-2023", "12-31-2023")["characteristicName"] == "Arsenic"
    assert fx.query_url("Result", fx.result_params("S", "a", "b")) == fx.query_url(
        "Result", fx.result_params("S", "a", "b")
    )


async def check_gateway(payload):
    job = await analyze(payload)
    assert all(m.target for m in job.mappings if m.source_field in DOC_MAPPED | VALUE_FIELDS)
    value = next(m for m in job.mappings if m.source_field in VALUE_FIELDS)
    assert value.confidence == 1 and value.concept in {"dissolved_arsenic", "total_arsenic"}
    unresolved = {m.source_field for m in job.mappings if m.target is None}
    # Documented: WQP context fields have no gateway target and remain unresolved.
    assert unresolved <= {"result_status", "monitoring_location_identifier", "provider_name"}
    for m in job.mappings:
        m.decision = "accepted" if m.target else "rejected"
        m.reviewer = "test-reviewer"
    record = service.normalize(job)
    assert record.sample.analyte == value.concept
    return record


@pytest.mark.parametrize("index", [0, 1])
async def test_flattened_keys_map_deterministically_and_normalize(index):
    record = await check_gateway(DOC["records"][index]["gateway_source"]["payload"])
    assert record.sample.unit == "ug/L" and record.sample.kind == "stream"


async def test_committed_sample_if_any_passes_same_checks():
    folder = Path(__file__).parents[2] / "data/interop/external"
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        for rec in json.loads(path.read_text())["records"]:
            assert rec["source_row"] and rec["transformations"] and rec["retrieval_date"]
            await check_gateway(rec["gateway_source"]["payload"])
