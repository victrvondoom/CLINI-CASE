output "canary_arns" {
  value = {
    us_east_1      = aws_synthetics_canary.healthz_use1.arn
    eu_west_1      = aws_synthetics_canary.healthz_euw1.arn
    ap_northeast_1 = aws_synthetics_canary.healthz_apne1.arn
  }
}

output "alarm_arns" {
  value = {
    us_east_1 = aws_cloudwatch_metric_alarm.healthz_use1.arn
  }
}

output "summary" {
  value = {
    probed_regions = ["us-east-1", "eu-west-1", "ap-northeast-1"]
    frequency      = "${var.frequency_seconds}s"
    api_endpoint   = var.api_endpoint
  }
}
