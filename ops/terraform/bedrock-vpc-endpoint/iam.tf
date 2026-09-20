# =============================================================================
# IRSA role — pods invoking Bedrock
# =============================================================================
#
# Trust policy: ONLY the EKS OIDC issuer for the configured cluster, AND
# ONLY the listed ServiceAccounts in the configured namespace. No node-level
# AWS perms — every Bedrock call is attributable to an exact pod identity.
#
# Inline policy: per-model-id condition restricting InvokeModel to the
# allowlist. Combined with the endpoint policy in vpc-endpoints.tf this is
# defense in depth — both layers must allow the call.

data "aws_iam_policy_document" "bedrock_invoke_assume_role" {
  statement {
    sid     = "TrustOnlyClinCasePodsViaIRSA"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.oidc_provider}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:sub"
      values   = [for sa in var.k8s_service_accounts : "system:serviceaccount:${var.k8s_namespace}:${sa}"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bedrock_invoke" {
  name               = "clincase-bedrock-invoke-role"
  assume_role_policy = data.aws_iam_policy_document.bedrock_invoke_assume_role.json
  description        = "IRSA role for ClinCase API + worker pods to invoke Bedrock through the VPC endpoint."
  tags               = { Name = "clincase-bedrock-invoke-role" }
}

data "aws_iam_policy_document" "bedrock_invoke_inline" {
  statement {
    sid    = "InvokeAllowedModelsOnly"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = var.allowed_model_arns
  }

  statement {
    sid    = "ApplyConfiguredGuardrail"
    effect = "Allow"
    actions = ["bedrock:ApplyGuardrail"]
    resources = var.guardrail_arn != "" ? [var.guardrail_arn] : ["*"]
  }

  statement {
    sid    = "ReadOnlyDescribeForObservability"
    effect = "Allow"
    actions = [
      "bedrock:GetModelInvocationLoggingConfiguration",
      "bedrock:ListFoundationModels",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenyAnyMutatingBedrockAdmin"
    effect = "Deny"
    actions = [
      "bedrock:CreateModelCustomizationJob",
      "bedrock:UpdateGuardrail",
      "bedrock:DeleteGuardrail",
      "bedrock:CreateProvisionedModelThroughput",
      "bedrock:DeleteProvisionedModelThroughput",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name   = "clincase-bedrock-invoke-inline"
  role   = aws_iam_role.bedrock_invoke.id
  policy = data.aws_iam_policy_document.bedrock_invoke_inline.json
}
