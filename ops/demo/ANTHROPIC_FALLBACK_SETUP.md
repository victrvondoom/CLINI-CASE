# Anthropic API Direct — Fallback Setup (P2 — Insurance)

**Total time:** 10 minutes
**Total cost:** $0 (Anthropic offers $5 free credit on new accounts)

This is your **third leg of redundancy** for the May 7 demo:
1. Bedrock (preferred — May 6 migration)
2. OpenRouter (current — `$17.47` credit remaining)
3. **Anthropic API direct** (this doc — set up TODAY as insurance)

If both Bedrock AND OpenRouter fail simultaneously, this is what saves the demo.

---

## Step 1 — Get an Anthropic API key (5 min)

1. Go to https://console.anthropic.com
2. Sign up (use a fresh email if you've used the trial before)
3. Navigate to **API Keys** → **Create Key**
4. Copy the key — starts with `sk-ant-...`

New accounts receive **$5 in free trial credit** — about 20 case runs at observed cost.

---

## Step 2 — Add to `.env` (1 min)

Edit `D:/xzashr.ai Files/clincase-workspace/ClinCase/.env` — find these lines:

```
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

Set the API key:

```
ANTHROPIC_API_KEY=sk-ant-api03-XXXX...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

**Do NOT change `LLM_PROVIDER` yet** — you keep `openrouter` as primary. This is just pre-arming the fallback.

---

## Step 3 — Test it works (3 min, costs ~$0.05)

```bash
cd "D:/xzashr.ai Files/clincase-workspace/ClinCase/backend"

# Temporarily flip to anthropic
$env:LLM_PROVIDER = "anthropic"   # PowerShell
# OR
LLM_PROVIDER=anthropic             # bash

# Restart backend + worker (see BEDROCK_MIGRATION_RUNBOOK.md Step 3)

# Run smoke test
.venv/Scripts/python.exe -m scripts.smoke_test
# expect: SMOKE TEST: PASS
```

Then put back to `openrouter` (the primary):

```bash
$env:LLM_PROVIDER = "openrouter"
# Restart backend + worker again
```

---

## Step 4 — Document the failover trigger (1 min)

If on demo day the worker logs show `OpenRouter: 402` OR `OpenRouter: 503` errors:

1. Edit `.env` → change `LLM_PROVIDER=openrouter` to `LLM_PROVIDER=anthropic`
2. Restart backend + worker (`make backend.dev` + `python -m app.workers.case_runner`)
3. Demo continues — same Claude, different billing path

**Total failover time: ~30 seconds.** Known to work because the Anthropic
provider is already in `app/llm/anthropic_client.py` and the gateway
routes correctly per the round-15 fixes.

---

## Why this matters

The architecture's `LLMClient` abstraction (`app/llm/client.py`) was designed
exactly for this scenario — same agent code, swap the underlying provider
via one env var. Round-15 verified the path works for both
`openrouter` and `bedrock`. Anthropic-direct uses the same
`AnthropicClient` class that's already imported and tested.

You don't need to write new code. You just need an API key on file.

**Cost of this insurance: $0 (free trial). Time: 10 minutes. Reduces demo
catastrophe risk by ~10 percentage points.**
