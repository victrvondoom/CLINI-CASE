resource "aws_cloudwatch_log_group" "waf_logs" {
  name              = "/aws/wafv2/clincase-edge"
  retention_in_days = var.log_retention_days
  tags              = { Name = "clincase-waf-logs" }
}

resource "aws_wafv2_web_acl_logging_configuration" "clincase" {
  resource_arn            = aws_wafv2_web_acl.clincase.arn
  log_destination_configs = [aws_cloudwatch_log_group.waf_logs.arn]
}

# P3 alarm — blocked-request anomaly. Fires when BlockedRequests in any 5-min
# window exceeds 5x the trailing-1-hour median (catches credential-stuffing
# bursts before they cascade to the API).
resource "aws_cloudwatch_metric_alarm" "blocked_request_spike" {
  alarm_name          = "clincase-waf-blocked-spike-p3"
  alarm_description   = "Blocked request spike — possible credential stuffing or DDoS attempt"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 1000
  alarm_actions       = [var.blocked_request_alarm_sns_topic_arn]
  dimensions = {
    WebACL = aws_wafv2_web_acl.clincase.name
    Region = var.aws_region
    Rule   = "ALL"
  }
}
