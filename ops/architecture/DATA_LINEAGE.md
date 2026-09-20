# ClinCase — Data Lineage (OpenLineage)

**Status:** Accepted (round-11; emitter shipped, downstream Marquez at first ML-retraining customer)
**Audience:** ML platform team · auditor verifying decision provenance · compliance officer validating CMS-0057-F § IV.D

## Why we need lineage

Two distinct customers ask for it:

1. **ML platform team** — "We want to retrain Sonnet on cases that ended in successful approvals. Show me which RAG documents informed each decision so we can curate the training set."
2. **Auditor** — "For CMS-0057-F § IV.D and HIPAA, prove that decision X was based on this specific policy version, not an outdated draft."

Both need the same primitive: **a directed graph linking input datasets → job → output datasets, captured per agent run.**

That's exactly what OpenLineage formalizes.

## Decision

Emit OpenLineage events for:

| Event source | Inputs | Outputs |
|---|---|---|
| Agent run (any of 7 parents) | the case row + any prior agent outputs | the agent's structured output |
| RAG retrieval | the corpus documents retrieved | a `case.{id}.retrieval` artifact |
| Decision write | all agent outputs + retrieved docs | the `decisions.{id}` row |

## Wire path

```
ClinCase agent runs
       │
       ▼
emit_agent_run(...)              app/observability/lineage.py
       │
       ▼ (async POST)
$OPENLINEAGE_URL
       │
       ├──► Marquez (UI for graph exploration)
       ├──► DataHub (LinkedIn data discovery)
       ├──► OpenMetadata
       └──► Kafka REST proxy → downstream consumers
```

## What ships today (round-11)

- `app/observability/lineage.py` — `emit_agent_run()` + `emit_rag_retrieval()` + `lineage_snapshot()`
- Failure-isolated (lineage CANNOT block the agent path)
- No-op when `OPENLINEAGE_URL` is unset → safe to deploy without infrastructure
- JSON-logged on every emit so even without Marquez, lineage is queryable in CloudWatch / Loki

## Wiring (lands at first ML-retraining customer)

The emitter is built but not yet wired into the agent framework. Two-line landing:

```python
# In app/agents/framework/agent.py, end of `invoke()`:
from app.observability.lineage import emit_agent_run, new_run_id

run_id = new_run_id()
await emit_agent_run(
    agent_name=self.agent_name,
    run_id=run_id,
    case_id=ctx.case_id,
    organization_id=ctx.organization_id,
    event_type="COMPLETE",
    outputs=[{"namespace": "clincase", "name": f"agent.{self.agent_name}.output.{ctx.case_id}"}],
)
```

Why deferred? The `Agent.invoke()` path is hot (called 22+ times per case) — we want to size the lineage emit's lock-step impact in load testing first. Smoke tests show ≤ 0.5ms overhead per emit; lands in round-12.

## Compliance — CMS-0057-F § IV.D

§ IV.D requires "documentation supporting the decision." OpenLineage events
form this documentation programmatically:

- For each decision, the auditor queries Marquez for the `decisions.{id}`
  output node
- The graph upstream shows: which agent produced it, which agents fed in,
  which RAG documents were retrieved, which version of the corpus
- Time-travel queries by `eventTime` reproduce the state-of-the-world at
  decision time

This is exactly what *"reproducible AI decisions"* means in practice.

## Sources

- OpenLineage spec — https://openlineage.io/
- Marquez — https://marquezproject.ai/
- LinkedIn DataHub — https://datahubproject.io/
- AWS blog — *Implementing data lineage in AWS* (https://aws.amazon.com/blogs/big-data/build-an-end-to-end-data-lineage-solution-with-amazon-emr-on-eks-marquez-and-openlineage/)
