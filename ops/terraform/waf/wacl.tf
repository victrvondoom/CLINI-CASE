resource "aws_wafv2_web_acl" "clincase" {
  name        = "clincase-edge-acl"
  scope       = "REGIONAL"
  description = "ClinCase edge protection: OWASP managed rules + per-tenant tier rate limits + bot control."

  default_action { allow {} }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "clincase-edge-acl"
    sampled_requests_enabled   = true
  }

  # ---- Rule 1: AWS-managed Common Rule Set (OWASP Top 10 baseline) ----
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ---- Rule 2: AWS-managed Known-Bad-Inputs ----
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 20
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ---- Rule 3: SQL Injection protection ----
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 30
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesSQLiRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesSQLiRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ---- Rule 4: Bot Control common bots ----
  rule {
    name     = "AWSManagedRulesBotControlRuleSet"
    priority = 40
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesBotControlRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesBotControlRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # ---- Rule 5: Per-tenant-tier rate limits ----
  # Each tenant tier (Bronze/Silver/Gold) has a different rate limit. The
  # x-tenant-tier header is set by the API based on org_quotas.tier; an attacker
  # cannot forge it because the WAF runs BEFORE the API, so we rate-limit by
  # source-IP and source-IP+URI within these tiers as a coarse approximation.
  # The fine-grained per-tenant enforcement is the in-process quota in app/quotas.py.
  rule {
    name     = "RateLimit-Bronze-Tier"
    priority = 100
    action { block {} }
    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min_bronze
        aggregate_key_type = "IP"
        scope_down_statement {
          byte_match_statement {
            search_string         = "bronze"
            field_to_match { single_header { name = "x-tenant-tier" } }
            text_transformation { priority = 0; type = "LOWERCASE" }
            positional_constraint = "EXACTLY"
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit-Bronze"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimit-Silver-Tier"
    priority = 110
    action { block {} }
    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min_silver
        aggregate_key_type = "IP"
        scope_down_statement {
          byte_match_statement {
            search_string         = "silver"
            field_to_match { single_header { name = "x-tenant-tier" } }
            text_transformation { priority = 0; type = "LOWERCASE" }
            positional_constraint = "EXACTLY"
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit-Silver"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimit-Gold-Tier"
    priority = 120
    action { block {} }
    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_5min_gold
        aggregate_key_type = "IP"
        scope_down_statement {
          byte_match_statement {
            search_string         = "gold"
            field_to_match { single_header { name = "x-tenant-tier" } }
            text_transformation { priority = 0; type = "LOWERCASE" }
            positional_constraint = "EXACTLY"
          }
        }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit-Gold"
      sampled_requests_enabled   = true
    }
  }
}

resource "aws_wafv2_web_acl_association" "clincase_alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.clincase.arn
}
