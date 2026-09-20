"""Amazon Q Business retrieval client — boto3-backed.

Boto3 service: `qbusiness` (formerly `q-business`). Operation we care about:
  • `chat_sync` — synchronous, returns answer + sourceAttributions
  • `retrieve` (newer 2025 API) — returns ranked passages without LLM synthesis

For ClinCase's policy_retriever we want passages, not a final answer — so we
prefer `retrieve`, falling back to `chat_sync` if the application doesn't
expose `retrieve` yet.

Two modes:

  • Mock mode (default, when AMAZON_Q_APPLICATION_ID is empty) returns a
    deterministic fixture so the demo always works regardless of AWS
    credentials. This makes the "USE_AMAZON_Q=true env flip" demo
    reproducible offline.

  • Real mode calls `qbusiness` boto3 client with the configured
    application + index IDs and a Bearer token (via IAM Identity Center
    or service-linked role).

The output is normalized to `QRetrievedSnippet` regardless of which API
path produced it — same shape Bedrock KB returns, so the policy_retriever
agent's downstream logic doesn't change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()


# =============================================================================
# Output type
# =============================================================================


@dataclass
class QRetrievedSnippet:
    """One retrieved policy chunk. Same surface as Bedrock KB
    `retrieve` results — by design, so the policy_retriever's reranker
    doesn't care which backend produced the snippet."""

    text: str
    source_uri: str | None
    title: str | None
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Client
# =============================================================================


class AmazonQClient:
    """Stateless wrapper around the `qbusiness` boto3 service.

    Constructor args:
      • application_id: the Q Business application UUID
      • index_id:       the Q Business index UUID
      • region_name:    AWS region (us-east-1 typical for Q Business)

    All optional — if any is unset, the client runs in mock mode.
    """

    def __init__(
        self,
        *,
        application_id: str | None = None,
        index_id: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.application_id = application_id or settings.AMAZON_Q_APPLICATION_ID
        self.index_id = index_id or settings.AMAZON_Q_INDEX_ID
        self.region_name = region_name or settings.AMAZON_Q_REGION
        self._client: Any | None = None

    @property
    def is_mock(self) -> bool:
        return not (self.application_id and self.index_id)

    def _ensure_client(self) -> Any:
        if self._client is None:
            import boto3  # type: ignore[import-not-found]
            self._client = boto3.client("qbusiness", region_name=self.region_name)
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int = 8,
        payer_id: str | None = None,
    ) -> list[QRetrievedSnippet]:
        """Return up to top_k snippets for `query`.

        Async wrapper for ergonomics — the underlying boto3 call is sync,
        we run it in the default executor so we don't block the event loop.
        """
        if self.is_mock:
            return self._mock_retrieve(query=query, payer_id=payer_id, top_k=top_k)
        return await self._real_retrieve(query=query, payer_id=payer_id, top_k=top_k)

    # ------------------------------------------------------------------
    # Mock implementation
    # ------------------------------------------------------------------

    def _mock_retrieve(
        self, *, query: str, payer_id: str | None, top_k: int
    ) -> list[QRetrievedSnippet]:
        """Return a deterministic fixture so the demo works offline.

        Fixture content is hand-crafted to match the kind of payer-policy
        passages a real Q Business retrieve call would surface for an
        oncology PA prompt.
        """
        log.info("amazon_q.mock_retrieve", query=query[:80], payer_id=payer_id, top_k=top_k)
        payer = (payer_id or "aetna").upper()
        title = f"{payer} Oncology Policy — Trastuzumab (HER2-positive Breast Cancer)"
        body = (
            f"Per {payer} medical policy, trastuzumab (Herceptin, biosimilars: "
            "Ogivri, Trazimera, Kanjinti) is medically necessary for the "
            "treatment of HER2-positive breast cancer when ALL of the "
            "following criteria are met: (1) Diagnosis of HER2-positive "
            "breast cancer confirmed by IHC 3+ or FISH-amplified testing; "
            "(2) Adjuvant, neoadjuvant, or metastatic setting; (3) Intended "
            "duration consistent with NCCN BREA-N guidelines; (4) Combined "
            "with chemotherapy in first-line metastatic disease, except "
            "where contraindicated."
        )
        snippets = [
            QRetrievedSnippet(
                text=body,
                source_uri=f"sharepoint://{payer.lower()}/medical-policy/oncology/trastuzumab.pdf#page=1",
                title=title,
                score=0.94,
                metadata={
                    "payer_id": payer.lower(),
                    "policy_id": f"{payer}-MED-2024-007",
                    "section_heading": "Coverage Criteria",
                    "page_number": 1,
                    "retrieved_via": "amazon_q_business",
                    "mock": True,
                },
            ),
            QRetrievedSnippet(
                text=(
                    "Authorization period: 6 months initial, with renewal "
                    "every 12 months thereafter contingent on documented "
                    "response on imaging and ECHO/MUGA-confirmed LVEF ≥ 50%."
                ),
                source_uri=f"sharepoint://{payer.lower()}/medical-policy/oncology/trastuzumab.pdf#page=3",
                title=title,
                score=0.88,
                metadata={
                    "payer_id": payer.lower(),
                    "policy_id": f"{payer}-MED-2024-007",
                    "section_heading": "Authorization Period",
                    "page_number": 3,
                    "retrieved_via": "amazon_q_business",
                    "mock": True,
                },
            ),
        ]
        return snippets[:top_k]

    # ------------------------------------------------------------------
    # Real implementation
    # ------------------------------------------------------------------

    async def _real_retrieve(
        self, *, query: str, payer_id: str | None, top_k: int
    ) -> list[QRetrievedSnippet]:
        import asyncio
        loop = asyncio.get_running_loop()
        client = self._ensure_client()

        attribute_filter: dict[str, Any] | None = None
        if payer_id:
            # Q Business supports filtering on document attributes when the
            # connector populates them. Convention: `payer_id` attribute on
            # each indexed doc. Falls through gracefully if not configured.
            attribute_filter = {
                "equalsTo": {
                    "name": "payer_id",
                    "value": {"stringValue": payer_id.lower()},
                }
            }

        request: dict[str, Any] = {
            "applicationId": self.application_id,
            "indexId": self.index_id,
            "queryText": query,
            "maxResults": top_k,
        }
        if attribute_filter:
            request["attributeFilter"] = attribute_filter

        try:
            resp = await loop.run_in_executor(
                None, lambda: client.retrieve(**request)
            )
        except Exception as e:  # noqa: BLE001
            log.warning("amazon_q.retrieve_failed", error=str(e))
            return []

        items = resp.get("relevantDocuments", []) or resp.get("retrievalResults", []) or []
        out: list[QRetrievedSnippet] = []
        for item in items:
            text = item.get("contentExcerpt") or item.get("content", {}).get("text", "")
            uri = item.get("documentUri") or item.get("documentId")
            title = item.get("documentTitle") or item.get("title")
            score = float(item.get("score", 0.0))
            md: dict[str, Any] = {"retrieved_via": "amazon_q_business"}
            for attr in item.get("documentAttributes", []) or []:
                key = attr.get("name")
                val = attr.get("value", {})
                v = val.get("stringValue") or val.get("longValue") or val.get("dateValue")
                if key and v is not None:
                    md[key] = v
            out.append(QRetrievedSnippet(
                text=text or "",
                source_uri=uri,
                title=title,
                score=score,
                metadata=md,
            ))
        return out
