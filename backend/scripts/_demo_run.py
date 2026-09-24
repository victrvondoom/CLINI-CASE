"""ASCII-safe end-to-end probe — finds approved case with citations + runs pending case."""
import json, sys, time, urllib.request, urllib.error

API = "http://localhost:8000"
LOG = open(r"C:\Users\ASUS\AppData\Local\Temp\clincase_demo_run.log", "w", encoding="utf-8")
def log(*a):
    msg = " ".join(str(x) for x in a)
    LOG.write(msg + "\n")
    LOG.flush()

def post(path, body, headers=None):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    return json.loads(urllib.request.urlopen(urllib.request.Request(API+path, data=json.dumps(body).encode(), headers=h), timeout=120).read())

def get(path, headers=None):
    return json.loads(urllib.request.urlopen(urllib.request.Request(API+path, headers=headers or {}), timeout=120).read())

# Login
auth = post("/api/v1/auth/login", {"email":"admin@clincase.health","password":"clincase2026"})
T = auth["access_token"]
H = {"Authorization": f"Bearer {T}"}

cases_resp = get("/api/v1/cases?limit=20", H)
items = cases_resp.get("cases", cases_resp) if isinstance(cases_resp, dict) else cases_resp
log(f"cases: {len(items)}")

approved = [c for c in items if c.get("status") == "approved"]
log(f"approved: {len(approved)}")

# 1) inspect any approved case for citations
if approved:
    cid = approved[0]["case_id"]
    log(f"--- inspecting approved case {cid} ---")
    detail = get(f"/api/v1/cases/{cid}", H)
    dec = detail.get("decision") or {}
    log(f"  verdict: {dec.get('verdict')}")
    log(f"  rationale: {(dec.get('rationale') or '')[:200]}")
    log(f"  citations ({len(dec.get('citations', []))}):")
    for c in dec.get("citations", []):
        log(f"    kind={c.get('kind')!s:12s} pointer={(c.get('pointer') or '')[:80]}")
    log(f"  risk_flags: {dec.get('risk_flags')}")

# 2) find a pending and run it
pending = [c for c in items if c.get("status") == "pending"]
log(f"\npending: {len(pending)}")
if pending:
    cid = pending[0]["case_id"]
    log(f"--- POST /cases/{cid}/run-async ---")
    try:
        out = post(f"/api/v1/cases/{cid}/run-async", {}, H)
        log(f"  response: {json.dumps(out, default=str)[:400]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:600]
        log(f"  HTTP {e.code}: {body}")

# 3) compliance scorecard endpoint
log("\n--- /compliance scorecard ---")
try:
    cs = get("/api/v1/compliance/scorecard", H)
    log(f"  keys: {list(cs.keys()) if isinstance(cs, dict) else cs}")
except urllib.error.HTTPError as e:
    log(f"  HTTP {e.code}")

# 4) business value
log("\n--- /business-value ---")
try:
    bv = get("/api/v1/business-value", H)
    log(f"  keys: {list(bv.keys()) if isinstance(bv, dict) else bv}")
except urllib.error.HTTPError as e:
    log(f"  HTTP {e.code}")

# 5) eval
log("\n--- /eval ---")
try:
    ev = get("/api/v1/eval", H)
    log(f"  keys: {list(ev.keys()) if isinstance(ev, dict) else ev}")
except urllib.error.HTTPError as e:
    log(f"  HTTP {e.code}")

# 6) Architecture (re-verify with detail)
log("\n--- /architecture/layers detail ---")
arch = get("/api/v1/architecture/layers", H)
for L in arch.get("layers", []):
    log(f"  {L.get('id'):24s} components={len(L.get('components', []))} endpoints={len(L.get('endpoints') or [])}")

LOG.close()
print("OK — log written to C:\\Users\\ASUS\\AppData\\Local\\Temp\\clincase_demo_run.log")
