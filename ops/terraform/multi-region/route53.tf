# ─── Route 53 latency-based routing ─────────────────────────────────────────
# A single api.clincase.example.com record fans out to whichever regional ALB
# is closest to the client. Health checks gate each region so a failed ALB
# de-registers automatically (sub-second client failover).

# --- Health checks ----------------------------------------------------------

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_alb_dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/v1/healthz"
  failure_threshold = 3
  request_interval  = 30
  measure_latency   = true
  regions           = ["us-east-1", "us-west-1", "eu-west-1"]

  tags = { Name = "clincase-primary-${var.primary_region}" }
}

resource "aws_route53_health_check" "secondary" {
  fqdn              = var.secondary_alb_dns_name
  port              = 443
  type              = "HTTPS"
  resource_path     = "/api/v1/healthz"
  failure_threshold = 3
  request_interval  = 30
  measure_latency   = true
  regions           = ["us-east-1", "us-west-1", "eu-west-1"]

  tags = { Name = "clincase-secondary-${var.secondary_region}" }
}

# --- LBR records ------------------------------------------------------------
# Set identifier ensures Route 53 treats the two records as a single LBR set.
# The client gets routed to whichever region has the lower observed latency
# from their resolver — overridden by health-check failures.

resource "aws_route53_record" "primary" {
  zone_id        = var.hosted_zone_id
  name           = var.service_dns_name
  type           = "A"
  set_identifier = "clincase-${var.primary_region}"
  health_check_id = aws_route53_health_check.primary.id

  alias {
    name                   = var.primary_alb_dns_name
    zone_id                = var.primary_alb_zone_id
    evaluate_target_health = true
  }

  latency_routing_policy {
    region = var.primary_region
  }
}

resource "aws_route53_record" "secondary" {
  zone_id        = var.hosted_zone_id
  name           = var.service_dns_name
  type           = "A"
  set_identifier = "clincase-${var.secondary_region}"
  health_check_id = aws_route53_health_check.secondary.id

  alias {
    name                   = var.secondary_alb_dns_name
    zone_id                = var.secondary_alb_zone_id
    evaluate_target_health = true
  }

  latency_routing_policy {
    region = var.secondary_region
  }
}
