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
        j = None

        async def call(path, **extra):
            nonlocal j
            body = {} if j is None else {"job_id": j["id"], "expected_version": j["version"]}
            for _attempt in range(4):
                response = await client.post("/api/v1/interop/" + path, json={**body, **extra})
                if response.status_code != 429:
                    break
                await asyncio.sleep(min(60, max(1, int(response.headers.get("Retry-After", "1")))))
            response.raise_for_status()
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
        return_response = await client.post(
            "/api/v1/interop/return", json={"job_id": j["id"], "expected_version": j["version"]}
        )
        return_response.raise_for_status()
        returned = return_response.json()
        j = returned["job"]
        assert returned["lab_acknowledgement"]["status"] == "delivered"
        assert returned["lab_representation"]["sample"] == j["normalized"]
        valid_metrics = j["metrics"]
        broken = copy.deepcopy(j["bundle"])
        o = next(
            e["resource"] for e in broken["entry"] if e["resource"]["resourceType"] == "Observation"
        )
        o["valueQuantity"].update(code="ppm", unit="ppm")
        await call("validate", bundle=broken)
        assert not j["validation"]["valid"]
        print(
            json.dumps(
                {
                    "correlation_id": j["id"],
                    "receiver_mode": meta.json()["receiver_mode"],
                    "ai_status": j["ai_status"],
                    "valid_package_metrics": valid_metrics,
                    "failure_metrics": j["metrics"],
                    "roundtrip_fields_preserved": returned["validation"]["roundtrip"][
                        "fields_preserved"
                    ],
                    "resources_acknowledged": j["transfers"][-1]["acknowledgement"][
                        "resources_acknowledged"
                    ],
                    "lab_return_status": returned["lab_acknowledgement"]["status"],
                    "roundtrip_sample_preserved": returned["lab_representation"]["sample"]
                    == j["normalized"],
                    "broken_bundle_rejected": not j["validation"]["valid"],
                    "events": len(j["events"]),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="reviewer@clincase.health")
    parser.add_argument("--password", default=os.getenv("DEMO_USER_PASSWORD", "clincase2026"))
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--fixtures", action="store_true")
    args = parser.parse_args()
    asyncio.run(fixtures() if args.fixtures else demo(args))
