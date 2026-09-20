"""Amazon Q Business integration — alternative knowledge backend for policy retrieval.

Amazon Q Business is AWS's enterprise RAG platform (announced 2024 GA, expanded
2025–2026 with first-party connectors for SharePoint, Confluence, Salesforce,
S3, etc.). Unlike Bedrock Knowledge Base — which the team owns end-to-end —
Q Business is the AWS-managed enterprise-search story Cognizant's customers
already have provisioned for their Microsoft 365 / SharePoint / Confluence
policy libraries.

This adapter lets ClinCase query Q Business as an OPTIONAL alternative to
Bedrock KB for the policy_retriever agent. The toggle is one env var:

    USE_AMAZON_Q=true          → Q Business backend
    USE_AMAZON_Q=false (default) → Bedrock KB backend (current production)

Why this matters strategically:

  • Many TriZetto customers' payer policy docs already live in M365/Confluence.
    Building "yet another vector index" is a non-starter procurement-wise.
    Q Business plugs into their existing knowledge corpus directly.

  • ClinCase's policy_retriever schema is unchanged — same `PolicyExcerpt`
    Pydantic model on output. The retrieval *backend* is the only thing
    that swaps. This is what "pluggable" means in production.

  • Per the Availity 2025 case study (publicly documented), Q + Bedrock is
    a known-good combo for healthcare payer ops. ClinCase slots into that
    same pattern.

NOTE on the May 15, 2026 Q Developer EOS: this module is for **Q Business**
(retrieval), NOT Q Developer (IDE assistant). Q Business is unaffected by
the Q Developer signup freeze.
"""
from app.integrations.amazon_q.client import (
    AmazonQClient,
    QRetrievedSnippet,
)

__all__ = ["AmazonQClient", "QRetrievedSnippet"]
