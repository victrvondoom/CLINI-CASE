# =============================================================================
# Bedrock Interface VPC Endpoints (PrivateLink)
# =============================================================================
#
# Two endpoints — runtime + agent-runtime. The endpoint policy below scopes
# what *any* IAM principal connecting through this endpoint can do:
#   - Only InvokeModel + InvokeModelWithResponseStream + ApplyGuardrail
#   - Only the configured allowed_model_arns (per-model-id condition)
#
# This is one of two enforcement layers. The other is the IAM role assumed
# by the EKS pods (see iam.tf) — defense in depth.

resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.bedrock_vpce.id]
  private_dns_enabled = true   # so SDK resolves `bedrock-runtime.*.amazonaws.com` to the VPCe

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowClinCaseInvokeOnAllowedModels"
        Effect    = "Allow"
        Principal = "*"   # narrowed by IAM role; redundant deny default applies
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = var.allowed_model_arns
      },
      {
        Sid       = "AllowApplyGuardrail"
        Effect    = "Allow"
        Principal = "*"
        Action    = "bedrock:ApplyGuardrail"
        Resource  = var.guardrail_arn != "" ? [var.guardrail_arn] : ["*"]
      },
      {
        Sid       = "DenyAllOtherActions"
        Effect    = "Deny"
        Principal = "*"
        NotAction = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ApplyGuardrail",
        ]
        Resource = "*"
      },
    ]
  })

  tags = { Name = "clincase-bedrock-runtime-vpce" }
}

resource "aws_vpc_endpoint" "bedrock_agent_runtime" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-agent-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [aws_security_group.bedrock_vpce.id]
  private_dns_enabled = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAgentCoreAndKBRetrieve"
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "bedrock:InvokeAgent",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
        ]
        Resource = "*"
      },
    ]
  })

  tags = { Name = "clincase-bedrock-agent-runtime-vpce" }
}
