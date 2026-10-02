# Running CLINI-CASE on Kubernetes (local kind)

Kubernetes orchestrates the **whole application**, not a single feature: the nginx **frontend**, the FastAPI **api**, the independent Track 7 **receiver** (System B) and **PostgreSQL** (pgvector) run as four workloads in one namespace of a disposable local [kind](https://kind.sigs.k8s.io/) cluster. One command builds the images, creates the cluster, generates the secrets, deploys everything and waits until it is ready; a second command proves it works. Everything is local and free: no cloud account, registry or paid service is involved.

> **Scope.** This is a local portability and hardening showcase. It is not a production deployment and it is not evidence about EKS. See [Non-goals](#non-goals).

## Prerequisites

| Tool | Needed | Notes |
|---|---|---|
| Docker Desktop (engine running) | yes | Give it at least 4 GB of memory. Measured idle: the whole kind node, Kubernetes control plane included, uses about 1.5 GB; the four workloads add roughly 250 MB. |
| `kubectl` | yes | Any recent client (tested with v1.36). |
| `kind` | yes | A recent release whose default CNI (kindnet) enforces NetworkPolicy; v0.24 or newer is expected to, and `verify` proves it on yours. Tested with v0.33.0 (Kubernetes v1.37). Not on `PATH`? Pass `--kind <path>` or set `KIND`. |
| Python 3.11+ | yes | `k8s/cluster.py` uses only the standard library. `verify` also runs `backend/scripts/interop_demo.py`, so the interpreter it uses (`--python`, default: the one running the script) needs the backend dependencies: `pip install -e "backend[dev]"`. |
| Free host port | yes | The frontend is published on `127.0.0.1:8080`. If 8080 is taken, use `up --host-port 18080`; `verify` and `credentials` find the published port on their own. |

## One-command flow

PowerShell:

```powershell
python k8s/cluster.py up            # first run 15-30 min (node image, Python and npm builds); later runs ~1 min
python k8s/cluster.py verify        # PASS/FAIL table, exit code 1 on any failure
python k8s/cluster.py credentials   # writes the generated demo login to k8s/.cache/kind-login.json (git-ignored)
python k8s/cluster.py down          # deletes the cluster, its volumes and the generated Secret
```

bash (Git Bash, WSL, macOS, Linux):

```bash
python3 k8s/cluster.py up
python3 k8s/cluster.py verify
python3 k8s/cluster.py credentials
python3 k8s/cluster.py down
```

Then open <http://localhost:8080> and sign in as `reviewer@clincase.health` (or `admin@` / `coordinator@`) with the password printed by `credentials`.

| Command | What it does |
|---|---|
| `up [--skip-build] [--host-port N] [--build-ca PEM]` | Idempotent. Creates the cluster if absent, builds the images, loads the ones that changed, creates the Secret if absent, refreshes the schema ConfigMap, applies `k8s/`, restarts the app Deployments if an image changed, and waits for every rollout. `--build-ca` trusts one extra root certificate for pip/npm during the builds (TLS-inspecting antivirus or proxy; see Troubleshooting). |
| `verify [--python PATH]` | Live checks (below). Prints a table and exits non-zero on any failure. |
| `credentials` | Prints the demo e-mail and the generated password. Nothing else ever prints it. |
| `down` | `kind delete cluster --name clinicase`. Everything in the cluster, including the database volume, is gone. |

Every subcommand accepts `--kind PATH` (or `KIND`). Every `kubectl` call is pinned to the context `kind-clinicase`, so the script never touches whichever cluster happens to be current.

## Topology

```
 browser  http://localhost:8080
    |   127.0.0.1:8080 -> kind node :30080        (the only way in; loopback only)
    v
+---------------------------- namespace clinicase (Pod Security: restricted) --------------------------+
|                                                                                                       |
|  Service frontend  NodePort 30080 -> :5173                                                            |
|        |                                                                                              |
|        v                                                                                              |
|  Deployment frontend   nginx-unprivileged  clinicase-web:local        /healthz answered by nginx      |
|        |   /api/  /fhir/  /mcp   ->  http://api:8000                                                  |
|        v                                                                                              |
|  Deployment api        uvicorn app.main:app  clinicase-api:local                                      |
|        |-- 5432 -------->  StatefulSet postgres   pgvector/pgvector:pg16  (2Gi PVC)                   |
|        |-- 8091 -------->  Deployment receiver    clinicase-api:local     (System B, own SQLite)      |
|        |-- 5173 -------->  frontend  GET /healthz (live reachability for /api/v1/runtime)             |
|        `-- 443  -------->  public internet (optional LLM providers; private ranges excluded)          |
|                                                                                                       |
|  NetworkPolicy: default-deny ingress and egress, DNS to CoreDNS, and exactly the arrows above        |
+-------------------------------------------------------------------------------------------------------+
```

| Workload | Kind | Image | Port | Probes |
|---|---|---|---|---|
| `frontend` | Deployment | `clinicase-web:local` | 5173 (NodePort 30080) | `GET /healthz` (served by nginx itself) |
| `api` | Deployment | `clinicase-api:local` | 8000 | liveness `GET /api/v1/healthz`, readiness `GET /api/v1/readyz` (queries the database), startup probe on `/healthz` |
| `receiver` | Deployment | `clinicase-api:local` (same image, different command) | 8091 | `GET /healthz` |
| `postgres` | StatefulSet | `pgvector/pgvector:pg16` | 5432 | `pg_isready -h 127.0.0.1` |

`k8s/` holds the manifests: `namespace`, `serviceaccounts`, `configmap`, `postgres`, `receiver`, `api`, `frontend`, `networkpolicies` (applied through `kustomization.yaml`) and `kind-config.yaml` (cluster definition, not a resource). The Secret `clinicase-secrets` and the ConfigMap `clinicase-db-schema` are created by `cluster.py` and are deliberately not in git.

## What `up` does

1. Checks the Docker engine, then creates the kind cluster `clinicase` from `k8s/kind-config.yaml` (one node, `127.0.0.1:8080 -> 30080`).
2. Builds `clinicase-api:local` (`backend/Dockerfile`, used by the api **and** the receiver) and `clinicase-web:local` (`frontend/Dockerfile`), then loads them into the node, plus the PostgreSQL image when it is cached locally. Loading is `docker save --platform <your engine's platform>` into one archive followed by `kind load image-archive`: plain `kind load docker-image` fails with `ctr: content digest ... not found` on engines that use Docker's containerd image store (the default in recent Docker Desktop), and only after minutes. Images use `imagePullPolicy: Never`, so the node never pulls the local tags from a registry. The ids of the loaded images are recorded on the node, so an unchanged image is not loaded again and re-running `up` stays quick.
3. Applies the namespace, then creates the Secret `clinicase-secrets` **only if it does not exist** (random `secrets.token_urlsafe(32)` values for the database password, `DATABASE_URL`, `JWT_SECRET`, `INTEROP_RECEIVER_TOKEN` and `DEMO_USER_PASSWORD`; passed to `kubectl` on stdin, never on a command line, never written to disk). Re-running `up` therefore never rotates live credentials.
4. Creates or refreshes the ConfigMap `clinicase-db-schema` from `backend/db/schema.sql` (not committed as YAML), which PostgreSQL runs from `/docker-entrypoint-initdb.d` the first time it starts on an empty volume. The synthetic Track 7 payloads read by `POST /api/v1/interop/demo` ship inside the API image (`COPY data /app/data`); only the writable policy store (`/app/data/policies`) is mounted, so nothing hides them.
5. `kubectl apply -k k8s`, and `rollout restart` of the api, receiver and frontend when an image's content changed (a rebuilt image under the same `:local` tag is only picked up by new pods).
6. Waits for `postgres`, `receiver`, `api` and `frontend` to roll out, printing pods, events and logs if one does not become ready.

## What `verify` proves

It exits non-zero on any failure and prints one row per check:

| Check | Meaning |
|---|---|
| `web GET /healthz via NodePort` | The published port reaches nginx in the frontend pod. |
| `api GET /api/v1/healthz` and `/readyz` via nginx | The reverse proxy reaches the api, and the api can read its schema in PostgreSQL. |
| `auth POST login reviewer@clincase.health` | Seeded demo users exist and the password from the Secret works. |
| `api GET /api/v1/runtime` | The api reports `live: true`, the pod identity from the Downward API, and every peer (frontend, receiver, database) reachable from inside the cluster. |
| `Track 7 interop_demo.py over HTTP` | The full Track 7 story runs against the cluster and asserts `receiver_mode == "HTTP network"`: the api reaches the receiver Deployment over the cluster network. |
| `netpol frontend -> api:8000 allowed` | Control: the allowed edge works with the same probe tool. |
| `netpol frontend -> postgres:5432 denied` | The web tier cannot reach the database: the connection must fail, not merely be refused by the application. |
| `netpol api -> postgres:5432 allowed` | The api can. |
| `netpol receiver -> postgres:5432 denied` | System B cannot reach the evidence store. |

The password reaches the demo script through its environment, not its arguments, and is masked in any error text.

## Security posture

| Control | What the manifests do |
|---|---|
| Pod Security Admission | The namespace **enforces** the `restricted` profile (and warns/audits at the same level). All four workloads comply, including PostgreSQL: it runs as uid/gid/fsGroup 999 with `PGDATA` in a sub-directory of the volume. A pod that drifts from the baseline (root, added capabilities, privilege escalation, `hostPath`, ...) is rejected at admission. |
| Container hardening | Every container, init containers included: `runAsNonRoot`, non-zero numeric UID (api and receiver 10001, nginx 101, postgres 999), `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem: true`. The only writable paths are explicit `emptyDir`s (`/tmp`, `/app/data/policies`, `/data`, `/var/run/postgresql`) and the database PVC. CPU and memory requests and limits everywhere; no `latest` tags. |
| Identity | One ServiceAccount per workload, token not mounted (`automountServiceAccountToken: false` on the account and on every pod). There is **no Role, ClusterRole or binding anywhere and no cluster-admin**: nothing in the stack talks to the Kubernetes API, so it is granted nothing. |
| Network | Default-deny for ingress **and** egress, then an allow-list: DNS to CoreDNS; internet to the frontend on 5173; frontend to api:8000; api to postgres:5432, receiver:8091, frontend:5173 and public TCP 443 (RFC 1918 private and link-local ranges excluded); receiver and postgres accept connections from the api only and initiate none. |
| Secrets | Generated at `up`, kept only in the cluster's `clinicase-secrets`, never committed, never logged. `credentials` is the one explicit way to read the demo password. |
| Entry point | One NodePort, mapped by kind to the loopback interface only. |

Honest limits: Kubernetes Secrets in kind are base64 in etcd, not encrypted at rest; traffic is plain HTTP on loopback with no TLS or mTLS; `ENVIRONMENT=dev` enables the seeded demo users; there is no image scanning or signing, no admission policy engine beyond Pod Security Admission, and one replica of everything.

NetworkPolicy is only a promise if the CNI keeps it. `verify` therefore tests it instead of trusting it: it opens a TCP connection from the frontend pod to PostgreSQL and expects it to fail, and one from the api pod and expects it to succeed. If the cluster's CNI did not enforce policy, the denied row would report `FAIL ... NetworkPolicy is NOT enforced`.

What was observed on a real run (kind v0.33.0, Kubernetes v1.37, kindnet `v20260820` with its built-in `kube-network-policies` engine, Windows 11 and Docker Desktop 29.8):

- **Pod Security Admission:** all four workloads were admitted under `enforce: restricted`, `kubectl apply` printed no Pod Security warnings, and `kubectl label --dry-run=server --overwrite ns clinicase pod-security.kubernetes.io/enforce=restricted` reported nothing, which is the API server's own check that no running pod violates the profile. Inside the running containers: api and receiver run as uid 10001, nginx as 101 and PostgreSQL as 999; writes outside the emptyDirs fail with "Read-only file system"; `CapEff` is 0, `NoNewPrivs` is 1 and seccomp is in filter mode.
- **NetworkPolicy:** the denied edges really were blocked (the connection timed out) and the allowed ones connected, so kindnet enforces policy here. frontend to postgres, receiver to postgres, receiver to api, frontend to receiver and frontend to the internet were all blocked. api to postgres, receiver and frontend connected. api to a public address on 443 connected, while api to the in-cluster API server Service (`10.96.0.1:443`) and api to a public address on port 80 were blocked, which is the private-range exclusion and the port restriction doing their job.
- **Probes and entry point under default-deny:** kubelet HTTP probes and the NodePort path worked without any extra allow rules.

## The `/runtime` page when deployed

The api exposes `GET /api/v1/runtime` (authenticated), which the `/runtime` page renders. Inside this cluster it reports the label **Live cluster topology** and `live: true`. Everything comes from the pod's own environment and probes of server-configured endpoints, never from anything the browser sends:

- **Identity** from the Downward API variables `POD_NAME`, `POD_NAMESPACE`, `NODE_NAME` and `POD_IP`, plus `RUNTIME_PLATFORM=kind`.
- **Images** from the ConfigMap: `CLINICASE_IMAGE`, `RUNTIME_FRONTEND_IMAGE` and `RUNTIME_RECEIVER_IMAGE`.
- **Reachability**: `GET /healthz` against `RUNTIME_FRONTEND_URL` (`http://frontend:5173`) and against `INTEROP_RECEIVER_URL` (`http://receiver:8091`), and a `SELECT 1` against PostgreSQL. This is why the api's egress policy includes `frontend:5173`.

No CPU, memory, replica or cloud metrics are collected. Run outside Kubernetes (compose or a plain process) the same page is labelled **Deployment topology**.

## Day-2 operations

```bash
kubectl --context kind-clinicase -n clinicase get pods,svc,networkpolicy
kubectl --context kind-clinicase -n clinicase logs deploy/api
kubectl --context kind-clinicase -n clinicase rollout restart deployment/api   # after editing k8s/configmap.yaml and re-running up --skip-build
```

- **Ship a code change:** run `python k8s/cluster.py up` again. Docker's layer cache keeps unchanged builds fast; the app Deployments restart only if an image actually changed.
- **Re-apply manifests only:** `up --skip-build` (the images must already exist locally).
- **Schema:** PostgreSQL loads `backend/db/schema.sql` only on the first start of an empty volume (the api also runs its own idempotent schema bootstraps at startup). For a clean database run `down` then `up`, or delete the StatefulSet and the PVC `data-postgres-0`.
- **Data lifetime:** PostgreSQL data survives pod restarts and `up`; the receiver's receipts live in an `emptyDir` and survive container restarts but not pod re-creation. `down` removes everything.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `up` stops with "host port 8080 is already in use" | Another program owns 8080 (a common one). Run `up --host-port 18080`; `verify` and `credentials` detect the published port from Docker. |
| `docker build` fails in `pip install` or `npm ci` with `CERTIFICATE_VERIFY_FAILED` / `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | An antivirus or proxy re-signs HTTPS (for example AVG/Avast Web Shield or Zscaler) with a root certificate that the build containers do not trust. Export that **root certificate** (public part only) as PEM and run `up --build-ca <file.pem>` (or set `CLINICASE_BUILD_CA`). The certificate is used only by pip and npm during the build, is never added to a system trust store, and the repository's Dockerfiles are untouched. Do not push images built this way. PowerShell example: `$c = Get-ChildItem Cert:\LocalMachine\Root \| Where-Object Subject -like "*Shield Root*" \| Select-Object -First 1; "-----BEGIN CERTIFICATE-----`n$([Convert]::ToBase64String($c.RawData,'InsertLineBreaks'))`n-----END CERTIFICATE-----" \| Set-Content -Encoding ascii root.pem`. |
| `kubectl` intermittently says `x509: certificate signed by unknown authority` for `127.0.0.1:<port>` | The same class of problem: an antivirus re-signs the loopback connection to the kind API server (seen with AVG, in windows that lasted from under a minute to over five, typically after a build or an image load; `openssl s_client` then shows an issuer like "AVG Web/Mail Shield Untrusted Root"). `cluster.py` detects it and runs its own `kubectl` calls through the `kubectl` inside the kind node (`docker exec`), which reaches the API server over the node's loopback, for the rest of that run. For manual use: `docker exec -i clinicase-control-plane kubectl --kubeconfig /etc/kubernetes/admin.conf get pods -A`, or retry in a minute, or add the antivirus's HTTPS-scanning exception for `127.0.0.1`. |
| Pod `ErrImageNeverPull` | The image is not in the node; the manifests deliberately never pull `:local` images. Re-run `up`, which loads images that are new or changed. If `up` says "images already on the node" but the pod still cannot find one, clear the load record with `kubectl annotate node clinicase-control-plane clinicase.local/image-ids-` and run `up` again. |
| `postgres-0` stays `Pending` / the PVC is `Pending` | kind's default StorageClass `standard` uses `WaitForFirstConsumer`, so the claim binds only when the pod is scheduled. If it stays pending, check `kubectl get sc` shows `standard (default)` and that Docker has free disk. |
| `postgres-0` is `ContainerCreating` with "configmap clinicase-db-schema not found" | The manifests were applied without the orchestrator. Run `python k8s/cluster.py up`, which creates the ConfigMap first. |
| `readyz` returns 503 and the api pod is not Ready | The api cannot query its schema yet. Normally transient on first boot (PostgreSQL is still loading `schema.sql`; the init container and readiness probe hold traffic back). If it persists, check `kubectl logs statefulset/postgres` and `kubectl logs deploy/api`. |
| api logs "password authentication failed" | The Secret and the database volume disagree, which happens if `clinicase-secrets` was deleted but the PVC kept. Run `down` then `up`. |
| `verify` reports `NetworkPolicy is NOT enforced` | The cluster's CNI does not implement NetworkPolicy. Use kind v0.24+ with its default CNI. |
| `POST /api/v1/interop/demo` returns 500 with `FileNotFoundError: /app/data/interop/environmental.json` | The API image predates `COPY data /app/data` in `backend/Dockerfile`, or something was mounted over `/app/data`. Rebuild with `python k8s/cluster.py up` (without `--skip-build`). |
| `interop_demo.py exit 1` in `verify` | The host interpreter is missing backend dependencies (`pip install -e "backend[dev]"` or pass `--python`), or a Retry-After rate limit was hit; re-run `verify`. |
| `kubectl` says the context does not exist | The cluster is not running. `python k8s/cluster.py up`. |
| Slow first start | The api imports a large dependency tree on a throttled node; the startup probe allows up to 3 minutes before liveness applies. |

## Non-goals

- No Horizontal Pod Autoscaler, KEDA, service mesh, Kafka, Terraform, Helm or GitOps tooling.
- No cloud: no EKS, ECR, RDS or managed Kubernetes of any kind, and no registry; images are built locally and loaded into kind.
- Local only and disposable. It is not a production reference, not a compliance claim and not evidence of how the existing `ops/k8s` (EKS) material behaves.
- No new Bedrock or other model-provider integration; LLM egress (TCP 443) is optional and unused by the demo path.
