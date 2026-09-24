# ClinCase — AWS Bedrock Migration Runbook

**Owner:** vsrupeshkumar (ClinCase)
**Target environment:** your AWS account, region `ap-south-1` (Mumbai) — fallback `us-east-1`
**Window:** one working day
**Author:** vsrupeshkumar
**Status:** Ready to execute · **Version:** 1.0

---

## 0. TL;DR — What this runbook achieves

ClinCase was developed against the Anthropic API via OpenRouter so we could iterate
without waiting on AWS provisioning. This runbook flips the LLM provider to **AWS
Bedrock Claude Sonnet 4.6**, swaps the in-memory policy corpus for a **Bedrock
Knowledge Base** backed by **OpenSearch Serverless**, and wraps every prompt
boundary with a **Bedrock Guardrail** that redacts PHI before any token leaves
our VPC. After this runbook, the same 7-agent LangGraph DAG runs entirely
inside AWS — no third-party LLM call, no PHI egress.

Total time budget: **4 hours** (incl. verification + rollback drill).
Critical-path time: **2.5 hours**.

| Phase | Duration | Owner | Exit criterion |
|------:|---------:|-------|----------------|
| 1. Account + IAM bootstrap                       | 25m | S.P.   | `aws sts get-caller-identity` returns the engineering role |
| 2. Bedrock model access                           | 15m | S.P.   | `bedrock:InvokeModel` returns 200 for `anthropic.claude-sonnet-4-20250620-v1:0` |
| 3. Provider swap (`LLM_PROVIDER=bedrock`)         | 20m | S.P.   | `/llm/ping` returns 200 with `provider=bedrock` and a Sonnet response |
| 4. Knowledge Base — vector store + ingestion      | 60m | A.S.   | Console shows status `READY`; `RetrieveAndGenerate` returns top-5 sections |
| 5. Bedrock Guardrails (PHI redaction)             | 30m | M.K.   | A test prompt containing "SSN 123-45-6789" returns the masked variant |
| 6. End-to-end demo replay                         | 30m | full team | All three demo paths run green with backend-only AWS calls |
| 7. Rollback drill                                 | 20m | S.P.   | Flip back to OpenRouter via env var in <60 seconds |

---

## 1. Pre-flight checks (do this BEFORE you sit down at the AWS workstation)

### 1.1 Confirmations
- [ ] The AWS account is provisioned and you have the **Engineering** role ARN
- [ ] Region is `ap-south-1` (Mumbai). If Bedrock is not yet enabled in `ap-south-1`, fall back to `us-east-1` and update `AWS_REGION` in `.env` accordingly. (Bedrock Claude Sonnet 4.6 is GA in `us-east-1`, GA in `ap-south-1` for 4.6 as of Q2 2026.)
- [ ] Local AWS CLI v2 installed: `aws --version` ≥ `2.15.0`
- [ ] Local Python venv has `boto3>=1.35` (already pinned in `backend/pyproject.toml`)
- [ ] You have the demo seed cohort (108 cases) in the local Postgres — running locally is fine for Day-1 demo; we do **NOT** need to migrate the DB to RDS today
- [ ] Have the OpenRouter `.env` line **commented out, not deleted** — we want to be able to flip back in <60s if Bedrock has an outage during the demo

### 1.2 Secrets you'll need
- AWS account ID
- Engineering role ARN
- Bedrock model ID (default: `anthropic.claude-sonnet-4-20250620-v1:0`)
- S3 bucket name for KB documents (we'll create: `clincase-kb-policies-<accountId>`)
- OpenSearch Serverless collection ARN (we'll create: `clincase-kb`)

### 1.3 Files modified by this runbook
| File | Change |
|------|--------|
| `.env`                                          | Add `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_KB_ID`, `BEDROCK_GUARDRAIL_ID`. Flip `LLM_PROVIDER=bedrock` |
| `backend/app/llm/bedrock_client.py`             | Already implemented; verify it loads |
| `backend/app/llm/factory.py`                    | Already routes by `LLM_PROVIDER` env var |
| `backend/app/agents/policy_retriever.py`        | Add `BedrockKnowledgeBaseRetriever` path (gated by env var) |

---

## 2. Phase 1 — Account + IAM bootstrap (25 min)

### 2.1 Configure CLI

```bash
aws configure sso --profile clincase-eng
# When prompted:
#   SSO start URL: <your SSO start URL>
#   SSO region: ap-south-1
#   Account: <your AWS account ID>
#   Role: Engineering
#   Default region: ap-south-1
#   Output format: json

aws sso login --profile clincase-eng
export AWS_PROFILE=clincase-eng
export AWS_REGION=ap-south-1
aws sts get-caller-identity
```

**Acceptance:** `Arn` field contains `Engineering` and the expected account ID.

### 2.2 Create the ClinCase execution role

> The Engineering SSO role is for humans. The app needs its own IAM role with
> least privilege so we can hand the same role to ECS Fargate when we deploy
> for production. Today, we'll use it via temporary credentials on the laptop.

Save as `ops/aws/clincase-app-role-trust.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ecs-tasks.amazonaws.com" },
      "Action": "sts:AssumeRole"
    },
    {
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::<ACCOUNT_ID>:root" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Save as `ops/aws/clincase-app-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:Retrieve",
        "bedrock:RetrieveAndGenerate",
        "bedrock:ApplyGuardrail"
      ],
      "Resource": [
        "arn:aws:bedrock:ap-south-1::foundation-model/anthropic.claude-sonnet-4-20250620-v1:0",
        "arn:aws:bedrock:ap-south-1:<ACCOUNT_ID>:knowledge-base/*",
        "arn:aws:bedrock:ap-south-1:<ACCOUNT_ID>:guardrail/*"
      ]
    },
    {
      "Sid": "S3KBSource",
      "Effect": "Allow",
      "Action": [ "s3:GetObject", "s3:ListBucket" ],
      "Resource": [
        "arn:aws:s3:::clincase-kb-policies-<ACCOUNT_ID>",
        "arn:aws:s3:::clincase-kb-policies-<ACCOUNT_ID>/*"
      ]
    },
    {
      "Sid": "Logs",
      "Effect": "Allow",
      "Action": [ "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents" ],
      "Resource": "arn:aws:logs:ap-south-1:<ACCOUNT_ID>:log-group:/aws/clincase/*"
    }
  ]
}
```

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" ops/aws/clincase-app-*.json

aws iam create-role \
  --role-name clincase-app \
  --assume-role-policy-document file://ops/aws/clincase-app-role-trust.json

aws iam put-role-policy \
  --role-name clincase-app \
  --policy-name clincase-app-inline \
  --policy-document file://ops/aws/clincase-app-policy.json
```

**Acceptance:**
```bash
aws iam get-role --role-name clincase-app --query 'Role.Arn'
# Returns: "arn:aws:iam::<ACCOUNT_ID>:role/clincase-app"
```

---

## 3. Phase 2 — Bedrock model access (15 min)

### 3.1 Request access to Claude Sonnet 4.6

Console → **Amazon Bedrock** → **Model access** → request access to:
- Anthropic Claude Sonnet 4.6 (`anthropic.claude-sonnet-4-20250620-v1:0`)
- Anthropic Claude Haiku 4 (`anthropic.claude-haiku-4-20250514-v1:0`) — fallback for cost-sensitive paths
- Amazon Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`) — for KB

Approval is normally instant for new accounts. Wait for **Status: Access granted** on all three.

### 3.2 Sanity-test InvokeModel

```bash
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-sonnet-4-20250620-v1:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":50,"messages":[{"role":"user","content":"Say hello in 5 words."}]}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/bedrock-out.json && cat /tmp/bedrock-out.json
```

**Acceptance:** JSON response with `"type": "message"` and a 5-word greeting in `content[0].text`.

---

## 4. Phase 3 — Provider swap (20 min)

### 4.1 Update `.env`

```bash
# .env additions
AWS_REGION=ap-south-1
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250620-v1:0
# Keep OPENROUTER_API_KEY commented for fast rollback
# OPENROUTER_API_KEY=sk-or-v1-...
```

### 4.2 Verify the existing BedrockClient

The repo already ships `backend/app/llm/bedrock_client.py` with the Converse API
implementation. Confirm it imports cleanly:

```bash
cd backend && .venv/Scripts/python.exe -c "from app.llm.factory import get_llm_client; c = get_llm_client(); print(type(c).__name__)"
```

**Acceptance:** prints `BedrockClient`.

### 4.3 Hit the `/llm/ping` route end-to-end

```bash
# Restart backend (in another terminal)
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000

# In a fresh terminal:
curl -s http://localhost:8000/llm/ping | jq .
```

**Acceptance:**
```json
{
  "provider": "bedrock",
  "model_id": "anthropic.claude-sonnet-4-20250620-v1:0",
  "ok": true,
  "sample_text": "...",
  "input_tokens": 12,
  "output_tokens": 18
}
```

### 4.4 Run a real case through the LangGraph DAG

```bash
# Submit the canned demo case and watch the SSE stream
curl -X POST http://localhost:8000/cases \
  -H "Authorization: Bearer $(./scripts/login.sh admin)" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/case_alpha.json | jq -r '.id' | tee /tmp/case.id

curl -N "http://localhost:8000/cases/$(cat /tmp/case.id)/stream?token=..."
```

**Acceptance:** The SSE stream emits `clinical_extractor` → `policy_retriever`
→ `necessity_reasoner` → `decision_composer` events, each with non-zero
token usage and a `model_id` of `anthropic.claude-sonnet-4-20250620-v1:0`.
Final verdict matches what the same case produced under OpenRouter.

---

## 5. Phase 4 — Knowledge Base (60 min)

> **Why a real KB?** The in-memory `policies.json` works for 21 entries.
> A real payer in production has **thousands** of CPB pages. Bedrock KBs
> give us auto-chunking, embedding, vector search, and citation extraction
> without us writing a retriever. This is the single biggest "AWS-native"
> signal in the demo and the natural answer to the question
> *"How does this scale beyond your seeded corpus?"*

### 5.1 Create S3 bucket + upload policy PDFs

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="clincase-kb-policies-$ACCOUNT_ID"

aws s3 mb "s3://$BUCKET" --region ap-south-1
aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Upload our 21 policy excerpts as Markdown (one file per policy)
.venv/Scripts/python.exe scripts/policies_to_markdown.py \
  --in backend/app/data/policies.json \
  --out /tmp/policy-md
aws s3 sync /tmp/policy-md "s3://$BUCKET/policies/"
```

> If `scripts/policies_to_markdown.py` doesn't exist yet, ship a 30-line script
> that emits one `<payer>_<policy_id>.md` per entry with frontmatter
> (`payer:`, `policy_id:`, `title:`) so we get section-level chunking.

### 5.2 Create OpenSearch Serverless collection

Console path: **OpenSearch Service** → **Serverless** → **Create collection**
- Name: `clincase-kb`
- Type: **Vector search**
- Encryption: AWS-owned key (demo) or KMS key (production)
- Network: **Public** for demo; **VPC-only** for production
- Data access policy: grant `aoss:*` to `clincase-app` role and the Bedrock
  service principal `bedrock.amazonaws.com`

Wait ~3 min for collection to become **Active**.

### 5.3 Create Bedrock Knowledge Base

Console path: **Bedrock** → **Knowledge bases** → **Create knowledge base**
- Name: `clincase-policies`
- IAM role: **Create new** (Bedrock will scaffold `AmazonBedrockExecutionRoleForKnowledgeBase_*`)
- Data source:
  - Type: S3
  - Bucket: `s3://clincase-kb-policies-<ACCOUNT_ID>/policies/`
  - Chunking: Default — 300 tokens, 20% overlap
  - Parsing: Default
- Embedding model: **Amazon Titan Embeddings V2** (1024 dims)
- Vector store: **Amazon OpenSearch Serverless** → pick existing `clincase-kb` collection
- Click **Create knowledge base**

Wait ~5 min for status `Available`. Then **Sync** the data source.
Wait another ~3 min for sync `Complete` (you should see `21 documents indexed`).

### 5.4 Test retrieval from the console

In the KB detail view, **Test knowledge base** with:
> *"What are the LVEF requirements for trastuzumab in HER2-positive breast cancer?"*

**Acceptance:** Top result is Aetna 0048 § Initial Authorization Criteria with
LVEF ≥ 50% and the 60-day window highlighted.

### 5.5 Wire the KB into the Policy Retriever

Add to `.env`:
```bash
BEDROCK_KB_ID=<from console, e.g., XYZ12345>
USE_BEDROCK_KB=true
```

Edit `backend/app/agents/policy_retriever.py`. Add a guarded code path
right above the existing `_candidate_sections` filter:

```python
if settings.USE_BEDROCK_KB:
    kb = boto3.client("bedrock-agent-runtime", region_name=settings.AWS_REGION)
    rsp = kb.retrieve(
        knowledgeBaseId=settings.BEDROCK_KB_ID,
        retrievalQuery={"text": f"{snap.requested_treatment.name} for {snap.primary_diagnosis.description}, payer: {state.payer_id}"},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )
    excerpts = [
        PolicyExcerpt(
            payer_id=state.payer_id,
            policy_id=r["metadata"].get("policy_id", "unknown"),
            policy_title=r["metadata"].get("title", "Untitled"),
            section_heading=r["metadata"].get("section", "Body"),
            excerpt_text=r["content"]["text"],
            source_url=r["location"]["s3Location"]["uri"],
            relevance_score=r["score"],
        )
        for r in rsp["retrievalResults"]
    ]
    state.policy_excerpts = excerpts
    return state
```

**Acceptance:** Re-running a case shows `policy_excerpts[].source_url` start
with `s3://clincase-kb-policies-...`, and the `policy_retriever` SSE event
includes `retrieval_source: "bedrock_kb"`.

---

## 6. Phase 5 — Bedrock Guardrails for PHI (30 min)

### 6.1 Create the guardrail

Console path: **Bedrock** → **Guardrails** → **Create guardrail**
- Name: `clincase-phi-redact`
- Sensitive information filters → **PII**:
  - **Mask** (do not block): `NAME`, `EMAIL`, `PHONE`, `ADDRESS`, `US_SOCIAL_SECURITY_NUMBER`, `US_BANK_ACCOUNT_NUMBER`, `CREDIT_DEBIT_CARD_NUMBER`, `DRIVER_ID`, `DATE_OF_BIRTH`
  - Custom regex (Mask): `\bMRN[:\s]?\d{6,10}\b` for medical record numbers
- Denied topics: none (we want medical content; this is a clinical tool)
- Word filters: profanity off
- Content filters: HATE/INSULT/SEXUAL/VIOLENCE = `HIGH` (treat as safety not as moderation)
- **Save** and **Create version 1**

### 6.2 Wire the guardrail into the BedrockClient

Add to `.env`:
```bash
BEDROCK_GUARDRAIL_ID=<from console>
BEDROCK_GUARDRAIL_VERSION=1
```

In `backend/app/llm/bedrock_client.py`, in the `complete()` method:

```python
extra_kwargs = {}
if settings.BEDROCK_GUARDRAIL_ID:
    extra_kwargs["guardrailConfig"] = {
        "guardrailIdentifier": settings.BEDROCK_GUARDRAIL_ID,
        "guardrailVersion": settings.BEDROCK_GUARDRAIL_VERSION,
        "trace": "enabled",
    }
response = self._client.converse(
    modelId=self._model_id,
    messages=msgs,
    system=[{"text": system}],
    inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    **extra_kwargs,
)
```

### 6.3 Test PHI redaction

Send a physician note with seeded PHI:
```bash
curl -X POST http://localhost:8000/cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(./scripts/login.sh admin)" \
  -d '{
    "payer_id": "aetna",
    "patient_initials": "S.D.",
    "physician_note": "Patient John Smith, DOB 1972-03-14, MRN 1234567, SSN 123-45-6789, requesting trastuzumab.",
    "fhir_bundle": {"resourceType":"Bundle","entry":[]},
    "requested_treatment_name": "trastuzumab",
    "requested_j_code": "J9355"
  }' | jq .
```

**Acceptance:**
- The `clinical_extractor` SSE event's `output.physician_note_redacted` contains
  `Patient {NAME}, DOB {DATE_OF_BIRTH}, MRN {MRN}, SSN {US_SOCIAL_SECURITY_NUMBER}`
- The downstream agents never see the original PHI
- The `cases.physician_note` row in Postgres still stores the original (PHI
  is sanitised at the LLM boundary, not at the input boundary, by design — the
  EHR-of-record is the source of truth)

---

## 7. Phase 6 — End-to-end demo replay (30 min)

Run all three demo paths:

1. **Path A — Approval (60s):** Submit a clean trastuzumab case under Aetna.
   - Expected: APPROVE verdict in <12s, all 4 agents emit traces, citations
     resolve to KB excerpts, no PHI in any LLM call.
2. **Path B — Denial → Appeal (90s):** Submit a denial-bound osimertinib case
   (EGFR-negative).
   - Expected: DENY verdict, conditional edge fires Appeals Drafter, the
     drafted appeal cites NCCN.
3. **Path C — Multi-payer arbitration (60s):** Open `/cases/:id/compare` on a
   trastuzumab case.
   - Expected: 4 payer cards (Aetna, UHC, BCBS, Anthem) populate from real KB
     retrieval per payer; arbitration recommendation surfaces.

**Acceptance:** All three paths run green with `LLM_PROVIDER=bedrock`,
`USE_BEDROCK_KB=true`, and `BEDROCK_GUARDRAIL_ID` set. Total wall-time across
all 3 paths ≤ 4 minutes.

---

## 8. Phase 7 — Rollback drill (20 min)

> **Why drill this?** If Bedrock has any incident in `ap-south-1` during a
> live session, we need to flip back to OpenRouter
> in under 60 seconds. **Rehearse this drill at least once.**

### 8.1 The rollback steps (commit to muscle memory)

```bash
# Step 1: Edit .env (one line):
sed -i 's/^LLM_PROVIDER=bedrock/LLM_PROVIDER=openrouter/' .env
# Step 2: Uncomment OPENROUTER_API_KEY in .env
sed -i 's/^# OPENROUTER_API_KEY=/OPENROUTER_API_KEY=/' .env
# Step 3: Restart uvicorn (auto-reloads on .env change with --reload, but bounce to be safe)
pkill -f "uvicorn app.main"; (cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000 &)
# Step 4: Verify
curl -s http://localhost:8000/llm/ping | jq -r '.provider'
# Acceptance: prints "openrouter"
```

### 8.2 Forward-roll back to Bedrock

After the incident clears, reverse the sed commands. Total time: <60s.

---

## 9. Production deployment notes (beyond a single-account demo)

These are **out of scope for a single-account demo deployment**. They are
documented here so the path to real production is explicit.

### 9.1 ECS Fargate cluster
- Task definition uses `clincase-app` execution role (already created in §2.2).
- Containers: `backend` (FastAPI on 8000), `frontend` (nginx on 80 serving the Vite build).
- Load balancer: ALB with TLS via ACM cert, listener forwards `/api/*` to backend, `/` to frontend.

### 9.2 RDS Aurora PostgreSQL Serverless v2
- Replaces local Docker Postgres.
- pgvector extension for embedding storage if we ever bring retrieval in-house.
- Multi-AZ; encrypted at rest with KMS; daily snapshots, 35-day PITR window.

### 9.3 Per-tenant guardrails
- A demo deployment uses one guardrail across all orgs.
- In production, each `organization_id` gets its own guardrail version so
  enterprise customers can plug in their own redaction policies.

### 9.4 VPC + PrivateLink for Bedrock
- All Bedrock traffic over `com.amazonaws.<region>.bedrock-runtime` PrivateLink endpoint.
- Zero egress to the public internet from the application VPC.

### 9.5 CloudWatch + X-Ray
- Already-instrumented `trace_agent` writes to CloudWatch Logs and X-Ray segments
  via `aws-xray-sdk` (drop-in patch).
- Per-agent latency p50/p95/p99 dashboards.

### 9.6 Cost controls
- Bedrock spend alarm at $50/day for the demo account.
- Guardrail-blocked requests don't bill for output tokens — verify this on the
  first invoice.

---

## 10. Sign-off

- [ ] Phase 1–6 acceptance criteria all met (initials + timestamp): __________
- [ ] Rollback drill successful (<60s total): __________
- [ ] All three demo paths recorded as backup video: __________
- [ ] `.env` committed to AWS Secrets Manager (NOT to git): __________

**Engineer:**                              **Date:**
**Reviewer:**                              **Date:**

---

*This runbook is checked into the repo at `ops/aws/MIGRATION_RUNBOOK.md`. If
you change a step, version-bump and PR.*
