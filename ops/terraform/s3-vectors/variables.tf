variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "cost_center" {
  type    = string
  default = "AEROFYTA-CLINCASE-PROD"
}

variable "organization_id" {
  description = "ClinCase organization_id this index belongs to. Index name will be `clincase-policies-${organization_id}`."
  type        = string
}

variable "source_bucket_arn" {
  description = "ARN of the S3 bucket holding the customer's source policy PDFs/HTML."
  type        = string
}

variable "kms_key_arn" {
  description = "KMS multi-region key ARN. Same key as the source bucket — defense in depth + cross-region replica."
  type        = string
}

variable "embedding_model_arn" {
  description = "Bedrock embedding model ARN. Default: Titan Text Embeddings V2 (1024 dim)."
  type        = string
  default     = "arn:aws:bedrock:ap-south-1::foundation-model/amazon.titan-embed-text-v2:0"
}

variable "vector_dimensions" {
  description = "Embedding dimension count. Must match embedding_model_arn output."
  type        = number
  default     = 1024
}

variable "bedrock_kb_principal_arn" {
  description = "IAM principal ARN of the Bedrock Knowledge Base that will query this index."
  type        = string
}
