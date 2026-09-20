# =============================================================================
# IAM execution role — what FIS is allowed to do during an experiment
# =============================================================================
#
# Scoped narrowly: only the actions the 5 experiments need. NOT a generic
# "FIS can do anything" role — that's how chaos becomes an outage.

resource "aws_iam_role" "fis_execution" {
  name = "clincase-fis-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "fis.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "sts:ExternalId" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "fis_execution" {
  role = aws_iam_role.fis_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # EXP-02: kill EKS pods
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
        ]
        Resource = "*"
      },
      # EXP-03: RDS forced failover
      {
        Effect = "Allow"
        Action = ["rds:RebootDBCluster", "rds:DescribeDBClusters"]
        Resource = "arn:aws:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:cluster:${var.rds_cluster_id}"
      },
      # EXP-04: ElastiCache failover
      {
        Effect = "Allow"
        Action = ["elasticache:TestFailover", "elasticache:DescribeReplicationGroups"]
        Resource = "*"
      },
      # EXP-05: NACL rule add/remove
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkAclEntry",
          "ec2:DeleteNetworkAclEntry",
          "ec2:DescribeNetworkAcls",
        ]
        Resource = "*"
      },
      # CloudWatch — for stop conditions + experiment lifecycle logs
      {
        Effect = "Allow"
        Action = ["cloudwatch:DescribeAlarms"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${var.fis_log_group_arn}:*"
      },
    ]
  })
}
