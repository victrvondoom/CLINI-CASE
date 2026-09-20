# ClinCase — PgBouncer (transaction pooling for Aurora)

**Status: apply-ready.**

PgBouncer multiplexes many client connections onto a small backend pool.
Without it, ClinCase's per-pod asyncpg pools blow past Aurora's
`max_connections` budget at ~5 cells × 50 pods × 10 conns = 2,500 conns —
double the default Aurora `max_connections` of 1,000 on `db.r7g.large`.

This module deploys two PgBouncer instances:
- **`pgbouncer-writer`** — fronts the Aurora primary; transaction pooling
- **`pgbouncer-reader`** — fronts the Aurora reader endpoint

ClinCase pods set `DATABASE_URL` and `DATABASE_READ_URL` to point at these
two services instead of Aurora directly. The reduction is dramatic:

| Layer | Connections (50 pods × 10 conns) |
|---|---:|
| Without PgBouncer | 500 conns Aurora-primary-side |
| With PgBouncer (transaction mode, 25 backends) | 25 conns Aurora-primary-side |
| **Aurora primary headroom** | **475 conns freed** |

## Deploy

```bash
kubectl apply -f ops/k8s/pgbouncer/configmap.yaml -n clincase
kubectl apply -f ops/k8s/pgbouncer/deployment.yaml -n clincase
kubectl apply -f ops/k8s/pgbouncer/service.yaml -n clincase

# Verify
kubectl get svc -n clincase pgbouncer-writer pgbouncer-reader
psql -h pgbouncer-writer.clincase.svc.cluster.local -U clincase -d clincase -c "SHOW POOLS;"
```

## Config

`pgbouncer.ini` highlights:
- `pool_mode = transaction`            — multiplex per-transaction
- `max_client_conn = 1000`             — front-end clients
- `default_pool_size = 25`             — back-end conns per (db,user)
- `reserve_pool_size = 5`              — burst capacity
- `server_reset_query = DISCARD ALL`   — avoid leaking session state
- `query_wait_timeout = 5`             — fast-fail when backend is exhausted
- `tls_mode = require`                 — encrypt the backend hop

## When to retire

- Move to **Amazon RDS Proxy** (managed PgBouncer-equivalent) at the first
  customer that requires native AWS managed services across the stack.
  Migration is config-only.

## Files

- `configmap.yaml`   — pgbouncer.ini + userlist.txt template (secrets via
                       External Secrets Operator)
- `deployment.yaml`  — writer + reader Deployments with PDB + HPA
- `service.yaml`     — pgbouncer-writer + pgbouncer-reader services
- `README.md`        — this file

## Sources

- PgBouncer docs — https://www.pgbouncer.org/
- AWS RDS Proxy alternative — https://aws.amazon.com/rds/proxy/
