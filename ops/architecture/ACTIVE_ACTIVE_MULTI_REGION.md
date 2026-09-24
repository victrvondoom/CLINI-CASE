# ClinCase — Active/Active Multi-Region (ADR-0011)

**Status:** Deferred-with-explicit-trigger
**Audience:** TriZetto solution architect · Gold-tier customer SRE · auditor verifying RPO 1s commitment

## Context

Round-9 multi-region story is **active/passive failover** via Aurora Global Database secondary + Route 53 LBR. RPO is "1 second" only because Aurora Global advertises that — actual customer-facing RPO is bound by the failover script's wall-clock time (60–90s) PLUS DNS propagation (30–60s). Real RPO at the customer is therefore **~2 minutes**, not 1 second.

For most customers this is acceptable. For **Gold-tier** customers contracted at "RPO 1s, RTO 60s" — it is not. They need **active/active**: writes accepted in BOTH regions concurrently, conflict resolution at the data layer.

## What active/active actually requires (this is why it's a multi-month project)

| Requirement | Effort | Risk |
|---|---|---|
| **CRDT or last-writer-wins for every domain table** | High — every UPDATE statement needs a vector clock or HLC timestamp | High — convergence bugs are subtle |
| **Aurora write-forwarding OR Aurora multi-master** | Medium — Aurora supports it for some engines but with restrictions | Medium — performance penalty on cross-region writes |
| **Eventual-consistency-aware queries** | High — every `SELECT for UPDATE` must reason about replica lag | High — race conditions cause double-decisions |
| **Idempotent saga compensations across cells** | Medium — outbox pattern already partially ready | Medium |
| **Geo-aware Bedrock routing** | Low — round-10 residency module already does this | Low |
| **Geo-aware client routing (latency-based DNS)** | Low — Route 53 LBR already does this | Low |
| **Conflict UI for split-brain decisions** | Medium — coordinator UI shows the conflict and asks for resolution | Medium |
| **Cross-region message bus** (replaced outbox publisher) | High — EventBridge cross-region or Kinesis with multi-region consumer | Medium |

**Honest estimate:** 4–6 engineer-months for a competent team. Not a 1-night addition.

## Decision

**Deferred.** We commit to active/active only when ALL of these triggers fire:

1. A signed contract with a Gold-tier customer that names "RPO 1s, RTO 60s" as a contractual obligation
2. The customer's traffic profile makes active/passive's ~2-minute RPO commercially material (e.g., $X revenue/min lost during failover)
3. Engineering team has 4 months of dedicated runway (not a side project)
4. We have a formal verification of CRDT semantics for our specific schema

Until then: **active/passive with the round-10 regional-failover script** is the documented commitment. This is honest, achievable, and defensible.

## What we DO have today (round-10 + 11)

- Aurora Global Database secondary in `us-east-1` (apply-ready Terraform)
- `regional-failover.sh` — 5-phase script with smoke-test verification
- `dr-drill.sh` — quarterly verification it still works
- Per-tenant data residency runtime — already region-aware
- Cell-based architecture (round 11) — bounds blast radius
- Outbox pattern + saga compensations — already idempotent

A Gold customer who contractually requires 1-min RPO can run on this AND have a TriZetto SA on standby for failover orchestration. Not 1-second RPO, but defensible against single-region outages.

## What we DON'T have today (and would need)

- CRDT-aware schema (vector clocks on every domain row)
- Aurora multi-master configured
- Conflict resolution UI for the coordinator
- Cross-region message bus replacing the outbox publisher
- Formal CRDT correctness proof

## Honest framing

When a customer asks *"do you support active/active multi-region?"* — the answer is:

> "Today we deliver active/passive with a 60-second failover script that's
> drilled quarterly. Our DR/BCP playbook documents the path to active/active
> with explicit triggers; we've quantified the engineering investment as 4–6
> months. At the first contractually-obligated Gold customer, we begin that
> work. We have not engineered the prerequisites because that would be
> over-engineering for the customer profile we're shipping for."

This is what a senior solution architect *wants* to hear: clear-eyed about the gap, with a documented trigger and effort estimate. Hand-waving "yes we support it" without the CRDT work would be the wrong answer.

## Sources

- AWS Active-Active patterns — https://docs.aws.amazon.com/whitepapers/latest/aws-multi-region-fundamentals/active-active-architectures.html
- Aurora Global Database — https://aws.amazon.com/rds/aurora/global-database/
- AWS DynamoDB Global Tables (canonical active-active example) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html
- CRDTs — *A comprehensive study of Convergent and Commutative Replicated Data Types* (Shapiro et al.)
- Stripe engineering — *Online migrations at scale*
