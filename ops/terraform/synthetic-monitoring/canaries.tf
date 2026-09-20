# Per-region Synthetics canary. Repeated 4× because Terraform doesn't
# support `for_each` over providers — explicit per-region modules are
# the AWS-recommended pattern.

locals {
  canary_runtime = "syn-nodejs-puppeteer-9.0"
  canary_script  = <<-EOT
    const synthetics = require('Synthetics');
    const log = require('SyntheticsLogger');

    const apiCanaryBlueprint = async function () {
        const url = process.env.API_ENDPOINT + '/api/v1/healthz/deep';
        let res = await synthetics.executeHttpStep('healthz_deep', {
            hostname: new URL(url).hostname,
            method:   'GET',
            path:     new URL(url).pathname,
            port:     443,
            protocol: 'https:',
            body:     '',
            headers:  { 'User-Agent': 'ClinCaseCanary/1.0' },
        }, async function (res) {
            if (res.statusCode !== ${var.expected_status_code}) {
                throw new Error('healthz_deep returned ' + res.statusCode);
            }
            return true;
        });

        const v2url = process.env.API_ENDPOINT + '/api/v2/healthz';
        await synthetics.executeHttpStep('v2_healthz', {
            hostname: new URL(v2url).hostname,
            method:   'GET',
            path:     new URL(v2url).pathname,
            port:     443,
            protocol: 'https:',
            body:     '',
            headers:  { 'User-Agent': 'ClinCaseCanary/1.0' },
        }, async function (res) {
            if (res.statusCode !== 200) {
                throw new Error('v2 healthz returned ' + res.statusCode);
            }
            return true;
        });
    };

    exports.handler = async () => {
        return await apiCanaryBlueprint();
    };
  EOT
}

# us-east-1 ----------------------------------------------------------------
resource "aws_s3_bucket" "artifacts_use1" {
  provider = aws.us_east_1
  bucket   = "clincase-canary-artifacts-${data.aws_caller_identity.use1.account_id}-use1"
}

data "aws_caller_identity" "use1" { provider = aws.us_east_1 }

resource "aws_iam_role" "canary_use1" {
  provider           = aws.us_east_1
  name               = "ClinCaseCanaryRole-use1"
  assume_role_policy = data.aws_iam_policy_document.canary_assume.json
}

resource "aws_iam_role_policy_attachment" "canary_use1_policy" {
  provider   = aws.us_east_1
  role       = aws_iam_role.canary_use1.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/CloudWatchSyntheticsExecutionRolePolicy"
}

resource "aws_synthetics_canary" "healthz_use1" {
  provider             = aws.us_east_1
  name                 = "clincase-healthz-use1"
  artifact_s3_location = "s3://${aws_s3_bucket.artifacts_use1.id}/canary/"
  execution_role_arn   = aws_iam_role.canary_use1.arn
  runtime_version      = local.canary_runtime
  handler              = "index.handler"
  start_canary         = true

  schedule { expression = "rate(${tostring(var.frequency_seconds / 60)} minute)" }
  run_config {
    timeout_in_seconds  = 30
    memory_in_mb        = 1024
    environment_variables = {
      API_ENDPOINT = var.api_endpoint
    }
  }

  zip_file = data.archive_file.canary_zip.output_path
}

resource "aws_cloudwatch_metric_alarm" "healthz_use1" {
  provider            = aws.us_east_1
  alarm_name          = "clincase-canary-failed-use1"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  threshold           = var.alarm_threshold
  period              = 60
  metric_name         = "Failed"
  namespace           = "CloudWatchSynthetics"
  statistic           = "Sum"
  treat_missing_data  = "breaching"
  alarm_actions       = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  dimensions = {
    CanaryName = aws_synthetics_canary.healthz_use1.name
  }
}

# eu-west-1 ----------------------------------------------------------------
data "aws_caller_identity" "euw1" { provider = aws.eu_west_1 }

resource "aws_s3_bucket" "artifacts_euw1" {
  provider = aws.eu_west_1
  bucket   = "clincase-canary-artifacts-${data.aws_caller_identity.euw1.account_id}-euw1"
}

resource "aws_iam_role" "canary_euw1" {
  provider           = aws.eu_west_1
  name               = "ClinCaseCanaryRole-euw1"
  assume_role_policy = data.aws_iam_policy_document.canary_assume.json
}

resource "aws_iam_role_policy_attachment" "canary_euw1_policy" {
  provider   = aws.eu_west_1
  role       = aws_iam_role.canary_euw1.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/CloudWatchSyntheticsExecutionRolePolicy"
}

resource "aws_synthetics_canary" "healthz_euw1" {
  provider             = aws.eu_west_1
  name                 = "clincase-healthz-euw1"
  artifact_s3_location = "s3://${aws_s3_bucket.artifacts_euw1.id}/canary/"
  execution_role_arn   = aws_iam_role.canary_euw1.arn
  runtime_version      = local.canary_runtime
  handler              = "index.handler"
  start_canary         = true
  schedule { expression = "rate(${tostring(var.frequency_seconds / 60)} minute)" }
  run_config {
    timeout_in_seconds = 30
    memory_in_mb       = 1024
    environment_variables = { API_ENDPOINT = var.api_endpoint }
  }
  zip_file = data.archive_file.canary_zip.output_path
}

# ap-northeast-1 -----------------------------------------------------------
data "aws_caller_identity" "apne1" { provider = aws.ap_northeast_1 }

resource "aws_s3_bucket" "artifacts_apne1" {
  provider = aws.ap_northeast_1
  bucket   = "clincase-canary-artifacts-${data.aws_caller_identity.apne1.account_id}-apne1"
}

resource "aws_iam_role" "canary_apne1" {
  provider           = aws.ap_northeast_1
  name               = "ClinCaseCanaryRole-apne1"
  assume_role_policy = data.aws_iam_policy_document.canary_assume.json
}

resource "aws_iam_role_policy_attachment" "canary_apne1_policy" {
  provider   = aws.ap_northeast_1
  role       = aws_iam_role.canary_apne1.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/CloudWatchSyntheticsExecutionRolePolicy"
}

resource "aws_synthetics_canary" "healthz_apne1" {
  provider             = aws.ap_northeast_1
  name                 = "clincase-healthz-apne1"
  artifact_s3_location = "s3://${aws_s3_bucket.artifacts_apne1.id}/canary/"
  execution_role_arn   = aws_iam_role.canary_apne1.arn
  runtime_version      = local.canary_runtime
  handler              = "index.handler"
  start_canary         = true
  schedule { expression = "rate(${tostring(var.frequency_seconds / 60)} minute)" }
  run_config {
    timeout_in_seconds = 30
    memory_in_mb       = 1024
    environment_variables = { API_ENDPOINT = var.api_endpoint }
  }
  zip_file = data.archive_file.canary_zip.output_path
}

# Canary script (zipped) — same script reused across regions.
data "archive_file" "canary_zip" {
  type        = "zip"
  output_path = "${path.module}/build/canary.zip"
  source {
    filename = "nodejs/node_modules/index.js"
    content  = local.canary_script
  }
}
