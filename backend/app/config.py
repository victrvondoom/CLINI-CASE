"""Application configuration loaded from environment variables.

Single source of truth for all runtime config. Import `settings` everywhere
config is needed. Never read `os.environ` directly outside this module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used to detect dev defaults that must be rotated in production.
# Production deploys MUST override JWT_SECRET via env (or AWS Secrets Manager
# wired into env). The startup validator below fails-fast if a non-dev
# environment ships with this sentinel — preventing forgeable JWTs in prod.
_DEV_JWT_SECRET_SENTINEL = "clincase-dev-secret-change-in-prod-via-env-CmDbYVQrV3"

# .env lives at the repo root (one level above backend/). Resolve absolutely
# so we work regardless of where uvicorn / pytest / make is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"

# Pydantic-settings reads `.env` into the Settings object only — it does NOT
# export keys into os.environ. boto3, however, reads AWS_* purely from the
# process environment. Bridge the two so the same `.env` works for both.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM provider ----------------------------------------------------
    LLM_PROVIDER: Literal["anthropic", "openrouter", "bedrock"] = "openrouter"

    # Anthropic direct
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # OpenRouter (development-time choice; Anthropic-compatible models)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-sonnet-4.6"

    # Bedrock (used on May 6)
    AWS_REGION: str = "ap-south-1"
    BEDROCK_MODEL_ID: str = "apac.anthropic.claude-sonnet-4-6-20251022-v1:0"
    BEDROCK_HAIKU_MODEL_ID: str = "apac.anthropic.claude-haiku-4-5-20251001-v1:0"
    BEDROCK_GUARDRAIL_ID: str = ""
    BEDROCK_GUARDRAIL_VERSION: str = "DRAFT"
    BEDROCK_KB_ID: str = ""
    # S3 bucket where payer policy PDFs are stored for Bedrock KB ingestion.
    # Format: clincase-policies-{accountid}-aps1
    POLICIES_S3_BUCKET: str = ""
    # Bedrock KB data source ID (created when you set up the KB in the console).
    # Required to call start_ingestion_job.
    BEDROCK_KB_DATA_SOURCE_ID: str = ""

    # --- Database --------------------------------------------------------
    DATABASE_URL: str = "postgresql://clincase:clincase@localhost:5432/clincase"

    # --- Redis (multi-replica SSE pub/sub) -------------------------------
    # Empty → in-process pub/sub backend (single-replica dev / hackathon).
    # Set on production deploys with > 1 API replica to fan SSE events
    # across replicas. See `app/streaming.py` for the backend protocol.
    REDIS_URL: str = ""

    # --- Embeddings ------------------------------------------------------
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- App -------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Environment + safety enforcement --------------------------------
    # Setting ENVIRONMENT to anything other than "dev" forces all secrets
    # (JWT_SECRET, DEMO_USER_PASSWORD) to be overridden via env. Pattern is
    # standard for SOC 2 attestable systems — no dev defaults in prod.
    ENVIRONMENT: Literal["dev", "staging", "production"] = "dev"

    # --- Auth (JWT) ------------------------------------------------------
    # MUST be overridden in staging/production via env (or AWS Secrets
    # Manager wired into env). The model_validator below fails-fast if a
    # non-dev environment ships with the sentinel default.
    JWT_SECRET: str = _DEV_JWT_SECRET_SENTINEL
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days for demo convenience

    # --- Demo / seed users -----------------------------------------------
    # Bootstraps three demo users (admin/reviewer/coordinator) on first
    # startup so the live demo always works. MUST be overridden in
    # staging/production. The model_validator below enforces this.
    DEMO_USER_PASSWORD: str = "clincase2026"

    # --- Flags -----------------------------------------------------------
    USE_BEDROCK_KB: bool = False
    SEED_ON_BOOT: bool = False

    # --- MCP server ------------------------------------------------------
    # Optional shared-secret bearer token for /mcp. If empty, the endpoint
    # is open (hackathon / demo mode). In production this is set via AWS
    # Secrets Manager.
    MCP_AUTH_TOKEN: str = ""

    # --- GenAI Gateway (governed Bedrock entry point) --------------------
    # Default ON. Set to false ONLY for tests / local dev where you want
    # to bypass per-tenant quota / audit-log writes. The gateway wraps
    # whatever LLM client the factory builds, enforcing per-tenant model
    # allowlist + 24h rolling token + USD caps + content-safety pre-check
    # + audit row in llm_invocations. See app/llm/gateway.py.
    GENAI_GATEWAY_ENABLED: bool = True

    # --- Cognizant TriZetto AI Gateway (Aug 2025; MCP-native) ------------
    # When TRIZETTO_GATEWAY_URL is empty, the in-process mock receiver
    # handles `/api/v1/integrations/trizetto/submit` so the demo always
    # works end-to-end. Setting the URL switches to live Gateway calls.
    TRIZETTO_GATEWAY_URL: str = ""
    TRIZETTO_GATEWAY_TOKEN: str = ""

    # --- Amazon Q Business (alternative to Bedrock KB for policy retrieval)
    # Empty AMAZON_Q_APPLICATION_ID → Bedrock KB stays the policy source.
    # Set USE_AMAZON_Q=true to route policy retrieval through Q Business.
    USE_AMAZON_Q: bool = False
    AMAZON_Q_APPLICATION_ID: str = ""
    AMAZON_Q_INDEX_ID: str = ""
    AMAZON_Q_REGION: str = "us-east-1"

    # --- HITL gate -------------------------------------------------------
    # If the Necessity Reasoner's overall_confidence is below this threshold,
    # the LangGraph DAG pauses at the review_gate node — the case is
    # surfaced to the Reviewer queue and a clinician's verdict is required.
    # Per CMS-0057-F § IV.C and state AI-denial laws (CA SB 1120, TX, IL).
    # Lowered to 0.0 for the demo so the full 7-agent DAG always runs
    # end-to-end. In production this is set to 0.75 via env var and
    # low-confidence cases route to the Reviewer queue via review_gate.
    HITL_CONFIDENCE_THRESHOLD: float = 0.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- Production safety guards ---------------------------------------
    # These run at Settings() instantiation time (i.e. before the app
    # boots). If a staging/production deploy ships with a dev default, we
    # raise immediately rather than silently issuing forgeable JWTs or
    # accepting a known demo password.
    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT in ("staging", "production"):
            if self.JWT_SECRET == _DEV_JWT_SECRET_SENTINEL:
                raise RuntimeError(
                    f"FATAL: ENVIRONMENT={self.ENVIRONMENT} but JWT_SECRET is the "
                    "dev default. Set JWT_SECRET via env (or AWS Secrets Manager) "
                    "to a >= 32-char random value before booting."
                )
            if len(self.JWT_SECRET) < 32:
                raise RuntimeError(
                    f"FATAL: ENVIRONMENT={self.ENVIRONMENT} but JWT_SECRET is "
                    f"{len(self.JWT_SECRET)} chars. Minimum 32 chars required."
                )
            if self.DEMO_USER_PASSWORD == "clincase2026":
                raise RuntimeError(
                    f"FATAL: ENVIRONMENT={self.ENVIRONMENT} but DEMO_USER_PASSWORD "
                    "is the public demo default. Override via env before booting."
                )
        return self


settings = Settings()
