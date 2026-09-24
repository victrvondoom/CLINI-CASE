# ClinCase — Production Runbook

**On-call audience:** ClinCase SRE rotation + TriZetto on-call SA

**Companion artifacts:**
- `ops/sre/SLO.yaml` — SLO + error-budget definitions
- `ops/k8s/` — K8s manifests
- `ops/SCALING.md` — capacity model + bottleneck analysis
- `ops/aws/MIGRATION_RUNBOOK.md` — AWS Bedrock migration playbook
- `app/api/metrics.py` — Prometheus surface

---

## Severity ladder

| Severity | Symptom | Response time | Auto-page |
|---|---|---|---|
| **P1** | Customer-impacting outage. PHI exposure. Adverse-determination signoff missing. Cost runaway > 10× baseline. | 5 min | Yes — primary on-call + secondary + business owner |
| **P2** | One SLO at 14.4× burn rate (1h budget exhausted in 30d). Bedrock regional brownout. Queue depth > 200 sustained 5m. | 15 min | Yes — primary on-call |
| **P3** | One SLO at 6× burn rate (6h window). Latency degradation. Cost > 1.2× rolling-7d baseline. | 1 hr | Daytime: yes; off-hours: ticket |
| **P4** | Non-customer-impacting bug. Eval F1 dip < 5pp. | next business day | Ticket |

PagerDuty service: `PD-CLINCASE-PRIMARY`. Routing keys in AWS Secrets Manager `clincase/pagerduty-routing`.

---

## Standing dashboards

| Dashboard | URL | Watch for |
|---|---|---|
| ClinCase CloudWatch | (link) | API latency p99, error rate, queue depth, LLM cost rate |
| Bedrock Provisioned Throughput | AWS console → Bedrock → Provisioned throughput | Sonnet/Haiku utilization >80% |
| Datadog LLM Observability | (link) | Hallucination eval scores, prompt-injection scanner hits |
| Compliance live scorecard | https://api.clincase.example.com/api/v1/compliance/org | TAT %, SB-1120 %, audit completeness |

---

## Common incidents — diagnose + fix

### INC-001 — `BudgetExceeded` storm (per-case ceiling firing for many cases)

**Symptom:** `clincase_agent_invocations_total{status="error"}` rate spikes; cases all error before LLM call; logs show `BudgetExceeded[cost_usd]` with the $5/case ceiling.

**Diagnose:**
1. `kubectl logs -n clincase deploy/clincase-worker --tail=200 | grep BudgetExceeded`
2. Check `clincase_llm_cost_usd_total / clincase_cases_total{status='done'}` — average per-case cost.
3. If average > $4: a sub-agent is iterating beyond `max_iterations` because of a schema regression.

**Fix:**
1. Roll the worker tier back to the prior image: `kubectl rollout undo deploy/clincase-worker -n clincase`
2. Open a P3 to find the schema drift; check the latest agent_runs rows for the failing agent.
3. Do NOT raise the per-case ceiling under incident — it's the floor that's saving you.

### INC-002 — Bedrock regional brownout (`ap-south-1` 5xx storm)

**Symptom:** Sustained 5xx from `bedrock-runtime`; framework escalation Haiku→Sonnet not helping; queue depth climbing.

**Diagnose:**
1. AWS Health Dashboard: any `bedrock-runtime` events in `ap-south-1`?
2. Check `aws bedrock get-model-invocation-logging-configuration` — logging side healthy?
3. `kubectl exec` a worker; `python -c "from app.llm import get_llm_client; ..."` — direct hit.

**Fix:**
1. **If multi-region module is applied:** flip Route 53 LBR weights to favor `us-east-1` (Aurora secondary already promotable). Run:
   ```bash
   ./ops/sre/scripts/regional-failover.sh us-east-1
   ```
2. **If multi-region not yet applied** (current state): backlog is acceptable. Cases queue, drain when region recovers. Communicate to TriZetto on-call.
3. Bedrock recovers → automatic resume. Janitor reaps stale heartbeats and requeues affected jobs (`reap_stale` in `app/jobs/queue.py`).

### INC-003 — PHI guardrail bypass (P1, zero tolerance)

**Symptom:** `clincase_guardrail_blocked_total{guardrail="phi_input"}` rate > 0 for any 5-minute window with `decision=BLOCK_BYPASSED`. Or a security scan flags a PHI string in a prompt.

**Action (in this exact order):**
1. **STOP all worker traffic immediately.**
   ```bash
   kubectl scale deploy/clincase-worker -n clincase --replicas=0
   ```
2. Page primary + business owner + safety contact (`safety@clincase.example.com`).
3. Pull the offending agent_runs row. Establish the impact scope: which cases in the last 24h had PHI in the prompt?
4. **DO NOT** publish a fix; revert the API tier to the last known-good image (`:prod-{prior-date}` ECR tag).
5. Open a regulatory incident ticket. CMS-0057-F § IV.D requires retention; we keep the affected agent_runs rows but mark them `phi_quarantine`.
6. Once root-cause is verified clean, re-enable workers via canary 10% with elevated PHI guardrail strictness.

### INC-004 — Adverse determination missing reviewer signoff (CA SB 1120 violation)

**Symptom:** `clincase_compliance_sb1120_compliance_pct < 100` on any daily run. There exists at least one DENY decision in the last 24h with no `reviewer_actions` row.

**Action:**
1. Page primary + business owner. **This is a regulatory event in California.**
2. Identify the case: `SELECT id FROM cases c LEFT JOIN reviewer_actions ra ON ra.case_id = c.id JOIN decisions d ON d.case_id = c.id WHERE d.verdict = 'DENY' AND ra.id IS NULL AND c.created_at > NOW() - INTERVAL '24 hours';`
3. **Mark the case `awaiting_review`**: `UPDATE cases SET status = 'awaiting_review' WHERE id = ?;`
4. Notify the customer's clinical operations director via the configured contact.
5. Inspect `app/graph/build.py` review_gate routing — was the case under HITL_CONFIDENCE_THRESHOLD but routed past the gate? Open P1 fix-forward ticket.

### INC-005 — Queue depth runaway

**Symptom:** `clincase_jobs_queue_depth{status="queued"} > 200` sustained 5m.

**Diagnose:**
1. Check worker pod count: `kubectl get pods -n clincase -l tier=worker | wc -l`. HPA target is 5 jobs/replica.
2. Check Bedrock TPM: `clincase_llm_throttle_total` rate?
3. Check RDS: connection saturation? `pg_stat_activity` count.

**Fix:**
1. HPA should be scaling. If not: `kubectl describe hpa clincase-worker-hpa -n clincase` — is the custom metric `clincase_jobs_queue_depth` reaching the HPA?
2. If Bedrock-throttled: switch on Provisioned Throughput (already `ops/terraform/provisioned-throughput/`). Apply if not already.
3. If RDS-saturated: bump `DATABASE_POOL_MAX` in ConfigMap, rolling-restart workers.

### INC-006 — Eval cohort F1 regression (decision-quality SLO breach)

**Symptom:** `clincase_eval_cohort_macro_f1 < 0.85` on any daily run.

**Action:**
1. **Freeze production deploys**: comment on `#releases` Slack, GitHub deployment-protection rule already gates this.
2. Pull the disagreement taxonomy: `GET /api/v1/eval/cohort` → see `disagreement_taxonomy` block.
3. Identify the regressed agent. Most likely culprit: a sub-agent prompt change merged in the last 7 days. Bisect via `git log -p backend/app/prompts/`.
4. Roll the prompt back. Re-run eval. If F1 restored: deploy fix; unfreeze.

### INC-007 — Cost runaway (1.5× baseline for 1h)

**Symptom:** `clincase_llm_cost_usd_total / 1d > 1.5 ×` rolling 7-day median.

**Action:**
1. Check the per-agent cost breakdown: `histogram_quantile(0.99, sum by (agent_name)(rate(clincase_agent_cost_usd_total[1h])))`.
2. If one agent is the outlier: usually `letter_composer` or `evidence_matcher` reflection is iterating to ceiling. Pin `max_iterations` lower in config; rolling restart.
3. If broad-based: check Bedrock model_id distribution. If we're escalating Haiku→Sonnet on 100% of retries, the parser regressed; revert.
4. If the spike is real load (good problem): apply Provisioned Throughput Terraform; commit to OneMonth tier.

---

## Standard diagnostics commands

```bash
# Pod health
kubectl get pods -n clincase
kubectl logs -n clincase deploy/clincase-worker --tail=200
kubectl logs -n clincase deploy/clincase-api --tail=200

# Queue + budget snapshot
kubectl exec -it -n clincase deploy/clincase-api -- \
  curl -s http://localhost:8000/api/v1/jobs/queue/depth | jq .

# Live SLO snapshot
curl -s https://api.clincase.example.com/metrics | grep -E "clincase_(case_duration|llm_cost|queue_depth|guardrail)"

# Recent agent_runs for a case
psql $DATABASE_URL -c "SELECT id, agent_name, latency_ms, model_id, error_text \
  FROM agent_runs WHERE case_id = '$CASE_ID' ORDER BY id ASC;"

# Live compliance scorecard for an org
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.clincase.example.com/api/v1/compliance/org | jq .

# Evidence pack export (auditor request)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.clincase.example.com/api/v1/cases/$CASE_ID/evidence-pack \
  > evidence-$CASE_ID.json
```

---

## Post-mortem template (P1/P2 incidents)

Within 24 hours of resolution, the IC writes a post-mortem at `ops/sre/post-mortems/INC-YYYY-MM-DD-NNN.md` answering:

1. **Summary** — one paragraph; what broke, who was impacted, how we resolved.
2. **Timeline** — UTC timestamps from first alert to "resolved" declaration.
3. **Root cause** — the technical mechanism. Five-whys depth.
4. **Customer impact** — number of cases delayed/erred; cost dollars; PHI involvement (yes/no).
5. **Compliance impact** — CMS-0057-F clauses affected; SB 1120 events; auditor notification needed?
6. **Detection** — what fired (alert / customer report / monitoring miss)?
7. **Mitigation** — what stopped the bleeding.
8. **Resolution** — what fixed root cause.
9. **Action items** — *blameless*. Each AI has owner, JIRA, deadline.
10. **Glasses lessons** — what we learned for the rotation.

The post-mortem is reviewed in the next weekly SRE sync and shared with TriZetto on-call when the incident touched the integration surface.

---

## Escalation contacts

| Tier | Role | Channel | SLA |
|---|---|---|---|
| L1 | ClinCase SRE primary | PagerDuty `PD-CLINCASE-PRIMARY` | 5 min |
| L2 | ClinCase engineering manager | Slack `#clincase-on-call` | 15 min |
| L3 | TriZetto on-call SA | Slack `#trizetto-clincase-bridge` (configured in shared workspace) | 30 min |
| L4 | partner health-sciences lead | Email + phone (TODO: configure post-pilot) | 1 hr |

---

## Reference — Datadog LLM Observability

We instrument every Bedrock call with the Datadog LLM SDK ([docs](https://docs.datadoghq.com/llm_observability/)). Hallucination eval, prompt-injection scanner, and token/cost dashboards are pre-built; SLO burn-rate alerts feed the same PagerDuty service. See `app/observability/datadog.py` for the SDK init (TODO post-pilot).
