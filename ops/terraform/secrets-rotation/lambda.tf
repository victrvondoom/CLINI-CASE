# Three rotation Lambda functions, all in the same VPC + subnets so they
# can reach Postgres / Bedrock VPC endpoint.
#
# The function code is checked into git as a placeholder — production
# rotation logic ships from `aws-samples/aws-secrets-manager-rotation-lambdas`
# and ClinCase's own `rotation_jwt.py`.

data "archive_file" "rotate_jwt" {
  type        = "zip"
  output_path = "${path.module}/build/rotate_jwt.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOT
      """JWT secret rotator (two-secret-overlap pattern).
      Real impl: in `lambda_src/rotate_jwt.py`. This Terraform-bundled stub
      logs and exits 0 so apply succeeds; CI replaces it with the real source.
      """
      def lambda_handler(event, context):
          import json, os, sys
          print("rotate_jwt placeholder; replace via CI", json.dumps(event)[:500])
          return {"status": "placeholder"}
    EOT
  }
}

data "archive_file" "rotate_postgres" {
  type        = "zip"
  output_path = "${path.module}/build/rotate_postgres.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOT
      """Postgres master rotator stub. Replace with
      AWS-provided SecretsManagerRDSPostgreSQLRotationSingleUser package
      via CI build step."""
      def lambda_handler(event, context):
          import json
          print("rotate_postgres placeholder", json.dumps(event)[:500])
          return {"status": "placeholder"}
    EOT
  }
}

data "archive_file" "rotate_iam_key" {
  type        = "zip"
  output_path = "${path.module}/build/rotate_iam_key.zip"
  source {
    filename = "lambda_function.py"
    content  = <<-EOT
      """IAM access key rotator stub.
      Real impl: cycle the IAM access key, update the secret, deactivate the
      previous key after grace window. Replace via CI build step."""
      def lambda_handler(event, context):
          import json
          print("rotate_iam_key placeholder", json.dumps(event)[:500])
          return {"status": "placeholder"}
    EOT
  }
}

# -----------------------------------------------------------------------------

resource "aws_lambda_function" "rotate_jwt" {
  function_name = "clincase-rotate-jwt"
  role          = aws_iam_role.rotation.arn
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  filename      = data.archive_file.rotate_jwt.output_path
  source_code_hash = data.archive_file.rotate_jwt.output_base64sha256
  timeout       = 30

  vpc_config {
    subnet_ids         = var.vpc_subnet_ids
    security_group_ids = var.vpc_security_group_ids
  }

  environment {
    variables = {
      SECRETS_MANAGER_ENDPOINT = "https://secretsmanager.${data.aws_region.current.name}.amazonaws.com"
    }
  }
}

resource "aws_lambda_permission" "rotate_jwt_secrets_manager" {
  statement_id  = "AllowSecretsManagerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotate_jwt.function_name
  principal     = "secretsmanager.amazonaws.com"
}

resource "aws_lambda_function" "rotate_postgres" {
  function_name = "clincase-rotate-postgres"
  role          = aws_iam_role.rotation.arn
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  filename      = data.archive_file.rotate_postgres.output_path
  source_code_hash = data.archive_file.rotate_postgres.output_base64sha256
  timeout       = 60

  vpc_config {
    subnet_ids         = var.vpc_subnet_ids
    security_group_ids = var.vpc_security_group_ids
  }
}

resource "aws_lambda_permission" "rotate_postgres_secrets_manager" {
  statement_id  = "AllowSecretsManagerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotate_postgres.function_name
  principal     = "secretsmanager.amazonaws.com"
}

resource "aws_lambda_function" "rotate_iam_key" {
  function_name = "clincase-rotate-iam-key"
  role          = aws_iam_role.rotation.arn
  runtime       = "python3.12"
  handler       = "lambda_function.lambda_handler"
  filename      = data.archive_file.rotate_iam_key.output_path
  source_code_hash = data.archive_file.rotate_iam_key.output_base64sha256
  timeout       = 30
}

resource "aws_lambda_permission" "rotate_iam_key_secrets_manager" {
  statement_id  = "AllowSecretsManagerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rotate_iam_key.function_name
  principal     = "secretsmanager.amazonaws.com"
}
