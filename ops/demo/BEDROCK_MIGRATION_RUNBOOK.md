# ClinCase — Bedrock Migration Runbook (May 6, 2026)

**Owner:** Danish A. G. (`agdanishr@gmail.com`)
**Run date:** May 6, 2026 (T-1 day)
**Estimated total time:** 3 hours including rollback test
**Critical risk:** If Bedrock fails AND OpenRouter is also unavailable, demo is dead. ALWAYS keep OpenRouter as the safety net.

---

## Pre-flight (run BEFORE leaving home for the venue)

### 1. Verify OpenRouter still works (your safety net)

```bash
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"
.venv/Scripts/python.exe -m scripts.smoke_test
# expect: SMOKE TEST: PASS
```

```bash
# verify a quick LLM call still works on OpenRouter
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | head -c 500
# expect: JSON with model list
```

### 2. Verify your AWS credentials

```bash
aws sts get-caller-identity
# expect: { "UserId": "...", "Account": "...", "Arn": "..." }
```

If this fails: **STOP. Do not proceed with migration.** Use OpenRouter for the demo and frame the story as "We're showing you on OpenRouter today; production runs on Bedrock with the same Claude Sonnet 4.6 weights — see the deployment ADR."

### 3. Verify Bedrock model access in `ap-south-1`

```bash
aws bedrock list-foundation-models --region ap-south-1 \
  --query "modelSummaries[?contains(modelId, 'sonnet-4-6')].modelId"
```

Expected output:
```
[
  "apac.anthropic.claude-sonnet-4-6-20251022-v1:0",
  "apac.anthropic.claude-haiku-4-5-20251001-v1:0"
]
```

If empty → **request model access** in the Bedrock console (takes ~10 minutes
for Anthropic models on the partner account; may already be pre-approved).

---

## Step-by-step migration (estimated 30 minutes)

### Step 1 — Update `.env`

```bash
# Backup current .env
cp "D:/xzashr.ai Files/clincase-workspace/ClinCase/.env" \
   "D:/xzashr.ai Files/clincase-workspace/ClinCase/.env.backup-$(date +%Y%m%d-%H%M%S)"

# Edit .env — change THIS LINE only:
# from: LLM_PROVIDER=openrouter
# to:   LLM_PROVIDER=bedrock
```

The Bedrock-specific values are already in `.env`:
```
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=apac.anthropic.claude-sonnet-4-6-20251022-v1:0
BEDROCK_HAIKU_MODEL_ID=apac.anthropic.claude-haiku-4-5-20251001-v1:0
```

### Step 2 — Set AWS credentials

Either:
```bash
aws configure
# enter Access Key ID, Secret Access Key, region=ap-south-1
```

Or add to `.env`:
```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

(Whichever is preferred per the partner account team.)

### Step 3 — Restart backend + worker

```bash
# Stop existing
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force }"
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { \$_.MainModule.FileName -like '*venv*' } | Stop-Process -Force"

# Start fresh
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log &
.venv/Scripts/python.exe -m app.workers.case_runner &
```

### Step 4 — Verify Bedrock works end-to-end

```bash
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"
.venv/Scripts/python.exe -m scripts.smoke_test
# expect: SMOKE TEST: PASS

# queue ONE test case
.venv/Scripts/python.exe -m scripts._demo_poll
# expect: case completes in ~90s (Bedrock is faster than OpenRouter for the
# same model in the same region) and verdict + citations are produced
```

If the test case completes successfully — **Bedrock migration is done. Demo path validated.**

---

## Rollback procedure (if Bedrock fails for any reason)

```bash
# Restore the backed-up .env
cp "D:/xzashr.ai Files/clincase-workspace/ClinCase/.env.backup-..." \
   "D:/xzashr.ai Files/clincase-workspace/ClinCase/.env"

# Restart services
# (same kill + start commands as Step 3 above)

# Verify OpenRouter is back
.venv/Scripts/python.exe -m scripts.smoke_test
```

**Rollback time: ~2 minutes.** No code changes needed — pure env-var flip.

---

## Common Bedrock failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel` | IAM role missing `bedrock:InvokeModel` | Add policy `AmazonBedrockReadOnly` + `AmazonBedrockFullAccess` to your IAM user |
| `ResourceNotFoundException` on the model_id | Model not enabled for your account | Enable Anthropic models in Bedrock console (takes ~10 min) |
| `ValidationException: model_id ... is not a valid model ID` | Region mismatch | Verify `AWS_REGION=ap-south-1` and model_id starts with `apac.anthropic.` |
| Throttling (429) | Hit on-demand limit | Either request a quota increase OR provision dedicated throughput (apply-ready Terraform in `ops/terraform/provisioned-throughput/`) |
| Sudden 500s after the migration | Bedrock Guardrails misconfigured | Set `BEDROCK_GUARDRAIL_ID=` (empty) in .env to disable guardrails for the demo |

---

## What changes in the demo when on Bedrock vs OpenRouter

| Aspect | OpenRouter | Bedrock |
|---|---|---|
| Latency per LLM call | 2–10 sec (highly variable) | 1–5 sec (more predictable) |
| Cost per case | ~$0.50–1.50 | ~$0.10–0.30 (no marketplace fee) |
| Visible in pitch | Generic "Claude Sonnet 4.6" | "AWS Bedrock + Claude Sonnet 4.6" — judges love this |
| Compliance posture | Public API | VPC-bound + Bedrock Guardrails + the partner-account audit logs |
| Failure mode | OpenRouter outage = no demo | AWS regional outage = no demo (extremely rare) |

---

## What to say in the pitch about the LLM provider

**On Bedrock (preferred):**
> *"ClinCase runs on AWS Bedrock with Claude Sonnet four-point-six — the same Bedrock + Claude + MCP stack the industry standardized on for the Anthropic partnership announced November fourth, twenty-twenty-five. Per-tenant Bedrock Guardrails mask PHI before any call leaves the VPC."*

**On OpenRouter (fallback):**
> *"Today we're demoing on OpenRouter for cost parity in the hackathon environment; production runs on AWS Bedrock with identical Claude Sonnet four-point-six weights. Our LLM provider abstraction in `app/llm/` makes the switch a single environment variable flip — see the deployment ADR."*

---

## Final check (do this in the venue, 30 min before stage)

```bash
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"
.venv/Scripts/python.exe -m scripts.smoke_test
echo "current LLM_PROVIDER:"; grep "^LLM_PROVIDER" "D:/xzashr.ai Files/clincase-workspace/ClinCase/.env"
```

If smoke test PASSES + LLM_PROVIDER value is what you expect → **GO**.
If anything is off → switch to OpenRouter via rollback procedure → **GO**.

---

**Owner accountability:** Danish A. G. is responsible for executing this runbook. If unable, the secondary is whoever has the partner AWS console access. **Do NOT delegate to a teammate who hasn't done a full read of this document.**
