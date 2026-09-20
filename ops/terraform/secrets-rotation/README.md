# ClinCase — AWS Secrets Manager rotation Terraform

**Status: apply-ready stub.**

Provisions AWS Secrets Manager rotation Lambdas for the long-lived
secrets that today never rotate in production. Required by:

- HIPAA § 164.308(a)(5)(ii)(D) — *Password Management*
- NIST 800-53 IA-5 — *Authenticator Management*
- SOC 2 CC6.1 — *Logical access security software*

## What rotates

| Secret | Schedule | Rotator |
|---|---|---|
| `clincase/jwt-secret`        | 30d | `rotation_jwt.py` (mints new HS256 key, deploys with grace overlap) |
| `clincase/postgres-master`   | 30d | AWS-managed `SecretsManagerRDSPostgreSQLRotationSingleUser` |
| `clincase/bedrock-iam-key`   | 90d | AWS-managed Lambda + IAM access key rotation |
| `clincase/trizetto-mtls-cert`| 365d | cert-manager + Let's Encrypt (referenced; lives separately) |
| `clincase/oidc-client-secret`| 365d | Manual (customer's IdP team rotates; we just store the new value) |

## Why we needed this

Round-9 deploy reads JWT_SECRET, DATABASE_URL, etc. from K8s Secrets, which
are populated from AWS Secrets Manager via External Secrets Operator. The
*values* never rotate. A leaked JWT_SECRET stays leaked forever.

This module wires automatic rotation. The application reads from Secrets
Manager via External Secrets Operator → K8s Secret → environment variable.
Rotation Lambda updates the Secrets Manager value → ESO syncs the K8s
Secret within 60s → next pod restart picks up the new value.

For zero-downtime rotation we use the **two-secret pattern**: each pod can
verify with EITHER the previous or the current key for a 24h grace window.

## Apply

```bash
cd ops/terraform/secrets-rotation
terraform init -backend-config=backend.tfvars
terraform apply -var-file=prod.tfvars
```

Provisions the secret + the rotation Lambda in one apply.

## Files

- `main.tf` — providers + backend
- `variables.tf` — environment + retention
- `secrets.tf` — secret definitions + rotation schedules
- `lambda.tf` — Lambda functions (one per secret type)
- `iam.tf` — Lambda execution role + secret-access policies
- `outputs.tf` — secret ARNs

## Sources

- AWS — *Rotating AWS Secrets Manager secrets* — https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html
- AWS-provided rotation Lambdas — https://github.com/aws-samples/aws-secrets-manager-rotation-lambdas
- HIPAA Security Rule § 164.308 — https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html
