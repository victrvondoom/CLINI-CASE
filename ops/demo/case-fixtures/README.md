# Demo case fixtures — pre-built result JSON

These three files are the **expected** ClinCase output for the three demo paths. Useful for:

- **Demo fallback** — if the live LLM call fails on stage, show the JSON file as proof of what the result *would* look like
- **Eval cohort** — gold-label answers against which `app/api/eval.py` cohort harness measures macro F1
- **Regression gates** — if the schema of any of these files changes, a contract test in `backend/tests/agents/` will surface it

| File | Verdict | Demo path |
|---|---|---|
| [`case-001-clean-approve.json`](./case-001-clean-approve.json) | APPROVE | The "happy path" — trastuzumab on HER2+ breast cancer |
| [`case-002-deny-with-appeal.json`](./case-002-deny-with-appeal.json) | DENY → appeal drafted | Pembrolizumab + missing PD-L1 ≥ 1% (denial path with auto-drafted appeal letter) |
| [`case-003-hitl-pause.json`](./case-003-hitl-pause.json) | REFER (paused at review_gate) | Edge case where Necessity Reasoner confidence < 0.75 → routes to clinician for SB 1120 signoff |

## Schema of each file

Each fixture mirrors the response shape of `POST /api/v1/cases/{case_id}/run`:

```json
{
  "case_id": "...",
  "clinical_snapshot": {...},
  "policy_excerpts": [...],
  "necessity_assessment": {...},
  "decision": {"verdict": "...", "rationale": "...", "citations": [...], "confidence": 0.92},
  "denial_forecast": null | {...},
  "appeal_draft": null | {"appeal_body": "...", "structured_arguments": [...]},
  "patient_communication": {...},
  "paused_for_review": false | true,
  "pause_reason": null | "..."
}
```

## How to regenerate

After Bedrock migration on May 6:

```bash
# Run the full DAG against each fixture and capture the response
for fixture in trastuzumab_clean pembrolizumab_deny lowconf_refer; do
  curl -X POST http://localhost:8000/api/v1/demo-fixtures/$fixture/create-case \
       -H "Authorization: Bearer $TOKEN" \
    | jq -r '.case_id' > /tmp/case_id

  curl -X POST http://localhost:8000/api/v1/cases/$(cat /tmp/case_id)/run \
       -H "Authorization: Bearer $TOKEN" \
    | jq . > ops/demo/case-fixtures/$fixture.json
done
```

The fixtures shipped here are pre-built, hand-constructed examples that match what the DAG would produce. Treat as gold labels, not as live truth.
