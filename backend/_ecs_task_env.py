"""Pure builder for the ECS task definition's environment and secrets (kept import-safe: no AWS calls).

Outside `dev` no credential may be written into the task definition in plaintext. Sensitive values are
referenced as Secrets Manager ARNs (`<NAME>_SECRET_ARN`) and injected by ECS at launch through the
task-execution role.
"""

from __future__ import annotations

from collections.abc import Mapping

ENVIRONMENTS = ("dev", "staging", "production")

# Injected from Secrets Manager outside dev; plain env only in dev.
SECRET_NAMES = ("JWT_SECRET", "DEMO_USER_PASSWORD", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")
# The app refuses to boot outside dev without these (see app/config.py `_enforce_production_secrets`).
REQUIRED_OUTSIDE_DEV = ("JWT_SECRET", "DEMO_USER_PASSWORD")

PLAIN_PASS_THROUGH = (
    "LLM_PROVIDER", "OPENROUTER_MODEL", "ANTHROPIC_MODEL",
    "BEDROCK_MODEL_ID", "BEDROCK_HAIKU_MODEL_ID",
    "BEDROCK_GUARDRAIL_ID", "BEDROCK_GUARDRAIL_VERSION",
    "BEDROCK_KB_ID", "BEDROCK_KB_DATA_SOURCE_ID", "POLICIES_S3_BUCKET",
    "EMBEDDING_MODEL", "LOG_LEVEL", "USE_BEDROCK_KB", "PLATFORM_ADMIN_USER_IDS",
)  # fmt: skip


def deploy_environment(environ: Mapping[str, str]) -> str:
    env = environ.get("DEPLOY_ENVIRONMENT", "staging")
    if env not in ENVIRONMENTS:
        raise ValueError(f"DEPLOY_ENVIRONMENT must be one of {ENVIRONMENTS}, got {env!r}")
    return env


def secret_arns(environ: Mapping[str, str]) -> list[str]:
    """Every Secrets Manager ARN the task will reference (the execution role needs read access to these)."""
    return [a for n in SECRET_NAMES if (a := environ.get(f"{n}_SECRET_ARN"))]


def build_task_env_and_secrets(
    environ: Mapping[str, str], *, region: str, cors_origins: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (`environment`, `secrets`) container-definition lists. Raises ValueError on unsafe input."""
    env_name = deploy_environment(environ)
    env: list[dict[str, str]] = [
        {"name": "AWS_REGION", "value": region},
        # Always explicit: the app's safety guards only engage when ENVIRONMENT != dev.
        {"name": "ENVIRONMENT", "value": env_name},
    ]
    for key in PLAIN_PASS_THROUGH:
        if value := environ.get(key):
            env.append({"name": key, "value": value})
    env += [
        {"name": "CORS_ORIGINS", "value": cors_origins},
        # The deployed task has no reachable database here and must not seed demo data.
        {"name": "SEED_ON_BOOT", "value": "false"},
        {"name": "DATABASE_URL", "value": "postgresql://disabled@disabled/disabled"},
    ]

    secrets: list[dict[str, str]] = []
    for name in SECRET_NAMES:
        arn, plain = environ.get(f"{name}_SECRET_ARN"), environ.get(name)
        if env_name == "dev":
            if arn:
                secrets.append({"name": name, "valueFrom": arn})
            elif plain:
                env.append({"name": name, "value": plain})
            continue
        if plain:
            raise ValueError(
                f"{name} is set in plaintext but DEPLOY_ENVIRONMENT={env_name}; "
                f"store it in Secrets Manager and set {name}_SECRET_ARN instead"
            )
        if arn:
            secrets.append({"name": name, "valueFrom": arn})
        elif name in REQUIRED_OUTSIDE_DEV:
            raise ValueError(f"{name}_SECRET_ARN is required when DEPLOY_ENVIRONMENT={env_name}")
    return env, secrets


def execution_role_secret_policy(
    arns: list[str], kms_key_arn: str | None = None
) -> dict[str, object] | None:
    """Least-privilege read access for the task-execution role (None when no secrets are referenced).

    Secrets encrypted with a customer-managed KMS key (as in ops/terraform/secrets-rotation) also need
    `kms:Decrypt` on that key; pass it via `SECRETS_KMS_KEY_ARN`."""
    if not arns:
        return None
    statements: list[dict[str, object]] = [
        {
            "Sid": "ReadTaskSecrets",
            "Effect": "Allow",
            "Action": ["secretsmanager:GetSecretValue"],
            "Resource": sorted(set(arns)),
        }
    ]
    if kms_key_arn:
        statements.append(
            {
                "Sid": "DecryptTaskSecrets",
                "Effect": "Allow",
                "Action": ["kms:Decrypt"],
                "Resource": kms_key_arn,
            }
        )
    return {"Version": "2012-10-17", "Statement": statements}
