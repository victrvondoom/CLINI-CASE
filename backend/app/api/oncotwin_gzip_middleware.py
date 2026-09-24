"""Gzip for OncoTwin API responses only.

OncoTwin intelligence / FHIR / research payloads are 50–400 KB of JSON and compress 5–8×. Compression is
scoped to /api/v1/oncotwin/* because Starlette's GZipMiddleware buffers the whole response, which would
break ClinCase's server-sent-event streams elsewhere in the app; no OncoTwin route streams.

Observed motivation: on a Windows dev machine with HTTP-inspecting antivirus, loopback responses larger
than ~64 KB were intermittently reset after ~19 s (reproduced even with Python's stdlib http.server), which
left twin pages hanging. Compressed payloads stay well under that size.
"""
from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

ONCOTWIN_PREFIX = "/api/v1/oncotwin/"


class OncoTwinGZipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 1024) -> None:
        self.app = app
        self.gzip = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(ONCOTWIN_PREFIX):
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)
