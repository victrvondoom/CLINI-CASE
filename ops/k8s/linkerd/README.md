# ClinCase — Linkerd Service Mesh Install Path

**Status: apply-ready, currently NOT installed.**

This directory closes the gap between [`ops/architecture/SERVICE_MESH_DECISION.md`](../../architecture/SERVICE_MESH_DECISION.md) (the "when to add it" doc) and *"the Helm command to actually install it when one of the trigger conditions hits."*

## When to install (recap from the decision record)

Install only when ONE of these signals appears:

1. Service count crosses 10 (today: 2 — api + worker)
2. A Cognizant Gold-tier customer asks for SPIFFE workload identity
3. Inter-cluster traffic emerges (multi-region active/active needs cross-cluster service discovery)
4. L7 traffic shaping becomes critical (canary at the % level, traffic mirroring)
5. OpenTelemetry coverage falls below 80% of inter-service calls

## Why Linkerd (not Istio Ambient or AWS App Mesh)

See [`SERVICE_MESH_DECISION.md`](../../architecture/SERVICE_MESH_DECISION.md) § "Recommended mesh." Short version:

- **Linkerd** = simpler control plane, lighter sidecars (~10MB), Rust-based proxy. Easier to operate at our team size.
- Istio Ambient is the right call at 50+ services. We're nowhere near that.
- AWS App Mesh ties us deeper to AWS-only and is being de-emphasized by AWS in favor of EKS-native options.

## Install (when trigger fires)

### Step 1: install Linkerd CLI

```bash
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | sh
export PATH=$PATH:$HOME/.linkerd2/bin
linkerd version
```

### Step 2: pre-flight check

```bash
linkerd check --pre
```

Should report all green. If not, fix before installing.

### Step 3: install the CRDs

```bash
linkerd install --crds | kubectl apply -f -
```

### Step 4: install the control plane

```bash
helm upgrade --install linkerd-control-plane linkerd/linkerd-control-plane \
    --namespace linkerd \
    --create-namespace \
    --values ops/k8s/linkerd/values.yaml \
    --wait
```

### Step 5: verify

```bash
linkerd check                                     # all green
linkerd viz install | kubectl apply -f -          # observability dashboard
linkerd viz dashboard                             # opens dashboard locally
```

### Step 6: enroll ClinCase namespace

```bash
kubectl annotate namespace clincase linkerd.io/inject=enabled
kubectl rollout restart deploy -n clincase          # pods come back with sidecars
```

### Step 7: enforce mTLS

After observing for a week with mTLS in permissive mode:

```bash
kubectl apply -f ops/k8s/linkerd/mtls-strict-policy.yaml
```

## Files

- `values.yaml` — Helm values for the first install (HA control plane, restricted egress)
- `mtls-strict-policy.yaml` — `Server` + `MeshTLSAuthentication` resources to enforce mTLS-only between pods (apply at Step 7)
- `service-profile.yaml` — `ServiceProfile` for `clincase-api` (per-route timeout + retry budget)

## Cost impact

| Item | Per-pod overhead |
|---|---|
| `linkerd-proxy` sidecar memory | +30-50 MB |
| `linkerd-proxy` sidecar CPU | +50m baseline |
| Latency per service hop | +1-3ms (Linkerd's Rust proxy is the fastest in the category) |

At our 2-replica × 2-tier = 4-pod baseline: ~+200MB cluster memory, ~+200m CPU. Negligible at our scale; will matter at 100+ pods.

## What this does NOT do

- Does NOT install observability (Prometheus + Grafana) — we use the existing `/metrics` endpoint
- Does NOT install Linkerd Jaeger — we use OpenTelemetry already
- Does NOT enforce mTLS on day 1 — that's Step 7 after observation

## Rollback

```bash
kubectl annotate namespace clincase linkerd.io/inject-
kubectl rollout restart deploy -n clincase
helm uninstall linkerd-control-plane -n linkerd
linkerd uninstall | kubectl delete -f -
```
