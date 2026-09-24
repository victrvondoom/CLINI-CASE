"""External-system integrations.

Each subpackage adapts ClinCase to one of the payer platforms it integrates with or
AWS-managed services. Adapters are STATELESS — they translate ClinCase's
internal types to/from the external API contract, without persisting state
of their own.

Packages:
  trizetto/    TriZetto AI Gateway + Facets + QNXT writeback
  kiro/        Amazon Kiro IDE spec exporter (.kiro/specs/*)
  amazon_q/    Amazon Q Business knowledge connector (alternative to Bedrock KB)
"""
