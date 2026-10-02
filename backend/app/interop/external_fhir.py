"""Optional third-party FHIR R4 interoperability check.

Submits the generated (synthetic) Bundle to a FHIR server this project does not control, reads it
back, and compares the semantic evidence fields. It proves one additional external FHIR R4 path; it
does NOT prove OAH conformance, and a generic server does not validate OAH profiles.

Safety rules enforced here, not by callers:
- synthetic data only (a public server retains what it receives);
- the server URL is server configuration, never request input (no SSRF);
- every failure is a fixed category, never exception text; the local workflow never depends on this.
"""

from __future__ import annotations

import asyncio
import ssl
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.onehealth import fhir

FHIR_JSON = "application/fhir+json"
READ_ATTEMPTS = 3  # reads only: the POST is never retried, so a retry cannot create a duplicate
COMPARED = ("sample", "history", "waterbody_name", "source_observation_id", "provenance")


class ExternalFhirRefusedError(ValueError):
    """The check was refused before any network call (non-synthetic data or no server configured)."""


def _ssl_context(system_trust: bool) -> ssl.SSLContext | bool:
    if not system_trust:
        return True
    try:
        import truststore
    except ImportError:
        return True  # fall back to the default store; verification stays on
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def make_client(timeout: float, system_trust: bool) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout, verify=_ssl_context(system_trust), follow_redirects=False
    )


def _record(base_url: str, **fields: Any) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "endpoint": base_url,
        "resource_type": "Bundle",
        "resource_id": None,
        "request": None,
        "retrieval": None,
        "semantic": None,
        "detail": "",
        "checked_at": datetime.now(UTC).isoformat(),
        "scope_note": (
            "Additional external FHIR R4 interoperability path. A generic FHIR server does not "
            "validate OAH profiles; this is not an OAH conformance result."
        ),
        **fields,
    }


def _compare(sent: dict[str, Any], received: dict[str, Any]) -> dict[str, Any]:
    original = fhir.read_evidence(sent)
    returned = fhir.read_evidence(received)
    rows = [{"field": f, "preserved": original.get(f) == returned.get(f)} for f in COMPARED]
    return {
        "fields": rows,
        "fields_preserved": sum(r["preserved"] for r in rows),
        "fields_total": len(rows),
    }


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


async def exchange(
    bundle: dict[str, Any],
    *,
    synthetic: bool,
    base_url: str,
    request_timeout_s: float,
    system_trust: bool = False,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """POST the Bundle, GET it back, compare. Returns a result record; I/O failures never raise."""
    if not synthetic:
        raise ExternalFhirRefusedError("Only synthetic Bundles may be sent to a public FHIR server")
    if not base_url.lower().startswith(("http://", "https://")):
        raise ExternalFhirRefusedError("No third-party FHIR server is configured")
    base = base_url.rstrip("/")
    http = client or make_client(request_timeout_s, system_trust)
    headers = {"Content-Type": FHIR_JSON, "Accept": FHIR_JSON}
    try:
        started = time.perf_counter()
        try:
            created = await http.post(f"{base}/Bundle", json=bundle, headers=headers)
        except httpx.TimeoutException:
            return _record(base, detail="The server did not answer in time")
        except httpx.HTTPError:
            return _record(base, detail="The server could not be reached")
        request = {"status_code": created.status_code, "elapsed_ms": _ms(started)}
        if created.status_code not in (200, 201):
            return _record(
                base,
                status="rejected",
                request=request,
                detail=f"The server refused the Bundle (HTTP {created.status_code})",
            )
        try:
            resource_id = str(created.json().get("id", ""))
        except ValueError:
            resource_id = ""
        if not resource_id or "/" in resource_id:
            return _record(base, status="failed", request=request, detail="The server returned no usable resource id")

        received: httpx.Response | None = None
        read_started = time.perf_counter()
        for attempt in range(READ_ATTEMPTS):
            try:
                received = await http.get(f"{base}/Bundle/{resource_id}", headers={"Accept": FHIR_JSON})
            except httpx.HTTPError:
                received = None
            if received is not None and received.status_code == 200:
                break
            if attempt < READ_ATTEMPTS - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # short backoff for read-after-write lag
        known = {"resource_id": resource_id, "request": request}
        if received is None or received.status_code != 200:
            code = received.status_code if received is not None else "no response"
            return _record(base, status="failed", detail=f"The Bundle could not be read back (HTTP {code})", **known)
        retrieval = {"status_code": 200, "elapsed_ms": _ms(read_started)}
        try:
            semantic = _compare(bundle, received.json())
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            return _record(
                base,
                status="failed",
                retrieval=retrieval,
                detail="The returned Bundle could not be read as CLINI-CASE evidence",
                **known,
            )
        passed = semantic["fields_preserved"] == semantic["fields_total"]
        return _record(
            base,
            status="passed" if passed else "failed",
            retrieval=retrieval,
            semantic=semantic,
            detail="All compared evidence fields were preserved" if passed else "One or more evidence fields changed",
            **known,
        )
    finally:
        if client is None:
            await http.aclose()
