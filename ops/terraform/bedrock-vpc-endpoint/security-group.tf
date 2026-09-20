# =============================================================================
# Security group for the Bedrock VPC interface endpoints
# =============================================================================
#
# Inbound: 443 from EKS node SG only — no 0.0.0.0/0.
# Outbound: deny-all (the endpoint doesn't initiate connections).

resource "aws_security_group" "bedrock_vpce" {
  name_prefix = "clincase-bedrock-vpce-"
  vpc_id      = var.vpc_id
  description = "Bedrock VPC endpoint — accepts 443 from EKS nodes only."

  ingress {
    description     = "HTTPS from EKS nodes"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [var.eks_node_security_group_id]
  }

  egress {
    description = "Endpoint does not initiate egress; deny-all"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []  # empty = no egress allowed
  }

  tags = { Name = "clincase-bedrock-vpce" }
}
