# ─── CloudWatch alarms on Bedrock provisioned-throughput utilization ────────
# When utilization climbs we want to know BEFORE Bedrock starts throttling.
# Two-tier alarming:
#   • 80% sustained 5m → P3 (someone gets paged during business hours)
#   • 95% sustained 2m → P2 (PagerDuty fires immediately)

locals {
  primary_alarm_dims = {
    sonnet = "clincase-sonnet-${var.primary_region}"
    haiku  = "clincase-haiku-${var.primary_region}"
  }
}

# --- Sonnet P3 (80%) --------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "sonnet_p3" {
  provider            = aws.primary
  alarm_name          = "clincase-bedrock-sonnet-utilization-p3-${var.primary_region}"
  alarm_description   = "Sonnet provisioned throughput at >${var.utilization_p3_threshold}% — review burn rate."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 5
  metric_name         = "InvocationLatency"  # placeholder — actual TPM utilization metric is provided per-MU under AWS/Bedrock namespace
  namespace           = "AWS/Bedrock"
  period              = 60
  statistic           = "Average"
  threshold           = var.utilization_p3_threshold
  alarm_actions       = [var.alarm_sns_topic_arn]
  ok_actions          = [var.alarm_sns_topic_arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    ProvisionedModelArn = aws_bedrock_provisioned_model_throughput.sonnet_primary.provisioned_model_arn
  }

  tags = { Severity = "P3" }
}

# --- Sonnet P2 (95%) --------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "sonnet_p2" {
  provider            = aws.primary
  alarm_name          = "clincase-bedrock-sonnet-utilization-p2-${var.primary_region}"
  alarm_description   = "Sonnet provisioned throughput at >${var.utilization_p2_threshold}% — capacity exhaustion imminent."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "InvocationLatency"
  namespace           = "AWS/Bedrock"
  period              = 60
  statistic           = "Average"
  threshold           = var.utilization_p2_threshold
  alarm_actions       = [var.alarm_sns_topic_arn]
  ok_actions          = [var.alarm_sns_topic_arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    ProvisionedModelArn = aws_bedrock_provisioned_model_throughput.sonnet_primary.provisioned_model_arn
  }

  tags = { Severity = "P2" }
}

# --- Haiku P3 (80%) ---------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "haiku_p3" {
  provider            = aws.primary
  alarm_name          = "clincase-bedrock-haiku-utilization-p3-${var.primary_region}"
  alarm_description   = "Haiku provisioned throughput at >${var.utilization_p3_threshold}%."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 5
  metric_name         = "InvocationLatency"
  namespace           = "AWS/Bedrock"
  period              = 60
  statistic           = "Average"
  threshold           = var.utilization_p3_threshold
  alarm_actions       = [var.alarm_sns_topic_arn]
  ok_actions          = [var.alarm_sns_topic_arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    ProvisionedModelArn = aws_bedrock_provisioned_model_throughput.haiku_primary.provisioned_model_arn
  }

  tags = { Severity = "P3" }
}
