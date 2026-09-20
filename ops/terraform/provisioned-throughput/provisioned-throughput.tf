# ─── aws_bedrock_provisioned_model_throughput resources ─────────────────────
# Each resource binds an inference profile (Sonnet, Haiku) to N model units
# in a region. Allocation takes ~10 minutes; the resource is ready when its
# `status` reaches "InService". Until then, on-demand TPM still serves traffic.

# --- Primary region — Sonnet 4.6 --------------------------------------------

resource "aws_bedrock_provisioned_model_throughput" "sonnet_primary" {
  provider                          = aws.primary
  provisioned_model_name            = "clincase-sonnet-${var.primary_region}"
  model_arn                         = "arn:aws:bedrock:${var.primary_region}::foundation-model/${var.sonnet_model_id}"
  model_units                       = var.sonnet_model_units_primary
  commitment_duration               = var.commitment_duration == "" ? null : var.commitment_duration

  tags = {
    Tier  = "production"
    Model = "sonnet-4-6"
  }

  lifecycle {
    # Re-provisioning a model unit is destructive (releases capacity, then
    # waits ~10 min for re-allocation). Require explicit operator action by
    # setting prevent_destroy. Override via -replace if you really mean it.
    prevent_destroy = true
  }
}

# --- Primary region — Haiku 4.5 ---------------------------------------------

resource "aws_bedrock_provisioned_model_throughput" "haiku_primary" {
  provider                          = aws.primary
  provisioned_model_name            = "clincase-haiku-${var.primary_region}"
  model_arn                         = "arn:aws:bedrock:${var.primary_region}::foundation-model/${var.haiku_model_id}"
  model_units                       = var.haiku_model_units_primary
  commitment_duration               = var.commitment_duration == "" ? null : var.commitment_duration

  tags = {
    Tier  = "production"
    Model = "haiku-4-5"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# --- Secondary region (optional) --------------------------------------------

resource "aws_bedrock_provisioned_model_throughput" "sonnet_secondary" {
  count                             = var.enable_secondary_region ? 1 : 0
  provider                          = aws.secondary
  provisioned_model_name            = "clincase-sonnet-${var.secondary_region}"
  # NOTE: in non-apac regions the model_id prefix differs — e.g. "us." instead
  # of "apac.". The variable default carries the apac prefix; override it in
  # prod.tfvars when enable_secondary_region=true and secondary_region is in US/EU.
  model_arn                         = "arn:aws:bedrock:${var.secondary_region}::foundation-model/${replace(var.sonnet_model_id, "apac.", "us.")}"
  model_units                       = var.sonnet_model_units_secondary
  commitment_duration               = var.commitment_duration == "" ? null : var.commitment_duration

  tags = {
    Tier  = "production-failover"
    Model = "sonnet-4-6"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_bedrock_provisioned_model_throughput" "haiku_secondary" {
  count                             = var.enable_secondary_region ? 1 : 0
  provider                          = aws.secondary
  provisioned_model_name            = "clincase-haiku-${var.secondary_region}"
  model_arn                         = "arn:aws:bedrock:${var.secondary_region}::foundation-model/${replace(var.haiku_model_id, "apac.", "us.")}"
  model_units                       = var.haiku_model_units_secondary
  commitment_duration               = var.commitment_duration == "" ? null : var.commitment_duration

  tags = {
    Tier  = "production-failover"
    Model = "haiku-4-5"
  }

  lifecycle {
    prevent_destroy = true
  }
}
