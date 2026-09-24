"""End-to-end test of policy upload/list/delete/restore/purge against the
deployed ALB. Mints a JWT via the local backend (which has the seeded users)
and uses it against the public ALB (which shares the JWT_SECRET)."""
import json
import sys
import time

import requests
sys.stdout.reconfigure(encoding="utf-8")

LOCAL = "http://localhost:8000/api/v1"
ALB = "http://clincase-alb-729293716.us-east-1.elb.amazonaws.com/api/v1"

# 1. Login locally to get a JWT
tok = requests.post(
    f"{LOCAL}/auth/login",
    json={"email": "admin@clincase.health", "password": "clincase2026"},
    timeout=5,
).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
print(f"got JWT (len={len(tok)})")

# 2. Use that JWT against the deployed ALB
print("\n=== ALB list (no policies yet) ===")
r = requests.get(f"{ALB}/policies/list", headers=H, timeout=15)
print(f"  HTTP {r.status_code}")
print(f"  {json.dumps(r.json(), indent=2)[:300]}")

# 3. Upload a policy via ALB → real S3 → real bucket
print("\n=== ALB upload to REAL S3 (via ECS task running on AWS) ===")
real_pdf = b"%PDF-1.4\n" + b"AWS-deployed test policy. " * 80 + b"\n%%EOF"
up = requests.post(
    f"{ALB}/policies/upload",
    headers=H,
    files={"file": ("alb_uploaded.pdf", real_pdf, "application/pdf")},
    data={"payer_id": "uhc", "policy_title": "ALB-Deployed Test"},
    timeout=30,
)
print(f"  HTTP {up.status_code}")
print(json.dumps(up.json(), indent=2))
key = up.json().get("policy_key")

# 4. List
print("\n=== ALB list (after upload) ===")
ls = requests.get(f"{ALB}/policies/list", headers=H, timeout=15).json()
print(f"  backend={ls['backend']}  bucket={ls['bucket']}  n={ls['n']}")
for p in ls["policies"][:5]:
    print(f"  - {p['title']} ({p['size_bytes']} B) -> {p['s3_uri']}")

# 5. Delete (move to trash via ALB)
if key:
    print("\n=== ALB delete (real S3 .trash/) ===")
    de = requests.delete(f"{ALB}/policies/{key}", headers=H, timeout=15)
    print(f"  HTTP {de.status_code}")
    print(json.dumps(de.json(), indent=2))

    # 6. Trash list
    print("\n=== ALB trash ===")
    tr = requests.get(f"{ALB}/policies/trash", headers=H, timeout=15).json()
    print(f"  n={tr['n']}")
    for p in tr["policies"][:3]:
        print(f"  - {p['title']} trashed_at={p['trashed_at']}")

    # 7. Restore
    print("\n=== ALB restore ===")
    rs = requests.post(f"{ALB}/policies/trash/{key}/restore", headers=H, timeout=15)
    print(f"  HTTP {rs.status_code}  {rs.json().get('message', '')}")

    # 8. Cleanup
    print("\n=== ALB final cleanup (delete + purge) ===")
    requests.delete(f"{ALB}/policies/{key}", headers=H, timeout=15)
    pu = requests.delete(f"{ALB}/policies/trash/{key}/purge", headers=H, timeout=15)
    print(f"  HTTP {pu.status_code}  {pu.json().get('message', '')}")

print("\n=== final state ===")
ls = requests.get(f"{ALB}/policies/list", headers=H, timeout=15).json()
tr = requests.get(f"{ALB}/policies/trash", headers=H, timeout=15).json()
print(f"  active={ls['n']}, trash={tr['n']}")
