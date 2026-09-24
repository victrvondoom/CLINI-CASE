"""Poll until case completes (or fails), then dump full results."""
import asyncio, asyncpg, json, os, time, urllib.request

os.environ.setdefault('DATABASE_URL', 'postgresql://clincase:clincase@localhost:15432/clincase')
CASE_ID = "cabeca8945cf"  # freshly seeded rich-FHIR case (round-15 systemic-fix test)
TIMEOUT_S = 480  # 8 minutes max

API = "http://localhost:8000"


async def poll_and_report():
    started = time.time()
    last_status = None
    final_state = None
    while time.time() - started < TIMEOUT_S:
        c = await asyncpg.connect(os.environ['DATABASE_URL'])
        try:
            job = await c.fetchrow(
                "SELECT status, attempts, error_text FROM case_jobs WHERE case_id=$1 ORDER BY created_at DESC LIMIT 1",
                CASE_ID,
            )
            n_runs = await c.fetchval("SELECT COUNT(*) FROM agent_runs WHERE case_id=$1", CASE_ID)
            n_llm  = await c.fetchval("SELECT COUNT(*) FROM llm_invocations WHERE case_id=$1", CASE_ID)
            n_llm_ok = await c.fetchval("SELECT COUNT(*) FROM llm_invocations WHERE case_id=$1 AND status='ok'", CASE_ID)
            case_status = await c.fetchval("SELECT status FROM cases WHERE id=$1", CASE_ID)
        finally:
            await c.close()

        elapsed = int(time.time() - started)
        status_str = f"job={job['status']:10s} attempts={job['attempts']} | agents={n_runs} | llm={n_llm_ok}/{n_llm} | case={case_status}"
        if status_str != last_status:
            print(f"[+{elapsed:3d}s] {status_str}")
            if job['error_text']:
                print(f"          error_text: {(job['error_text'] or '')[:200]}")
            last_status = status_str

        if job['status'] in ('done', 'completed', 'success'):
            final_state = 'success'
            break
        if job['status'] in ('dead', 'failed'):
            final_state = 'failed'
            break
        if case_status in ('approved', 'denied', 'referred', 'overturned', 'appealed'):
            final_state = case_status
            break

        await asyncio.sleep(3)

    print()
    print("=" * 72)
    print(f"FINAL: {final_state or 'TIMEOUT'} after {int(time.time() - started)}s")
    print("=" * 72)

    # Now fetch the case detail
    auth = json.loads(urllib.request.urlopen(urllib.request.Request(
        API + '/api/v1/auth/login',
        data=json.dumps({'email': 'admin@clincase.health', 'password': 'clincase2026'}).encode(),
        headers={'Content-Type': 'application/json'},
    )).read())
    H = {'Authorization': f"Bearer {auth['access_token']}"}

    detail = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"{API}/api/v1/cases/{CASE_ID}", headers=H
    )).read())

    print()
    print("=== CASE DETAIL ===")
    for k in ('case_id', 'status', 'patient_initials', 'payer_id'):
        print(f"  {k:24s}: {detail.get(k)}")

    rt = detail.get('requested_treatment')
    if isinstance(rt, dict):
        print(f"  requested_treatment.name: {rt.get('name')}")
    else:
        print(f"  requested_treatment      : {rt}")

    cs = detail.get('clinical_snapshot')
    if isinstance(cs, dict):
        print(f"  clinical_snapshot keys   : {list(cs.keys())}")
        bm = cs.get('biomarkers') or []
        print(f"  biomarkers count         : {len(bm)}")
        for b in bm[:3]:
            print(f"    {b}")

    na = detail.get('necessity_assessment')
    if isinstance(na, dict):
        print(f"  necessity overall_verdict: {na.get('overall_verdict')}")
        print(f"  necessity overall_conf   : {na.get('overall_confidence')}")
        crits = na.get('criteria') or []
        print(f"  criteria evaluated       : {len(crits)}")

    dec = detail.get('decision')
    if isinstance(dec, dict):
        print()
        print("=== DECISION ===")
        print(f"  verdict          : {dec.get('verdict')}")
        print(f"  confidence       : {dec.get('confidence')}")
        print(f"  risk_flags       : {dec.get('risk_flags')}")
        rationale = dec.get('rationale') or ''
        print(f"  rationale ({len(rationale)} chars):")
        for line in rationale.split('\n'):
            print(f"    {line}")
        cits = dec.get('citations') or []
        print(f"  citations ({len(cits)}):")
        kinds_seen = set()
        for cit in cits:
            k = cit.get('kind')
            kinds_seen.add(k)
            print(f"    [{k:11s}] pointer={(cit.get('pointer') or '')[:70]}")
            t = cit.get('text') or ''
            if t:
                print(f"                 text={t[:80]}")
        print()
        print(f"  CITATION KINDS PRESENT: {sorted(kinds_seen)}")
        print(f"  ROUND-14 KINDS USED   : {sorted(kinds_seen - {'clinical', 'policy'})}")

    # Cost rollup
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    try:
        cost = await c.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0)::FLOAT FROM llm_invocations WHERE case_id=$1 AND status='ok'",
            CASE_ID,
        )
        latency = await c.fetchval(
            "SELECT COALESCE(SUM(latency_ms), 0)::INT FROM llm_invocations WHERE case_id=$1 AND status='ok'",
            CASE_ID,
        )
        in_tok = await c.fetchval(
            "SELECT COALESCE(SUM(input_tokens), 0)::INT FROM llm_invocations WHERE case_id=$1 AND status='ok'",
            CASE_ID,
        )
        out_tok = await c.fetchval(
            "SELECT COALESCE(SUM(output_tokens), 0)::INT FROM llm_invocations WHERE case_id=$1 AND status='ok'",
            CASE_ID,
        )
        n_calls = await c.fetchval(
            "SELECT COUNT(*) FROM llm_invocations WHERE case_id=$1 AND status='ok'",
            CASE_ID,
        )
    finally:
        await c.close()

    print()
    print("=== COST + LATENCY ===")
    print(f"  llm calls (ok)   : {n_calls}")
    print(f"  total cost       : ${cost:.4f}")
    print(f"  total tokens     : in={in_tok}  out={out_tok}")
    print(f"  total LLM latency: {latency} ms ({latency/1000:.1f}s)")

    # Per-agent breakdown
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    try:
        rows = await c.fetch(
            """
            SELECT agent_name, COUNT(*) AS n, SUM(cost_usd)::FLOAT AS cost, SUM(latency_ms)::INT AS latency
              FROM llm_invocations
             WHERE case_id=$1 AND status='ok'
             GROUP BY agent_name
             ORDER BY agent_name
            """,
            CASE_ID,
        )
        print()
        print("  per-agent breakdown:")
        for r in rows:
            print(f"    {r['agent_name']:35s} n={r['n']:2d}  ${r['cost']:.4f}  {r['latency']}ms")
    finally:
        await c.close()


if __name__ == "__main__":
    asyncio.run(poll_and_report())
