"""Outbox publisher worker — drains `event_outbox` to the configured message bus.

Run as a sidecar process or as a background task in the worker tier:
    .venv/Scripts/python.exe -m app.events.publisher

Targets (selected via env `EVENT_BUS_TARGET`):
  • "log"         — print to stdout (default; for dev / hackathon)
  • "eventbridge" — publish to AWS EventBridge (apply-ready; enable on prod via env)
  • "kinesis"     — publish to AWS Kinesis Data Streams (apply-ready)
  • "kafka"       — publish to MSK / Confluent (TODO post-pilot)

Drain loop:
  1. Pull batch of pending events via SELECT FOR UPDATE SKIP LOCKED
  2. For each: render as CloudEvents 1.0; publish to bus
  3. Mark `published_at = NOW()` on success
  4. Mark `attempts++ + last_error` on failure (will retry next loop until attempts >= 5)
  5. Sleep `_DRAIN_INTERVAL_SECONDS`

Multiple replicas can run safely (SKIP LOCKED).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
from typing import Any

import structlog

from app.events.outbox import (
    mark_failed,
    mark_published,
    pending_events,
    to_cloudevent,
)

log = structlog.get_logger()

_DRAIN_INTERVAL_SECONDS = int(os.getenv("OUTBOX_DRAIN_INTERVAL_SECONDS", "5"))
_BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "100"))
_TARGET = os.getenv("EVENT_BUS_TARGET", "log").lower()


_shutdown = asyncio.Event()


# =============================================================================
# Publisher implementations
# =============================================================================


async def _publish_log(envelope: dict[str, Any]) -> None:
    """Default for dev / hackathon. Just logs the CloudEvent."""
    log.info("outbox.publish.log", event=envelope["type"], event_id=envelope["id"])


async def _publish_eventbridge(envelope: dict[str, Any]) -> None:
    """Publish to AWS EventBridge as a custom event source.

    Requires:
      EVENTBRIDGE_BUS_NAME=clincase-domain-events
      EVENTBRIDGE_SOURCE=clincase
    """
    import aioboto3  # type: ignore[import-not-found]
    bus_name = os.getenv("EVENTBRIDGE_BUS_NAME", "clincase-domain-events")
    source = os.getenv("EVENTBRIDGE_SOURCE", "clincase")
    region = os.getenv("AWS_REGION", "ap-south-1")
    session = aioboto3.Session(region_name=region)
    async with session.client("events") as eb:
        await eb.put_events(Entries=[{
            "Source": source,
            "DetailType": envelope["type"],
            "Detail": json.dumps(envelope),
            "EventBusName": bus_name,
        }])


async def _publish_kinesis(envelope: dict[str, Any]) -> None:
    """Publish to a Kinesis Data Stream. Partition key = aggregate_id.

    Requires:
      KINESIS_STREAM_NAME=clincase-domain-events
    """
    import aioboto3  # type: ignore[import-not-found]
    stream = os.getenv("KINESIS_STREAM_NAME", "clincase-domain-events")
    region = os.getenv("AWS_REGION", "ap-south-1")
    partition_key = envelope.get("subject", envelope["id"])
    session = aioboto3.Session(region_name=region)
    async with session.client("kinesis") as k:
        await k.put_record(
            StreamName=stream,
            Data=json.dumps(envelope).encode("utf-8"),
            PartitionKey=partition_key,
        )


_PUBLISHERS = {
    "log": _publish_log,
    "eventbridge": _publish_eventbridge,
    "kinesis": _publish_kinesis,
}


# =============================================================================
# Drain loop
# =============================================================================


async def drain_once() -> int:
    """Drain a single batch. Returns count of events processed."""
    publisher = _PUBLISHERS.get(_TARGET, _publish_log)
    rows = await pending_events(batch_size=_BATCH_SIZE)
    if not rows:
        return 0

    processed = 0
    for row in rows:
        envelope = to_cloudevent(row)
        try:
            await publisher(envelope)
            await mark_published(row["id"])
            processed += 1
        except Exception as e:  # noqa: BLE001
            log.warning(
                "outbox.publish_failed",
                event_id=str(row["event_id"]),
                target=_TARGET,
                error=str(e)[:200],
            )
            await mark_failed(row["id"], str(e))
    return processed


async def main() -> None:
    log.info(
        "outbox.publisher.boot",
        target=_TARGET,
        drain_interval_s=_DRAIN_INTERVAL_SECONDS,
        batch_size=_BATCH_SIZE,
    )

    from app.db import db
    await db.connect()

    # Signal handling for graceful shutdown
    loop = asyncio.get_running_loop()
    def _stop() -> None:
        log.info("outbox.publisher.signal.shutdown")
        _shutdown.set()
    try:
        loop.add_signal_handler(signal.SIGTERM, _stop)
        loop.add_signal_handler(signal.SIGINT, _stop)
    except NotImplementedError:
        pass  # Windows asyncio

    while not _shutdown.is_set():
        try:
            n = await drain_once()
            if n:
                log.info("outbox.drained", count=n)
        except Exception as e:  # noqa: BLE001
            log.error("outbox.drain_error", error=str(e))

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_shutdown.wait(), timeout=_DRAIN_INTERVAL_SECONDS)

    await db.disconnect()
    log.info("outbox.publisher.exit")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    asyncio.run(main())
