"""Repeatable synthetic gateway demo against a running authenticated backend.
From backend: python scripts/interop_demo.py --base-url http://127.0.0.1:8000
Use --fixtures to regenerate synthetic valid/broken package examples offline.
"""

import argparse
import asyncio
import copy
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx


async def fixtures():
    from app.interop import service
    from app.interop.models import Job, Source
    from app.onehealth import fhir

    directory = Path(__file__).resolve().parents[1] / "data/interop"
    j = Job(
        id="ig-synthetic-fixture",
        organization_id="synthetic-fixtures",
        source=Source(
            source_system="SYNTHETIC Lab A",
            original_record_id="SYN-AS-001",
            payload=json.loads((directory / "environmental.json").read_text()),
            synthetic=True,
        ),
    )
    await service.analyze(j, False)
    for m in j.mappings:
        m.decision = "accepted" if m.target else "rejected"
        m.reviewer = "SYNTHETIC mapping reviewer"
        if m.source_field == "arsenic":
            m.concept = "total_arsenic"
    bundle = fhir.export(service.normalize(j))
    assert service.validate(bundle)["valid"]
    (directory / "valid-fhir.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    broken = copy.deepcopy(bundle)
    result = next(
        e["resource"] for e in broken["entry"] if e["resource"]["resourceType"] == "Observation"
    )
    result["valueQuantity"].update(code="ppm", unit="ppm")
    assert not service.validate(broken)["valid"]
    (directory / "broken-fhir.json").write_text(json.dumps(broken, indent=2), encoding="utf-8")
    print("Synthetic valid and invalid FHIR fixtures generated")


async def demo(args):
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        response = await client.post(
            "/api/v1/auth/login", json={"email": args.email, "password": args.password}
        )
        response.raise_for_status()
        client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
        meta = await client.get("/api/v1/interop/meta")
        meta.raise_for_status()
        receiver_mode = meta.json()["receiver_mode"]
        if receiver_mode != "HTTP network":
            raise RuntimeError(
                "Network demo requires the independent receiver over HTTP; "
                f"backend reported {receiver_mode!r}"
            )
        j = None
        latencies = []

        async def call(path, **extra):
            nonlocal j
            started = time.perf_counter()
            body = {} if j is None else {"job_id": j["id"], "expected_version": j["version"]}
            for _attempt in range(4):
                response = await client.post("/api/v1/interop/" + path, json={**body, **extra})
                if response.status_code != 429:
                    break
                await asyncio.sleep(min(60, max(1, int(response.headers.get("Retry-After", "1")))))
            response.raise_for_status()
            latencies.append(
                {"operation": path, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}
            )
            j = response.json()
            return j

        await call("demo")
        await call("analyze-schema", use_ai=args.ai)
        for m in list(j["mappings"]):
            await call(
                "mappings/" + j["id"] + ("/approve" if m["target"] else "/reject"),
                source_field=m["source_field"],
                concept="total_arsenic" if m["source_field"] == "arsenic" else None,
            )
        await call("generate-fhir")
        assert j["validation"]["valid"]
        await call("transfer")
        assert j["transfers"][-1]["status"] == "delivered", j["transfers"][-1]
        started = time.perf_counter()
        return_response = await client.post(
            "/api/v1/interop/return", json={"job_id": j["id"], "expected_version": j["version"]}
        )
        return_response.raise_for_status()
        returned = return_response.json()
        latencies.append(
            {"operation": "return", "duration_ms": round((time.perf_counter() - started) * 1000, 2)}
        )
        j = returned["job"]
        assert returned["lab_acknowledgement"]["status"] == "delivered"
        assert returned["roundtrip"]["status"] == "passed"
        assert returned["roundtrip"]["resource_ids_reassigned"] is True
        assert returned["lab_representation"]["sample"] == j["normalized"]
        valid_metrics = j["metrics"]
        initial_id = j["id"]
        initial_ai_status = j["ai_status"]
        acknowledged = j["transfers"][-1]["acknowledgement"]["resources_acknowledged"]
        broken = copy.deepcopy(j["bundle"])
        o = next(
            e["resource"] for e in broken["entry"] if e["resource"]["resourceType"] == "Observation"
        )
        o["valueQuantity"].update(code="ppm", unit="ppm")
        await call("challenge-receiver", bundle=broken)
        assert not j["validation"]["valid"]
        assert j["transfers"][-1]["status"] == "rejected", j["transfers"][-1]
        failure_metrics = j["metrics"]
        integrity = await client.post(
            f"/api/v1/interop/passport/{j['id']}/verify-integrity", json={}
        )
        integrity.raise_for_status()
        assert integrity.json()["valid"]
        exported = await client.get(f"/api/v1/interop/passport/{j['id']}/export")
        exported.raise_for_status()
        from app.onehealth.passport import verify_portable

        assert verify_portable(exported.json())["valid"]
        output = Path(__file__).resolve().parents[1] / ".cache/track7"
        output.mkdir(parents=True, exist_ok=True)
        (output / "evidence-passport.json").write_text(
            json.dumps(exported.json(), indent=2), encoding="utf-8"
        )
        # Return to the valid artifact before entering the existing review workflow.
        await call("validate", bundle=j["bundle"])
        await call("bind-evidence")
        bound_id = j["exposure_id"]
        response = await client.get("/api/v1/onehealth/exposures/" + bound_id)
        response.raise_for_status()
        record = response.json()

        async def clinical(action, **extra):
            nonlocal record
            response = await client.post(
                f"/api/v1/onehealth/exposures/{record['id']}/{action}",
                json={"expected_version": record["version"], **extra},
            )
            response.raise_for_status()
            record = response.json()

        await clinical("verify", note="SYNTHETIC demo operator verified the synthetic report")
        patients = await client.get("/api/v1/onehealth/patients")
        patients.raise_for_status()
        pid = next(p["id"] for p in patients.json()["patients"] if p["synthetic"])
        stamp = datetime.now(UTC)
        history = {
            "patient_id": pid,
            "consent_reference": "SYN-CONSENT-MIRA-HOUSEHOLD",
            "consent_recorded": True,
            "route": "drinking",
            "pathway_confirmed": True,
            "pathway_evidence": "SYNTHETIC household interview: documented outlet use",
            "treatment_context": "SYNTHETIC no point-of-use treatment reported",
            "started_on": (stamp - timedelta(days=365)).isoformat(),
            "ended_on": (stamp - timedelta(minutes=1)).isoformat(),
        }
        await clinical("link", history=history)
        await clinical(
            "review",
            decision="reviewed",
            note="SYNTHETIC exposure context reviewed; no disease inference",
        )
        assert record["assessment"]["eligible_for_review"]
        await call("generate-fhir")
        await call("transfer")
        assert j["transfers"][-1]["status"] == "delivered"
        retest_sample = {
            **record["sample"],
            "sample_id": "SYN-RETEST-" + j["id"][-8:],
            "report_reference": "SYN-RETEST-REPORT",
            "value": 8,
            "collected_at": (stamp - timedelta(hours=2)).isoformat(),
            "reported_at": (stamp - timedelta(hours=1)).isoformat(),
        }
        await clinical(
            "retest",
            note="SYNTHETIC new retest closes original environmental task",
            sample=retest_sample,
        )
        retest_id = record["id"]
        assert not record["lab_verified"] and record["history"] is None
        await clinical("verify", note="SYNTHETIC retest report independently verified")
        await clinical("link", history=history)
        await clinical(
            "review", decision="reviewed", note="SYNTHETIC retest context reviewed independently"
        )
        response = await client.post(
            "/api/v1/interop/from-evidence",
            json={"exposure_id": record["id"], "expected_version": record["version"]},
        )
        response.raise_for_status()
        j = response.json()
        await call("transfer")
        assert j["transfers"][-1]["status"] == "delivered"
        journey = await client.get(f"/api/v1/onehealth/exposures/{retest_id}/journey")
        journey.raise_for_status()
        retest_passport = await client.get(f"/api/v1/onehealth/exposures/{retest_id}/passport")
        retest_passport.raise_for_status()
        assert verify_portable(retest_passport.json())["valid"]
        (output / "retest-passport.json").write_text(
            json.dumps(retest_passport.json(), indent=2), encoding="utf-8"
        )
        results = {
            "correlation_id": initial_id,
            "retest_gateway_id": j["id"],
            "receiver_mode": receiver_mode,
            "ai_status": initial_ai_status,
            "valid_package_metrics": valid_metrics,
            "failure_metrics": failure_metrics,
            "roundtrip_fields_preserved": returned["validation"]["roundtrip"]["fields_preserved"],
            "roundtrip_fields_total": returned["validation"]["roundtrip"]["fields_total"],
            "roundtrip_status": returned["roundtrip"]["status"],
            "resource_ids_reassigned": returned["roundtrip"]["resource_ids_reassigned"],
            "resources_acknowledged": acknowledged,
            "lab_return_status": returned["lab_acknowledgement"]["status"],
            "roundtrip_sample_preserved": returned["lab_representation"]["sample"]
            == returned["job"]["normalized"],
            "broken_bundle_rejected_by_receiver": True,
            "passport_integrity": integrity.json(),
            "passport_offline_verified": True,
            "bound_exposure_id": bound_id,
            "retest_id": retest_id,
            "retest_change_ug_l": journey.json()["retest_comparison"]["change_ug_l"],
            "retest_exchange_status": j["transfers"][-1]["status"],
            "mapping_mode": "AI-assisted path" if args.ai else "Deterministic reference path",
            "latencies": latencies,
            "retest_events": len(j["events"]),
        }
        (output / "runtime-metrics.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="reviewer@clincase.health")
    parser.add_argument("--password", default=os.getenv("DEMO_USER_PASSWORD", ""))
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    asyncio.run(fixtures() if args.fixtures else demo(args))
