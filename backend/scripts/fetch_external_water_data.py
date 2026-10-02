"""Fetch and curate a small Water Quality Portal arsenic sample for the Track 7 gateway.

Source: Water Quality Portal (National Water Quality Monitoring Council; USGS, EPA, and
contributing agencies), https://www.waterqualitydata.us. Nothing here trains a model or infers
health effects. See docs/track7/DATA_SOURCES.md.

Usage (network required; the test suite never runs this):

    python scripts/fetch_external_water_data.py --out /path/outside/repo/wqp_arsenic.json

Redistribution of raw WQP rows is NOT cleared for this repository, so the output is meant to be
generated locally and not committed. TLS verification is always on; behind a TLS-inspecting proxy
pass --ca-bundle PATH (or set SSL_CERT_FILE), or --system-trust (needs `truststore`).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

BASE = "https://www.waterqualitydata.us/data"
SOURCE_NAME = "Water Quality Portal (WQP)"
PUBLISHER = (
    "National Water Quality Monitoring Council; U.S. Geological Survey (USGS); "
    "U.S. Environmental Protection Agency (EPA)"
)
CITATION = (
    "Water Quality Portal. Washington (DC): National Water Quality Monitoring Council, "
    "United States Geological Survey (USGS), Environmental Protection Agency (EPA); 2021. "
    "https://doi.org/10.5066/P9QRKUVJ"
)
# Fixed, deterministic query. One USGS stream site (Arroyo Hondo near San Jose, CA).
DEFAULT_SITE = "USGS-11173200"
DEFAULT_START = "01-01-2023"
DEFAULT_END = "12-31-2023"
FRACTION_FIELD = {"Dissolved": "arsenic_dissolved", "Total": "total_arsenic"}
TZ_OFFSETS = {
    "UTC": 0, "GMT": 0, "EST": -5, "EDT": -4, "CST": -6, "CDT": -5,
    "MST": -7, "MDT": -6, "PST": -8, "PDT": -7, "AKST": -9, "AKDT": -8, "HST": -10,
}  # fmt: skip
KIND_MAP = {"Stream": "stream"}  # other WQP site types have no honest gateway equivalent here


class FetchError(RuntimeError):
    pass


def result_params(site: str, start: str, end: str) -> dict[str, str]:
    return {
        "siteid": site,
        "characteristicName": "Arsenic",
        "startDateLo": start,
        "startDateHi": end,
        "dataProfile": "narrowResult",
        "mimeType": "csv",
        "zip": "no",
        "sorted": "no",
    }


def station_params(site: str) -> dict[str, str]:
    return {"siteid": site, "mimeType": "csv", "zip": "no"}


def query_url(endpoint: str, params: dict[str, str]) -> str:
    return f"{BASE}/{endpoint}/search?{urlencode(params)}"


def parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return list(reader.fieldnames or []), list(reader)


def _utc_iso(date: str, time_text: str, tz: str) -> str | None:
    if tz not in TZ_OFFSETS or not date:
        return None
    clock = time_text or "00:00:00"
    local = datetime.fromisoformat(f"{date}T{clock}").replace(
        tzinfo=timezone(timedelta(hours=TZ_OFFSETS[tz]))
    )
    return local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def curate_row(
    row: dict[str, str], station: dict[str, str]
) -> tuple[dict[str, Any] | None, list[dict[str, str]], str | None]:
    """Return (flattened gateway object, transformations, skip_reason)."""
    fraction = row.get("ResultSampleFractionText", "")
    if row.get("CharacteristicName") != "Arsenic" or fraction not in FRACTION_FIELD:
        return None, [], "no explicit Dissolved/Total fraction"
    if row.get("MeasureQualifierCode") or row.get("ResultDetectionConditionText"):
        return None, [], "qualified or non-detect result; not flattened"
    try:
        value = float(row["ResultMeasureValue"])
    except (KeyError, ValueError):
        return None, [], "non-numeric result value"
    unit = row.get("ResultMeasure/MeasureUnitCode", "")
    if unit.lower() != "ug/l":
        return None, [], "unit is not ug/L"
    collected = _utc_iso(
        row.get("ActivityStartDate", ""),
        row.get("ActivityStartTime/Time", ""),
        row.get("ActivityStartTime/TimeZoneCode", ""),
    )
    if not collected:
        return None, [], "unknown time zone code"
    value_field = FRACTION_FIELD[fraction]
    name = station.get("MonitoringLocationName", "")
    t: list[dict[str, str]] = []

    def add(src: str, target: str, rule: str) -> None:
        t.append({"source_field": src, "target_field": target, "rule": rule})

    out: dict[str, Any] = {}
    out["sample_no"] = row["ResultIdentifier"]
    add("ResultIdentifier", "sample_no", "copied verbatim")
    out["sample_location"] = name
    add("Station.MonitoringLocationName", "sample_location", "copied verbatim")
    out["water_source"] = name
    add(
        "Station.MonitoringLocationName",
        "water_source",
        "monitoring location name reused as waterbody; WQP has no separate waterbody name",
    )
    out["sample_time"] = collected
    add(
        "ActivityStartDate+ActivityStartTime/Time+ActivityStartTime/TimeZoneCode",
        "sample_time",
        "local clock time converted to UTC using the fixed offset table TZ_OFFSETS",
    )
    out["lab"] = row.get("LaboratoryName") or None
    add("LaboratoryName", "lab", "copied verbatim")
    out[value_field] = value
    add(
        f"ResultMeasureValue (ResultSampleFractionText={fraction})",
        value_field,
        f"fraction '{fraction}' becomes the explicit qualifier in the field name; "
        "value parsed as float, not rescaled",
    )
    out["units"] = "ug/L"
    add("ResultMeasure/MeasureUnitCode", "units", "'ug/l' normalised to 'ug/L'; no conversion")
    kind = KIND_MAP.get(station.get("MonitoringLocationTypeName", ""))
    if kind:
        out["kind"] = kind
        add("Station.MonitoringLocationTypeName", "kind", "'Stream' -> 'stream'")
    out["collector"] = row.get("OrganizationFormalName") or None
    add(
        "OrganizationFormalName",
        "collector",
        "proxy: reporting organization, not a named sampler",
    )
    out["report_reference"] = "/".join(
        [row.get("OrganizationIdentifier", ""), row["ActivityIdentifier"], row["ResultIdentifier"]]
    )
    add(
        "OrganizationIdentifier+ActivityIdentifier+ResultIdentifier",
        "report_reference",
        "joined with '/'",
    )
    method = " ".join(
        x
        for x in (
            row.get("ResultAnalyticalMethod/MethodIdentifier", ""),
            row.get("ResultAnalyticalMethod/MethodName", ""),
        )
        if x
    )
    out["method"] = method or None
    add(
        "ResultAnalyticalMethod/MethodIdentifier+MethodName",
        "method",
        "joined with a space",
    )
    analysis = row.get("AnalysisStartDate", "")
    if analysis and analysis >= row.get("ActivityStartDate", ""):
        out["report_time"] = analysis + "T23:59:59Z"
        add(
            "AnalysisStartDate",
            "report_time",
            "proxy: WQP exposes no report-issue time; analysis start date at 23:59:59Z used and "
            "must be confirmed or rejected by a reviewer",
        )
    # Unmapped-by-design context: kept so a reviewer sees it; the gateway marks it unresolved.
    out["result_status"] = row.get("ResultStatusIdentifier") or None
    add("ResultStatusIdentifier", "result_status", "copied verbatim; no gateway target")
    out["monitoring_location_identifier"] = row.get("MonitoringLocationIdentifier")
    add(
        "MonitoringLocationIdentifier",
        "monitoring_location_identifier",
        "copied verbatim; no gateway target",
    )
    out["provider_name"] = row.get("ProviderName") or None
    add("ProviderName", "provider_name", "copied verbatim; no gateway target")
    return {k: v for k, v in out.items() if v is not None}, t, None


def curate(
    result_columns: list[str],
    rows: list[dict[str, str]],
    station_columns: list[str],
    station: dict[str, str],
    *,
    retrieval_date: str,
    urls: dict[str, str],
    limit: int,
) -> dict[str, Any]:
    ordered = sorted(
        rows,
        key=lambda r: (
            r.get("ActivityStartDate", ""),
            r.get("ActivityStartTime/Time", ""),
            r.get("ResultIdentifier", ""),
        ),
    )
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for row in ordered:
        if len(records) >= limit:
            break
        flat, transformations, reason = curate_row(row, station)
        if flat is None:
            skipped.append({"ResultIdentifier": row.get("ResultIdentifier", ""), "reason": reason or ""})
            continue
        records.append(
            {
                "source": SOURCE_NAME,
                "publisher": PUBLISHER,
                "query_urls": urls,
                "retrieval_date": retrieval_date,
                "source_schema": {"result_columns": result_columns, "station_columns": station_columns},
                "source_row": row,
                "station_row": station,
                "transformations": transformations,
                "gateway_source": {
                    "source_system": SOURCE_NAME,
                    "original_record_id": row["ResultIdentifier"],
                    "format": "json",
                    "payload": flat,
                    "synthetic": False,
                },
            }
        )
    return {
        "source": SOURCE_NAME,
        "publisher": PUBLISHER,
        "citation": CITATION,
        "retrieval_date": retrieval_date,
        "query_urls": urls,
        "limit": limit,
        "selection_rule": "rows sorted by (ActivityStartDate, time, ResultIdentifier); first "
        "`limit` rows with explicit Dissolved/Total fraction, numeric ug/L value, no qualifier",
        "rows_returned_by_source": len(rows),
        "skipped_before_limit": skipped,
        "records": records,
    }


def http_get(
    url: str, *, ca_bundle: str | None, system_trust: bool = False, retries: int = 4, timeout: float = 60.0) -> str:
    import httpx

    verify: Any = ca_bundle or os.environ.get("SSL_CERT_FILE") or True
    if system_trust:  # opt-in: verify against the OS trust store (TLS-inspecting proxies)
        import ssl

        import truststore

        verify = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(verify=verify, timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": "CLINI-CASE-track7-curation/1.0"})
            if response.status_code == 200:
                return response.text
            if response.status_code < 500 and response.status_code != 429:
                raise FetchError(f"HTTP {response.status_code} from {url}")
            last = FetchError(f"HTTP {response.status_code} from {url}")
        except httpx.HTTPError as exc:
            last = exc
        time.sleep(2**attempt)
    raise FetchError(f"Fetch failed after {retries} attempts: {type(last).__name__}: {last}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, help="output JSON path (keep outside the repository)")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--site", default=DEFAULT_SITE)
    p.add_argument("--start", default=DEFAULT_START, help="MM-DD-YYYY")
    p.add_argument("--end", default=DEFAULT_END, help="MM-DD-YYYY")
    p.add_argument("--retrieval-date", help="UTC ISO timestamp; default is now")
    p.add_argument("--ca-bundle", help="PEM bundle for TLS verification (never disabled)")
    p.add_argument(
        "--system-trust",
        action="store_true",
        help="verify against the OS trust store via the optional 'truststore' package",
    )
    a = p.parse_args(argv)
    if not 1 <= a.limit <= 25:
        p.error("--limit must be between 1 and 25")
    retrieved = a.retrieval_date or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    r_url = query_url("Result", result_params(a.site, a.start, a.end))
    s_url = query_url("Station", station_params(a.site))
    try:
        result_cols, rows = parse_csv(http_get(r_url, ca_bundle=a.ca_bundle, system_trust=a.system_trust))
        station_cols, stations = parse_csv(http_get(s_url, ca_bundle=a.ca_bundle, system_trust=a.system_trust))
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not stations:
        print("error: Station query returned no rows", file=sys.stderr)
        return 2
    doc = curate(
        result_cols, rows, station_cols, stations[0],
        retrieval_date=retrieved, urls={"result": r_url, "station": s_url}, limit=a.limit,
    )  # fmt: skip
    if not doc["records"]:
        print("error: no rows met the curation rules", file=sys.stderr)
        return 3
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {len(doc['records'])} records to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
