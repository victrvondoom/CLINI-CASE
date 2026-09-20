# ClinCase — Argo CD GitOps bootstrap

**Status: apply-ready.**

Replaces the `kubectl apply` deploy story with declarative, reviewable,
auditable GitOps via Argo CD.

## Why GitOps

Round-9 deploy story was: SRE runs `kubectl apply -f ops/k8s/`. Wrong because:

1. **No audit trail** — `who deployed what, when` is nowhere to be found.
2. **Drift** — production resources can be modified out-of-band.
3. **No declarative rollback** — rollback means "find the previous YAML and reapply."
4. **No promotion model** — staging → prod requires re-running scripts.

Argo CD inverts this:
- **Git is the source of truth.** Cluster state SYNCS from git, not vice versa.
- **Drift is detected automatically.** Argo CD's UI shows red whenever cluster diverges.
- **Rollback = git revert.** No magic.
- **Promotion = PR.** Staging → prod is a PR moving the image tag.

## Pattern: App of Apps

Argo CD's well-known pattern for managing many apps. One root Application
manages a folder of child Applications:

```
clincase-root (Application)
   │
   ├─► clincase-api          (Application)
   ├─► clincase-worker       (Application)
   ├─► clincase-postgres-ha  (Application — Helm chart)
   ├─► linkerd              (Application — Helm chart, round 10)
   ├─► keda                 (Application — Helm chart, round 11)
   ├─► postgres-exporter    (Application — Helm chart for /metrics)
   └─► argocd-image-updater (Application — auto-tag-bump on new images)
```

Adding a new component = adding one YAML file under `ops/argocd/applications/`.
The root app sees the new file and creates the new Application automatically.

## Bootstrap (one-time)

```bash
# 1. Install Argo CD itself
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.12.4/manifests/install.yaml

# 2. Apply the root Application
kubectl apply -n argocd -f ops/argocd/app-of-apps.yaml

# 3. Open the UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# admin password:
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
```

## Promotion model

| Branch | Cluster | Auto-sync |
|---|---|---|
| `main` | staging | ✅ — every push |
| `prod` | prod    | ❌ — manual sync only (SRE clicks "Sync") |

The `prod` branch is fast-forwarded from `main` after staging soak. No PR's
ever target `prod` directly — promotion is a `git push prod main:prod`.

## Files

- `app-of-apps.yaml` — the root Application
- `applications/clincase-api.yaml` — API deployment
- `applications/clincase-worker.yaml` — worker deployment
- `applications/keda.yaml` — KEDA Helm chart
- `applications/linkerd.yaml` — Linkerd Helm chart (round 10)

## Sources

- Argo CD docs — https://argo-cd.readthedocs.io/
- App of Apps pattern — https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/
- Argo CD Image Updater — https://argocd-image-updater.readthedocs.io/
