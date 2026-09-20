# ClinCase — Kubernetes deployment

Production-ready manifests for AWS EKS. Two independent tiers; each scales
horizontally on its own signal.

```
                                       ┌────────────────────────────┐
                                       │  ALB (sticky for SSE)      │
                                       └─────────────┬──────────────┘
                                                     │
                                       ┌─────────────▼──────────────┐
                                       │  clincase-api Deployment    │
                                       │  (3–50 replicas, HPA on    │
                                       │   CPU + memory)            │
                                       └─────────────┬──────────────┘
                                                     │  enqueue (HTTP)
                                                     ▼
                                       ┌────────────────────────────┐
                                       │  case_jobs (RDS Aurora)    │
                                       │  Postgres SKIP LOCKED      │
                                       └─────────────┬──────────────┘
                                                     │  claim (HTTP)
                                                     ▼
                                       ┌────────────────────────────┐
                                       │  clincase-worker Deployment │
                                       │  (5–100 replicas, HPA on   │
                                       │   queue depth)             │
                                       └────────────────────────────┘
                                                     │
                                                     ▼
                                       ┌────────────────────────────┐
                                       │  Bedrock + Knowledge Base  │
                                       │  (PrivateLink — no public  │
                                       │   egress)                  │
                                       └────────────────────────────┘
```

## Files

| File | Purpose |
|---|---|
| `config.yaml`              | Namespace + ConfigMap + Secrets shape + ServiceAccounts + NetworkPolicy |
| `api-deployment.yaml`      | API tier Deployment + Service + Ingress + HPA |
| `worker-deployment.yaml`   | Worker tier Deployment + HPA (queue-depth) + PodDisruptionBudget |

## Apply order

```bash
kubectl apply -f config.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f worker-deployment.yaml
kubectl get all -n clincase
```

## Scale signals

| Tier | Scale on | Min | Max | Target |
|---|---|---:|---:|---|
| API    | CPU + memory                                          |  3 |  50 | 65% CPU avg |
| Worker | `clincase_jobs_queue_depth{status="queued"}` (custom)  |  5 | 100 | 5 queued jobs / replica avg |

The custom metric requires `prometheus-adapter` running in `kube-system`
mapping `/metrics` → external metrics API.

## Capacity model

See `ops/SCALING.md` for the full math. Quick reference:

| Daily volume | API replicas | Worker replicas | RDS instance | Monthly $ |
|--:|--:|--:|---|--:|
|  1,000 cases / day  |  3 |  5 | db.r6g.large (2 vCPU, 16 GB)    | ~$320  |
| 10,000 cases / day  |  6 | 25 | db.r6g.xlarge (4 vCPU, 32 GB)   | ~$1,200 |
|100,000 cases / day  | 20 | 80 | db.r6g.4xlarge (16 vCPU, 128GB) | ~$8,400 |

## Things production-grade you can verify in this YAML

- Rolling deploys with `maxUnavailable: 0` — no zero-replica window
- `terminationGracePeriodSeconds` separately tuned per tier (30s API, 60s worker — workers need longer to drain in-flight DAG runs)
- `preStop` sleep on API pods so the ALB deregisters them before the process exits
- IRSA per-pod-role — no node-level AWS perms
- NetworkPolicy locking egress to VPC-only — no PHI to public internet
- StickySessions on ALB for SSE streaming continuity
- PodDisruptionBudget ensuring ≥80% of workers stay up during voluntary disruptions
- Prometheus scrape annotations on API pods → `/metrics` is auto-discovered
