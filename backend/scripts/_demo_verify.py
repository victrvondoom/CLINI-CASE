"""End-to-end demo path verification (round-15) — pure stdlib, no Postgres TestClient needed.

Hits the running backend on :8000 and verifies every step of the demo
script (`ops/demo/PITCH_SCRIPT.md`).
"""
import json
import urllib.request
import urllib.error

API = "http://localhost:8000"


def post(path, body, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), headers=h)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def get(path, headers=None):
    req = urllib.request.Request(API + path, headers=headers or {})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def section(label):
    print()
    print(f"=== {label} ===")


# 1) login
section("1. LOGIN — admin@aerofyta.health")
auth = post("/api/v1/auth/login", {"email": "admin@aerofyta.health", "password": "clincase2026"})
TOK = auth["access_token"]
H = {"Authorization": f"Bearer {TOK}"}
print(f"OK  user={auth['user']['email']} role={auth['user']['role']} org={auth['user']['organization_id']}")

# 2) deep healthz
section("2. /healthz/deep")
h = get("/api/v1/healthz/deep", H)
print(f"status: {h.get('status')}")
for ck, cv in (h.get("checks") or {}).items():
    s = cv.get("status") if isinstance(cv, dict) else cv
    print(f"  {ck}: {s}")

# 3) cases list
section("3. /cases (list)")
cases = get("/api/v1/cases?limit=20", H)
if isinstance(cases, list):
    print(f"count: {len(cases)}")
    for c in cases[:8]:
        cid = c.get("id")
        st = c.get("status", "?")
        pi = c.get("patient_initials", "?")
        rt_v = c.get("requested_treatment")
        rt = rt_v.get("name") if isinstance(rt_v, dict) else rt_v
        print(f"  {cid} | {st} | {pi} | {rt}")
    cases_list = cases
elif isinstance(cases, dict):
    print(f"shape: dict, keys={list(cases.keys())}")
    cases_list = cases.get("items") or cases.get("cases") or []
    print(f"  inner count: {len(cases_list)}")
    for c in cases_list[:8]:
        print(f"  {c.get('id')} | {c.get('status')} | {c.get('patient_initials')}")
else:
    print(f"UNEXPECTED: {type(cases).__name__}")
    cases_list = []

# 4) architecture/layers
section("4. /architecture/layers")
arch = get("/api/v1/architecture/layers", H)
print(f"layers: {len(arch.get('layers', []))}")
print(f"primary_kpis: {len(arch.get('primary_kpis', []))}")
ali = arch.get("cognizant_alignment", {}) or {}
print(f"cognizant_alignment.ai_velocity_gap_addressed: {ali.get('ai_velocity_gap_addressed')}")
print(f"cognizant_alignment.agent_foundry_stage: {ali.get('agent_foundry_stage')}")
print(f"cognizant_alignment.neuro_san_compatible: {ali.get('neuro_san_compatible')}")
print(f"cognizant_alignment.trizetto_ai_gateway_native: {ali.get('trizetto_ai_gateway_native')}")
agents_layer = next((L for L in arch.get("layers", []) if L.get("id") == "orchestration"), None)
if agents_layer:
    a = agents_layer.get("agents", {})
    print(f"orchestration layer: {a.get('parents')} parents | {a.get('sub_agents')} sub-agents | {a.get('llm_backed_sub_agents')} LLM-backed")

# 5) foundry/manifest
section("5. /foundry/manifest")
f = get("/api/v1/foundry/manifest", H)
# Agent counts live under `agent_foundry_compatibility` (same block the
# /industrialize page reads); older payloads had them at the top level.
afc = f.get("agent_foundry_compatibility", {}) or {}
print(f"agents_total: {afc.get('agents_total', f.get('agents_total'))}")
print(f"sub_agents_total: {afc.get('sub_agents_total', f.get('sub_agents_total'))}")
print(f"agent_contract: {afc.get('agent_contract')}")
print(f"deployment_readiness: {f.get('deployment_readiness')}")

# 6) round-13/14 endpoints — make sure they answer (not 500 / not 404)
section("6. Round-13/14 endpoints reachability")
for path in [
    "/api/v1/sagas/me",
    "/api/v1/dlq/me/stats",
    "/api/v1/finops/me?window=7d",
    "/api/v1/compliance/control-library",
    "/api/v1/rate-limits/me",
    "/api/v1/residency",
    "/api/v1/authz/policies",
    "/api/v1/auth/oidc/status",
    "/api/v2/healthz",
    "/api/v1/llm-gateway/circuit-breakers",
]:
    try:
        d = get(path, H)
        keys = list(d.keys())[:4] if isinstance(d, dict) else f"<{type(d).__name__}>"
        print(f"  {path:55s} OK | keys={keys}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:120]
        print(f"  {path:55s} HTTP {e.code} {e.reason} | {body}")
    except Exception as e:
        print(f"  {path:55s} {type(e).__name__}: {str(e)[:100]}")

# 7) demo case — try running one if a fixture exists
section("7. case run-async (if a case exists)")
if cases_list:
    # /cases items key the id as `case_id`; tolerate `id` for older payloads.
    cid = cases_list[0].get("case_id") or cases_list[0]["id"]
    print(f"using case: {cid}")
    try:
        d = post(f"/api/v1/cases/{cid}/run-async", {}, H)
        print(f"OK   POST /cases/{cid}/run-async -> keys={list(d.keys()) if isinstance(d, dict) else type(d).__name__}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"FAIL HTTP {e.code} {e.reason} | {body}")
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
else:
    print("(no cases to run — would need to create one)")

print()
print("=== END ===")
