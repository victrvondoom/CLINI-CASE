"""Deployment configuration must not carry plaintext credentials and must set ENVIRONMENT explicitly."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
K8S = ROOT / "ops" / "k8s"


def _load_ecs_helper():
    spec = importlib.util.spec_from_file_location(
        "_ecs_task_env", ROOT / "backend" / "_ecs_task_env.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ecs = _load_ecs_helper()
ARN_JWT = "arn:aws:secretsmanager:us-east-1:111111111111:secret:clincase/jwt-AbCdEf"
ARN_DEMO = "arn:aws:secretsmanager:us-east-1:111111111111:secret:clincase/demo-AbCdEf"


def _build(environ):
    return ecs.build_task_env_and_secrets(
        environ, region="us-east-1", cors_origins="https://x.test"
    )


def _as_map(pairs):
    return {p["name"]: p.get("value", p.get("valueFrom")) for p in pairs}


def test_environment_is_always_explicit_and_defaults_to_staging_not_dev():
    env, _ = _build({"JWT_SECRET_SECRET_ARN": ARN_JWT, "DEMO_USER_PASSWORD_SECRET_ARN": ARN_DEMO})
    assert _as_map(env)["ENVIRONMENT"] == "staging"


def test_invalid_environment_is_rejected():
    with pytest.raises(ValueError):
        _build({"DEPLOY_ENVIRONMENT": "prod"})


@pytest.mark.parametrize(
    "name", ["JWT_SECRET", "DEMO_USER_PASSWORD", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"]
)
def test_plaintext_credentials_are_refused_outside_dev(name):
    environ = {
        "DEPLOY_ENVIRONMENT": "production",
        "JWT_SECRET_SECRET_ARN": ARN_JWT,
        "DEMO_USER_PASSWORD_SECRET_ARN": ARN_DEMO,
        name: "hunter2-not-a-real-secret",
    }
    with pytest.raises(ValueError, match="plaintext"):
        _build(environ)


@pytest.mark.parametrize("missing", ["JWT_SECRET_SECRET_ARN", "DEMO_USER_PASSWORD_SECRET_ARN"])
def test_required_secret_arns_outside_dev(missing):
    environ = {
        "DEPLOY_ENVIRONMENT": "production",
        "JWT_SECRET_SECRET_ARN": ARN_JWT,
        "DEMO_USER_PASSWORD_SECRET_ARN": ARN_DEMO,
    }
    del environ[missing]
    with pytest.raises(ValueError, match="required"):
        _build(environ)


def test_secrets_are_injected_by_arn_never_as_values():
    environ = {
        "DEPLOY_ENVIRONMENT": "production",
        "JWT_SECRET_SECRET_ARN": ARN_JWT,
        "DEMO_USER_PASSWORD_SECRET_ARN": ARN_DEMO,
        "AWS_SECRET_ACCESS_KEY": "AKIA-should-never-pass",
    }
    env, secrets = _build(environ)
    assert {s["name"]: s["valueFrom"] for s in secrets} == {
        "JWT_SECRET": ARN_JWT,
        "DEMO_USER_PASSWORD": ARN_DEMO,
    }
    names = {e["name"] for e in env}
    assert not names & {"JWT_SECRET", "DEMO_USER_PASSWORD", "AWS_SECRET_ACCESS_KEY"}
    assert "AKIA-should-never-pass" not in str(env)


def test_dev_keeps_plaintext_for_local_convenience():
    env, secrets = _build({"DEPLOY_ENVIRONMENT": "dev", "JWT_SECRET": "dev-only"})
    assert _as_map(env)["JWT_SECRET"] == "dev-only" and secrets == []


def test_execution_role_is_limited_to_the_referenced_secrets():
    assert ecs.execution_role_secret_policy([]) is None
    pol = ecs.execution_role_secret_policy([ARN_JWT, ARN_DEMO, ARN_JWT])
    stmt = pol["Statement"][0]
    assert stmt["Action"] == ["secretsmanager:GetSecretValue"] and stmt["Resource"] == sorted(
        {ARN_JWT, ARN_DEMO}
    )


def _k8s_docs():
    for path in sorted(K8S.rglob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if isinstance(doc, dict):
                yield path, doc


def test_no_kubernetes_secret_with_committed_values():
    offenders = [
        f"{p.relative_to(ROOT)}:{d['metadata']['name']}"
        for p, d in _k8s_docs()
        if d.get("kind") == "Secret" and (d.get("stringData") or d.get("data"))
    ]
    assert offenders == []


def test_no_placeholder_or_default_credentials_in_k8s_manifests():
    text = "\n".join(p.read_text() for p in sorted(K8S.rglob("*.yaml")))
    for needle in ("CHANGEME", "clincase:clincase", "sslmode=disable"):
        assert needle not in text, needle


def test_environment_is_set_in_the_cluster_configmap():
    cm = next(
        d
        for _, d in _k8s_docs()
        if d.get("kind") == "ConfigMap" and d["metadata"]["name"] == "clincase-config"
    )
    assert cm["data"]["ENVIRONMENT"] in ("staging", "production")


def test_database_credentials_are_url_encoded_and_host_is_not_a_placeholder():
    text = (K8S / "external-secrets.yaml").read_text()
    assert "REPLACE" not in text
    for line in text.splitlines():
        if "postgresql://" in line:
            assert "dbuser | urlquery" in line and "dbpass | urlquery" in line and ".dbhost" in line


def test_credentials_come_from_secrets_manager_via_external_secrets():
    ext = {d["metadata"]["name"]: d for _, d in _k8s_docs() if d.get("kind") == "ExternalSecret"}
    assert {"clincase-secrets", "clincase-keda-postgres-conn"} <= set(ext)
    for d in ext.values():
        assert d["spec"]["secretStoreRef"]["name"] == "clincase-aws"
        assert all("key" in item["remoteRef"] for item in d["spec"]["data"])
