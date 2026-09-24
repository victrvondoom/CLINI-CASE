# ClinCase — Bedrock VPC Endpoint + IAM Terraform module

**Status: apply-ready** — `terraform plan` produces a clean diff.

This module realizes AWS's documented architectural guidance for governed
Bedrock access: **VPC endpoints + endpoint policies + per-model-id IAM
conditions**. Cited from [AWS Architecture blog — Amazon Bedrock category](https://aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/):

> *"Use API Gateway or equivalent as a governed entry point to Bedrock,
> with IAM, quotas, and network controls."*
> *"Consider VPC endpoints, VPC Lattice, and IAM policies to tightly
> control and monitor Bedrock access."*

## What this module provisions

1. **`aws_vpc_endpoint` for `bedrock-runtime`** (Interface endpoint, AWS
   PrivateLink) — ClinCase pods reach Bedrock without traversing the public
   internet. Combined with the existing K8s NetworkPolicy this gives
   defense-in-depth.

2. **`aws_vpc_endpoint` for `bedrock-agent-runtime`** — required when we
   port to AgentCore Runtime (`ops/aws/agentcore/deployment.yaml`).

3. **VPC endpoint policy** scoping access to:
   - Caller IAM principal = `clincase-bedrock-invoke-role`
   - `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`
   - **Per-model-id condition** restricting calls to the configured Sonnet +
     Haiku ARNs only. Any new model requires a Terraform change — exactly
     the gating a CISO wants.

4. **`aws_iam_role` `clincase-bedrock-invoke-role`** for the EKS pods
   (assumed via IRSA from the `clincase` namespace's ServiceAccount):
   - Trust policy: only the EKS OIDC issuer for the configured cluster.
   - Inline policy: `bedrock:InvokeModel*` on the configured models, plus
     `bedrock:ApplyGuardrail` on the configured Guardrail ARN.

5. **`aws_security_group`** for the VPC endpoint allowing 443 from the EKS
   node security group only. No 0.0.0.0/0 inbound.

6. **CloudWatch Logs export** of Bedrock model-invocation logs (input/output
   capture, redacted) — per-tenant prefix for evidence-pack reproduction.

## Apply order

```bash
cd ops/terraform/bedrock-vpc-endpoint

# 1. Backend bootstrap
terraform init \
  -backend-config="bucket=clincase-tfstate-aps1" \
  -backend-config="key=bedrock-vpc-endpoint/terraform.tfstate" \
  -backend-config="region=ap-south-1"

# 2. Plan
terraform plan -var-file=prod.tfvars

# 3. Apply
terraform apply -var-file=prod.tfvars
```

Apply this **BEFORE** the K8s `clincase-api` and `clincase-worker`
deployments — once it's live, those pods reach Bedrock via the VPC endpoint
automatically (the Bedrock SDK resolves the regional endpoint to the VPC
endpoint by DNS).

## Verifying the network path

After apply, from a worker pod:

```bash
kubectl exec -it deploy/clincase-worker -n clincase -- \
  python -c "
import boto3, urllib.request, socket
client = boto3.client('bedrock-runtime', region_name='ap-south-1')
# Resolve the endpoint hostname — should be the VPCe DNS, NOT the public bedrock.amazonaws.com
host = client.meta.endpoint_url.replace('https://', '').replace('http://', '').split('/')[0]
print(f'endpoint host: {host}')
print(f'resolved IP:   {socket.gethostbyname(host)}')
"
```

The resolved IP MUST be in your VPC CIDR (10.0.x.x), not a public AWS IP.

## Cost

| Item | Hourly | Monthly | Notes |
|---|--:|--:|---|
| Interface endpoint (bedrock-runtime) | $0.014 × 3 AZ | ~$30.66 | per-AZ pricing |
| Interface endpoint (bedrock-agent-runtime) | $0.014 × 3 AZ | ~$30.66 | per-AZ pricing |
| Data processing | $0.01 / GB | varies | typical ClinCase traffic ≈ 5 GB/day → ~$1.50/month |
| **Total incremental cost** | | **~$63/month** | for the AWS-blessed governance pattern |

## Files

| File | Purpose |
|---|---|
| `main.tf` | Terraform/providers/backend |
| `variables.tf` | Inputs: vpc_id, subnet_ids, security_group_ids, eks_cluster_name, allowed_model_arns, guardrail_arn |
| `vpc-endpoints.tf` | The two `aws_vpc_endpoint` resources + endpoint policy |
| `iam.tf` | `clincase-bedrock-invoke-role` with IRSA trust + per-model conditions |
| `security-group.tf` | The endpoint security group |
| `logs.tf` | CloudWatch Logs target for Bedrock model-invocation logging |
| `outputs.tf` | endpoint IDs, role ARN, log group ARN |
| `prod.tfvars.example` | Sample inputs |
