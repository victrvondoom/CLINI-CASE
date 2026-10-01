"""Explicit HTTP boundary, network URL or embedded independent ASGI simulator."""

from typing import Any, cast

import httpx

from app.config import settings
from app.interop.receiver import LOCAL_TOKEN, app


async def exchange(
    org: str, correlation: str, bundle: dict[str, Any] | None = None, destination: str = "clinical"
) -> dict[str, Any]:
    url = settings.INTEROP_RECEIVER_URL
    headers = {
        "X-Tenant": org,
        "X-Receiver-Token": settings.INTEROP_RECEIVER_TOKEN or LOCAL_TOKEN,
    }
    transport = None if url else httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        base_url=url or "http://independent-receiver",
        transport=transport,
        timeout=10,
        headers=headers,
    ) as client:
        response = (
            await client.post(
                "/lab/fhir" if destination == "lab" else "/fhir",
                json={"correlation_id": correlation, "bundle": bundle},
            )
            if bundle is not None
            else await client.get("/exchanges/" + correlation)
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


async def withdraw(org: str, correlation: str) -> dict[str, Any]:
    async with httpx.AsyncClient(
        base_url=settings.INTEROP_RECEIVER_URL or "http://independent-receiver",
        transport=None if settings.INTEROP_RECEIVER_URL else httpx.ASGITransport(app=app),
        timeout=10,
        headers={
            "X-Tenant": org,
            "X-Receiver-Token": settings.INTEROP_RECEIVER_TOKEN or LOCAL_TOKEN,
        },
    ) as client:
        response = await client.post("/exchanges/" + correlation + "/withdraw")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
