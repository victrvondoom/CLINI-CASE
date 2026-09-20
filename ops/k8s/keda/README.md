# ClinCase — KEDA queue-depth autoscaler

**Status: apply-ready.** Pairs the worker Deployment with a `ScaledObject`
that reads the case_jobs queue depth from Postgres and scales workers
accordingly.

## Why we needed KEDA

Round-9 worker deployment had a fixed replica count (e.g., 5). That's
correct under steady load. It is **broken** under burst:

- Queue depth doubles → wait time doubles → SLO 4 (case-completion
  latency) busts.
- Manual scale-up requires SRE intervention every time.
- HPA can scale on CPU but not on queue depth (the actual signal that
  matters for asynchronous workloads).

KEDA is the standard pattern for "scale workers on queue depth."

## What this provisions

| Resource | Purpose |
|---|---|
| `ScaledObject/clincase-worker` | Tells KEDA to scale the `clincase-worker` Deployment based on Postgres queue depth |
| `TriggerAuthentication/clincase-postgres` | KEDA reads DB credentials from `clincase-secrets` |
| `Trigger: postgresql` | Polls `SELECT COUNT(*) FROM case_jobs WHERE status='queued'` every 30s |

## Scaling policy

- **Min replicas:** 2 (always one warm pod for fast cold-start)
- **Max replicas:** 50 (per-cell soft cap; matches Aurora connection budget)
- **Trigger threshold:** 5 queued jobs per pod. Above this → add pods.
- **Cooldown:** 300s (avoid flap)
- **Polling interval:** 30s

Math: a worker processes ~1 case / 60s end-to-end. 5 queued jobs / pod = ~5
minute backlog. Beyond that the SLO bell rings, so we scale up.

## Apply

```bash
# Pre-flight: KEDA must already be installed in the cluster
kubectl get deployment -n keda keda-operator || \
    helm upgrade --install keda kedacore/keda \
      --namespace keda --create-namespace

kubectl apply -f ops/k8s/keda/scaledobject-worker.yaml -n clincase

# Verify
kubectl get scaledobject -n clincase
kubectl get hpa -n clincase                # KEDA creates an HPA under the hood
```

## Verification

```bash
# Inflate the queue with a synthetic burst
for i in $(seq 1 100); do
  curl -X POST $API/api/v1/cases -H "Authorization: Bearer $TOKEN" \
       -d '{"patient_initials": "T.S.", ...}'
done

# Watch the worker deployment scale
kubectl get pods -l app=clincase-worker -n clincase --watch
```

## Trigger conditions to retire this

- Move workers to AWS Lambda / Fargate Spot — KEDA goes away (Lambda autoscales natively)
- Move queue to AWS SQS — `postgresql` trigger swaps for `aws-sqs-queue` trigger

## Files

- `scaledobject-worker.yaml` — the KEDA ScaledObject + TriggerAuthentication
- `README.md` — this file

## Sources

- KEDA — https://keda.sh/
- KEDA Postgres scaler — https://keda.sh/docs/latest/scalers/postgresql/
- AWS EKS + KEDA reference — https://aws.amazon.com/blogs/containers/microservices-deployment-on-amazon-eks-using-keda-and-fargate/
