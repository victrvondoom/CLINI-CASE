# ClinCase — Service Mesh Adoption Decision Record

**Decision today:** **Defer.** No service mesh until at least 30 distinct services or a customer hard-requires zero-trust mTLS.
**Trigger to revisit:** Either threshold above OR a customer asks for SPIFFE/SPIRE identity tokens.

This is the canonical answer to *"why aren't you running Istio / Linkerd?"*

---

## Context

ClinCase's K8s deployment today is two services: `clincase-api` and `clincase-worker`. Communication is:
- **API → Worker** — async via Postgres `case_jobs` queue. No direct call.
- **API → Bedrock** — outbound via VPC endpoint (PrivateLink + IAM).
- **Worker → Bedrock** — same.
- **Both → RDS** — pgbouncer-style pool over private subnets.
- **Both → external (TriZetto Gateway, Q Business)** — outbound HTTPS through NAT or PrivateLink.

There are zero internal service-to-service calls today. Adding a service mesh would solve a problem we don't have.

## When a service mesh is worth the operational tax

A service mesh (Istio / Linkerd / Consul Connect / AWS App Mesh) provides:

1. **mTLS between every pod pair** (zero-trust networking)
2. **Traffic shaping** — canary, blue/green, traffic mirroring at the L7 layer
3. **L7 retries + timeouts + circuit breaking** at the proxy layer (vs. in-app)
4. **Observability** — automatic distributed tracing without app instrumentation
5. **Identity** — SPIFFE/SPIRE-based workload identity tokens

**The cost:**
- 2 sidecars per pod (envoy + control-plane agent) → +30-50% memory per pod
- ~5-10ms p50 latency per service hop
- Significant operational complexity (Istio control plane is non-trivial)
- Mesh-specific CRDs leak into K8s manifests (VirtualService, DestinationRule, etc.)

## Decision matrix

| Criterion | Today | Trigger to add |
|---|---|---|
| Number of services | 2 (api + worker) | ≥10 distinct services |
| Inter-service mTLS required by a customer | No | Any customer asks (very likely Gold-tier EU healthcare) |
| Per-route traffic shaping needed | No | Canary deploy needs % traffic split (today: K8s `maxSurge`/`maxUnavailable` is enough) |
| Observability today | OpenTelemetry SDK | OTel coverage falls below 80% of inter-service calls |
| Identity (SPIFFE) required | No | Customer audit asks for SPIFFE IDs |
| Operations team size | <5 | Team adds dedicated platform engineer |

**None of the trigger thresholds is hit today.** Deferring is the right call.

## What we use INSTEAD of a service mesh

Each problem a mesh would solve has an alternative we already use:

| Mesh feature | ClinCase alternative | Trade-off accepted |
|---|---|---|
| mTLS | NetworkPolicy locks egress to VPC; KMS encrypts data at rest | No mTLS between pods inside the cluster (acceptable while cluster is single-tenant per customer) |
| L7 retries | `Agent[I, O]` framework's retry-with-feedback + ModelRouter Haiku→Sonnet | Per-call instead of per-route (acceptable; we don't have a complex mesh of HTTP services) |
| Circuit breaking | `app/llm/circuit_breaker.py` per-model | App-layer instead of proxy-layer (acceptable; only Bedrock is the volatile dependency) |
| Distributed tracing | OpenTelemetry SDK + W3C Trace Context | Manual instrumentation per layer (acceptable; we have it) |
| Workload identity | IRSA (IAM Roles for Service Accounts) | AWS-native, not SPIFFE-portable (acceptable until customer mandates portability) |

## When to revisit (concrete signals)

We will reopen this decision when ANY of these signals appear:

1. **Service count crosses 10.** ClinCase grows beyond api+worker into separate services for: separate-region routers, dedicated reflection-grader runtime, dedicated outbox publisher fleet, dedicated SSE bridge. At ~10 services, the mesh's L7-everything offsets the operational tax.

2. **Customer asks for SPIFFE IDs.** A Cognizant Gold-tier customer's security questionnaire asks for portable workload identity. SPIFFE/SPIRE → service mesh.

3. **Inter-cluster traffic emerges.** When we have multi-region active-active and need cross-cluster service discovery + mTLS, a mesh's `multi-cluster` mode is the right primitive.

4. **L7 traffic shaping becomes critical.** Canary at the % level, mirror traffic to a shadow service, header-based routing for tenant overrides. Today our deploys are simple enough that K8s rolling-update + HPA suffices.

5. **OpenTelemetry coverage gap.** If new services launch without OTel instrumentation, the mesh's auto-instrumentation becomes valuable. (We commit to OTel-from-day-1 in `CONTRIBUTING.md` — this should not happen.)

## Recommended mesh when we adopt

Order of preference at adoption time:

1. **Linkerd** — lighter, simpler, the right starting point. ~10MB sidecars.
2. **Istio Ambient Mesh** — Envoy-based but no per-pod sidecars (uses ztunnel + waypoint). Best for high-pod-count deployments.
3. **AWS App Mesh** — AWS-native; lowest learning curve for Cognizant TriZetto SAs already on AWS.

We do NOT recommend Consul Connect (HashiCorp) — adds a Consul control plane we don't otherwise need.

## How adopting would look (when we hit a trigger)

- T-30d: choose mesh; install control plane on staging cluster
- T-21d: enable sidecar injection on `clincase-worker` first (safer than API tier — async)
- T-14d: enable on `clincase-api` with sticky sessions verified for SSE
- T-7d: enable mTLS-only mode (`PeerAuthentication: STRICT`)
- T-0d: production deploy with `+1 sidecar` per pod accounted in HPA

## Sources

- Linkerd architecture: https://linkerd.io/2/reference/architecture/
- Istio Ambient Mesh: https://istio.io/latest/docs/ambient/overview/
- AWS App Mesh: https://aws.amazon.com/app-mesh/
- "When to use a service mesh" (Bilgin Ibryam): https://itnext.io/microservices-when-to-react-with-a-service-mesh-09a7c0eb31e3
- SPIFFE: https://spiffe.io/
