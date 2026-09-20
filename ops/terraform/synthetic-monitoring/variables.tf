variable "api_endpoint" {
  type        = string
  description = "Public URL of the ClinCase API. e.g. https://api.clincase.example.com"
}

variable "expected_status_code" {
  type    = number
  default = 200
}

variable "frequency_seconds" {
  type    = number
  default = 60
  validation {
    condition     = var.frequency_seconds >= 60
    error_message = "Synthetics canaries cannot run more often than 60s."
  }
}

variable "alarm_threshold" {
  type    = number
  default = 2
  description = "How many failures within evaluation_periods to trigger the alarm."
}

variable "alarm_sns_topic_arn" {
  type        = string
  description = "SNS topic the alarms publish to (paged via PagerDuty)."
  default     = ""
}
