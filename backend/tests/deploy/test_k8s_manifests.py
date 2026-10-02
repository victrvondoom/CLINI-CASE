"""Offline deployment contract for the local kind stack in k8s/ (frontend + api + receiver + postgres).

Nothing here needs a cluster, Docker or the network: the manifests, the orchestrator and the nginx
config are parsed and checked against (a) the contract shared with the application (ports, probe
paths, images, secret keys, config keys) and (b) the hardening posture the namespace enforces (Pod
Security `restricted`, NetworkPolicy default-deny, no RBAC, no committed secrets).
`python k8s/cluster.py verify` then proves the same properties against a running cluster.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
K8S = ROOT / "k8s"
NGINX_CONF = ROOT / "frontend" / "nginx.conf"
NOT_RESOURCES = {"kind-config.yaml", "kustomization.yaml"}

API_IMAGE = "clinicase-api:local"
WEB_IMAGE = "clinicase-web:local"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
SECRET_KEYS = {
    "DATABASE_URL",
    "JWT_SECRET",
    "INTEROP_RECEIVER_TOKEN",
    "DEMO_USER_PASSWORD",
    "POSTGRES_PASSWORD",
    "PASSPORT_SIGNING_KEY",
}
DOWNWARD_API = {
    "POD_NAME": "metadata.name",
    "POD_NAMESPACE": "metadata.namespace",
    "NODE_NAME": "spec.nodeName",
    "POD_IP": "status.podIP",
}
RESTRICTED_VOLUME_TYPES = {
    "configMap",
    "csi",
    "downwardAPI",
    "emptyDir",
    "ephemeral",
    "persistentVolumeClaim",
    "projected",
    "secret",
}


def _load(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]


RESOURCES = [
    (path.name, doc)
    for path in sorted(K8S.glob("*.yaml"))
    if path.name not in NOT_RESOURCES
    for doc in _load(path)
]
WORKLOADS = {
    doc["metadata"]["name"]: doc
    for _, doc in RESOURCES
    if doc["kind"] in ("Deployment", "StatefulSet")
}
CONTAINERS = [
    (name, doc["spec"]["template"]["spec"], container)
    for name, doc in WORKLOADS.items()
    for container in (
        doc["spec"]["template"]["spec"].get("initContainers", [])
        + doc["spec"]["template"]["spec"]["containers"]
    )
]
CONTAINER_IDS = [f"{name}/{container['name']}" for name, _, container in CONTAINERS]


def _of(kind: str) -> list[dict]:
    return [doc for _, doc in RESOURCES if doc["kind"] == kind]


def _named(kind: str, name: str) -> dict:
    return next(doc for doc in _of(kind) if doc["metadata"]["name"] == name)


def _spec(workload: str) -> dict:
    return WORKLOADS[workload]["spec"]["template"]["spec"]


def _main(workload: str) -> dict:
    return next(c for c in _spec(workload)["containers"] if c["name"] == workload)


def _env(container: dict) -> dict[str, dict]:
    return {item["name"]: item for item in container.get("env", [])}


def _port_number(container: dict, port: int | str) -> int:
    if isinstance(port, int):
        return port
    return next(p["containerPort"] for p in container["ports"] if p["name"] == port)


def _orchestrator():
    spec = importlib.util.spec_from_file_location("clinicase_cluster", K8S / "cluster.py")
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # keep k8s/ free of __pycache__
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# --- repository layout ----------------------------------------------------------------------


def test_kustomization_lists_every_manifest_except_kind_config():
    kustomization = yaml.safe_load((K8S / "kustomization.yaml").read_text(encoding="utf-8"))
    on_disk = {p.name for p in K8S.glob("*.yaml")} - NOT_RESOURCES
    listed = kustomization["resources"]
    assert len(listed) == len(set(listed)), "duplicate entries"
    assert set(listed) == on_disk
    assert listed[0] == "namespace.yaml"
    assert kustomization["namespace"] == "clinicase"
    assert "kind-config.yaml" not in listed


def test_superseded_track7_only_manifest_is_gone():
    assert not (ROOT / "ops" / "kind" / "track7-demo.yaml").exists()
    runbook = (ROOT / "docs" / "DEMO_RUNBOOK.md").read_text(encoding="utf-8")
    assert "track7-demo.yaml" not in runbook
    assert "docs/KUBERNETES.md" in runbook or "KUBERNETES.md" in runbook


def test_runbook_exists_and_documents_the_one_command_flow():
    text = (ROOT / "docs" / "KUBERNETES.md").read_text(encoding="utf-8")
    for needle in ("cluster.py up", "cluster.py verify", "cluster.py credentials", "cluster.py down"):
        assert needle in text, needle


# --- namespace and Pod Security Admission -----------------------------------------------------


def test_namespace_enforces_pod_security_admission():
    namespace = _named("Namespace", "clinicase")
    labels = namespace["metadata"]["labels"]
    enforce = labels["pod-security.kubernetes.io/enforce"]
    assert enforce in ("restricted", "baseline")
    if enforce == "baseline":  # only acceptable if a workload genuinely cannot comply
        assert labels["pod-security.kubernetes.io/warn"] == "restricted"
        assert labels["pod-security.kubernetes.io/audit"] == "restricted"
    assert all(doc["kind"] != "Namespace" or doc is namespace for _, doc in RESOURCES)


@pytest.mark.parametrize("workload", sorted(WORKLOADS))
def test_every_pod_satisfies_the_restricted_profile(workload):
    spec = _spec(workload)
    problems = []
    pod_security = spec.get("securityContext", {})
    problems += [flag for flag in ("hostNetwork", "hostPID", "hostIPC") if spec.get(flag)]
    for volume in spec.get("volumes", []):
        volume_type = next(key for key in volume if key != "name")
        if volume_type not in RESTRICTED_VOLUME_TYPES:
            problems.append(f"volume type {volume_type}")
    for container in spec.get("initContainers", []) + spec["containers"]:
        sc = container.get("securityContext", {})
        name = container["name"]
        if sc.get("privileged"):
            problems.append(f"{name}: privileged")
        if sc.get("allowPrivilegeEscalation") is not False:
            problems.append(f"{name}: allowPrivilegeEscalation")
        if "ALL" not in sc.get("capabilities", {}).get("drop", []):
            problems.append(f"{name}: capabilities.drop ALL")
        if set(sc.get("capabilities", {}).get("add", [])) - {"NET_BIND_SERVICE"}:
            problems.append(f"{name}: capabilities.add")
        if not sc.get("runAsNonRoot", pod_security.get("runAsNonRoot")):
            problems.append(f"{name}: runAsNonRoot")
        if sc.get("runAsUser", pod_security.get("runAsUser")) == 0:
            problems.append(f"{name}: runAsUser 0")
        profile = (sc.get("seccompProfile") or pod_security.get("seccompProfile") or {}).get("type")
        if profile not in ("RuntimeDefault", "Localhost"):
            problems.append(f"{name}: seccompProfile")
        if any("hostPort" in port for port in container.get("ports", [])):
            problems.append(f"{name}: hostPort")
    assert problems == []


# --- container hardening, resources, probes ---------------------------------------------------


@pytest.mark.parametrize(("workload", "pod", "container"), CONTAINERS, ids=CONTAINER_IDS)
def test_container_security_context(workload, pod, container):
    sc = container["securityContext"]
    assert sc["runAsNonRoot"] is True
    assert sc["allowPrivilegeEscalation"] is False
    assert sc["readOnlyRootFilesystem"] is True
    assert sc["capabilities"] == {"drop": ["ALL"]}
    assert sc["seccompProfile"] == {"type": "RuntimeDefault"}
    assert not sc.get("privileged")
    assert pod["securityContext"]["runAsUser"] not in (None, 0)
    assert not any("hostPort" in port for port in container.get("ports", []))


@pytest.mark.parametrize(("workload", "pod", "container"), CONTAINERS, ids=CONTAINER_IDS)
def test_container_has_resource_requests_and_limits(workload, pod, container):
    resources = container["resources"]
    for section in ("requests", "limits"):
        assert {"cpu", "memory"} <= set(resources[section]), f"{section} incomplete"


@pytest.mark.parametrize("workload", sorted(WORKLOADS))
def test_pod_does_not_use_host_access_or_the_default_service_account(workload):
    spec = _spec(workload)
    assert not any(spec.get(flag) for flag in ("hostNetwork", "hostPID", "hostIPC"))
    assert not any("hostPath" in volume for volume in spec.get("volumes", []))
    assert spec["serviceAccountName"] == workload
    assert spec["automountServiceAccountToken"] is False
    assert spec["enableServiceLinks"] is False


HTTP_PROBE_CONTRACT = {
    "api": (
        8000,
        {
            "startupProbe": "/api/v1/healthz",
            "livenessProbe": "/api/v1/healthz",
            "readinessProbe": "/api/v1/readyz",
        },
    ),
    "receiver": (
        8091,
        {"startupProbe": "/healthz", "livenessProbe": "/healthz", "readinessProbe": "/healthz"},
    ),
    "frontend": (
        5173,
        {"startupProbe": "/healthz", "livenessProbe": "/healthz", "readinessProbe": "/healthz"},
    ),
}


@pytest.mark.parametrize("workload", sorted(HTTP_PROBE_CONTRACT))
def test_http_probes_match_the_contract(workload):
    port, probes = HTTP_PROBE_CONTRACT[workload]
    container = _main(workload)
    for probe_name, path in probes.items():
        http_get = container[probe_name]["httpGet"]
        assert http_get["path"] == path, probe_name
        assert _port_number(container, http_get["port"]) == port, probe_name


def test_postgres_probes_use_tcp_pg_isready():
    container = _main("postgres")
    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        command = container[probe_name]["exec"]["command"]
        assert command[0] == "pg_isready", probe_name
        # The first-boot init server listens on the unix socket only; the TCP check proves the
        # final server (and therefore the loaded schema) is up.
        assert command[command.index("-h") + 1] == "127.0.0.1", probe_name


def test_api_waits_for_postgres_before_starting():
    init = {c["name"]: c for c in _spec("api")["initContainers"]}
    wait = "\n".join(init["wait-for-postgres"]["args"])
    assert '"postgres", 5432' in wait
    assert init["wait-for-postgres"]["image"] == API_IMAGE


def test_probe_paths_exist_as_real_routes():
    from app.interop.receiver import app as receiver_app
    from app.main import app as api_app

    api_paths = {getattr(route, "path", None) for route in api_app.routes}
    receiver_paths = {getattr(route, "path", None) for route in receiver_app.routes}
    assert {"/api/v1/healthz", "/api/v1/readyz"} <= api_paths
    assert "/healthz" in receiver_paths
    nginx = NGINX_CONF.read_text(encoding="utf-8")
    assert re.search(r"location\s*=\s*/healthz\s*\{[^}]*return\s+200", nginx)


# --- images, secrets, configuration -------------------------------------------------------------


def test_images_are_the_contract_tags_and_never_latest():
    images = {(name, c["name"]): c["image"] for name, _, c in CONTAINERS}
    assert set(images.values()) == {API_IMAGE, WEB_IMAGE, POSTGRES_IMAGE}
    assert images[("api", "api")] == API_IMAGE
    assert images[("receiver", "receiver")] == API_IMAGE
    assert images[("frontend", "frontend")] == WEB_IMAGE
    assert images[("postgres", "postgres")] == POSTGRES_IMAGE
    for _, _, container in CONTAINERS:
        image = container["image"]
        assert ":" in image.rsplit("/", 1)[-1] and not image.endswith(":latest"), image
        if image.endswith(":local"):
            assert container["imagePullPolicy"] == "Never", image  # loaded into kind, never pulled
        else:
            assert container["imagePullPolicy"] == "IfNotPresent", image
    assert ":latest" not in "\n".join(p.read_text(encoding="utf-8") for p in K8S.glob("*.yaml"))


def test_no_secret_objects_or_credentials_in_git():
    assert [doc["metadata"]["name"] for doc in _of("Secret")] == []
    text = "\n".join(p.read_text(encoding="utf-8") for p in K8S.glob("*.yaml"))
    assert not re.search(r"postgres(ql)?://[^/\s]+:[^@\s]+@", text)
    for needle in ("CHANGEME", "password:", "sslmode=disable"):
        assert needle not in text, needle


def test_every_secret_reference_points_at_the_generated_secret():
    references = []
    for _, doc in RESOURCES:
        if doc["kind"] in ("Deployment", "StatefulSet"):
            for container in _spec(doc["metadata"]["name"])["containers"]:
                for item in container.get("env", []):
                    ref = item.get("valueFrom", {}).get("secretKeyRef")
                    if ref:
                        references.append((item["name"], ref["name"], ref["key"]))
    assert references
    assert {name for _, name, _ in references} == {"clinicase-secrets"}
    assert {key for _, _, key in references} <= SECRET_KEYS
    for env_name, _, key in references:
        assert env_name == key or (env_name, key) == ("POSTGRES_PASSWORD", "POSTGRES_PASSWORD")
    # Plain `value:` is only acceptable for non-secret settings.
    for _, _, container in CONTAINERS:
        for item in container.get("env", []):
            assert item["name"] not in SECRET_KEYS or "valueFrom" in item, item["name"]


def test_api_environment_contract():
    api = _main("api")
    env = _env(api)
    for key in ("DATABASE_URL", "JWT_SECRET", "INTEROP_RECEIVER_TOKEN", "DEMO_USER_PASSWORD"):
        assert env[key]["valueFrom"]["secretKeyRef"] == {"name": "clinicase-secrets", "key": key}
    assert api["envFrom"] == [{"configMapRef": {"name": "clinicase-config"}}]
    for key, field_path in DOWNWARD_API.items():
        assert env[key]["valueFrom"]["fieldRef"]["fieldPath"] == field_path
    mounts = {m["mountPath"] for m in api["volumeMounts"]}
    assert {"/tmp", "/app/data/policies"} <= mounts  # the only writable paths on a read-only root


def test_interop_demo_payloads_ship_in_the_api_image():
    """POST /api/v1/interop/demo reads <app>/data/interop, so the image must carry it and no mount may hide it."""
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY data /app/data" in dockerfile
    ignored = (ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert not any(line.strip().rstrip("/") in {"data", "/data", "data/**"} for line in ignored)
    api = _main("api")
    volumes = {v["name"]: v for v in _spec("api")["volumes"]}
    mounts = {m["mountPath"]: m for m in api["volumeMounts"]}
    # Only the writable policy store is mounted under /app/data; anything over /app/data or
    # /app/data/interop would hide the payloads the image ships.
    assert "emptyDir" in volumes[mounts["/app/data/policies"]["name"]]
    assert not {"/app/data", "/app/data/interop"} & set(mounts)
    names = {p.name for p in (ROOT / "backend" / "data" / "interop").iterdir() if p.is_file()}
    assert {"environmental.json", "environmental-dissolved.json"} <= names  # the two files /demo reads
    from app.api import interop as interop_api

    # The demo endpoint resolves its payloads relative to the app package; the image must carry them there.
    assert (Path(interop_api.__file__).parents[2] / "data" / "interop" / "environmental.json").is_file()


def test_receiver_environment_contract():
    receiver = _main("receiver")
    env = _env(receiver)
    assert env["INTEROP_RECEIVER_DB"]["value"] == "/data/receipts.sqlite"
    assert env["INTEROP_RECEIVER_TOKEN"]["valueFrom"]["secretKeyRef"]["key"] == (
        "INTEROP_RECEIVER_TOKEN"
    )
    for key, field_path in DOWNWARD_API.items():
        assert env[key]["valueFrom"]["fieldRef"]["fieldPath"] == field_path
    assert receiver["command"][:2] == ["uvicorn", "app.interop.receiver:app"]
    assert receiver["command"][-2:] == ["--port", "8091"]
    volumes = {v["name"]: v for v in _spec("receiver")["volumes"]}
    mounts = {m["mountPath"]: m["name"] for m in receiver["volumeMounts"]}
    assert {"/data", "/tmp"} <= set(mounts)
    assert all("emptyDir" in volumes[mounts[path]] for path in ("/data", "/tmp"))


def test_config_map_carries_the_runtime_contract():
    data = _named("ConfigMap", "clinicase-config")["data"]
    assert data["ENVIRONMENT"] == "dev"
    assert data["CORS_ORIGINS"] == "http://localhost:8080"
    assert data["REDIS_URL"] == ""
    assert data["AUTH_DBLESS_DEMO_ENABLED"] == "false"
    assert data["SEED_ON_BOOT"] == "false"
    assert data["RUNTIME_PLATFORM"] == "kind"
    assert data["RUNTIME_FRONTEND_IMAGE"] == WEB_IMAGE
    assert data["RUNTIME_RECEIVER_IMAGE"] == API_IMAGE
    assert data["CLINICASE_IMAGE"] == API_IMAGE
    assert not SECRET_KEYS & set(data), "secrets must not live in the ConfigMap"


def test_config_map_urls_agree_with_the_services():
    data = _named("ConfigMap", "clinicase-config")["data"]
    receiver = urlparse(data["INTEROP_RECEIVER_URL"])
    frontend = urlparse(data["RUNTIME_FRONTEND_URL"])
    assert (receiver.scheme, receiver.hostname, receiver.port) == ("http", "receiver", 8091)
    assert (frontend.scheme, frontend.hostname, frontend.port) == ("http", "frontend", 5173)
    assert _named("Service", "receiver")["spec"]["ports"][0]["port"] == receiver.port
    assert _named("Service", "frontend")["spec"]["ports"][0]["port"] == frontend.port


# --- services, labels, storage ----------------------------------------------------------------


SERVICE_CONTRACT = {
    "api": ("ClusterIP", 8000),
    "receiver": ("ClusterIP", 8091),
    "frontend": ("NodePort", 5173),
    "postgres": ("ClusterIP", 5432),
}


@pytest.mark.parametrize("name", sorted(SERVICE_CONTRACT))
def test_service_matches_the_contract_and_selects_its_workload(name):
    service_type, port = SERVICE_CONTRACT[name]
    service = _named("Service", name)
    assert service["spec"]["type"] == service_type
    (service_port,) = service["spec"]["ports"]
    assert service_port["port"] == port
    assert _port_number(_main(name), service_port["targetPort"]) == port
    template_labels = WORKLOADS[name]["spec"]["template"]["metadata"]["labels"]
    assert service["spec"]["selector"].items() <= template_labels.items()
    if name == "frontend":
        assert service_port["nodePort"] == 30080
    else:
        assert "nodePort" not in service_port


def test_labels_are_consistent_across_every_resource():
    for source, doc in RESOURCES:
        labels = doc["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/part-of") == "clinicase", f"{source}:{doc['kind']}"
    for name, workload in WORKLOADS.items():
        template = workload["spec"]["template"]["metadata"]["labels"]
        assert template["app.kubernetes.io/name"] == name
        assert template["app.kubernetes.io/part-of"] == "clinicase"
        assert template["app.kubernetes.io/component"]
        assert workload["spec"]["selector"]["matchLabels"].items() <= template.items()


def test_postgres_storage_and_schema_contract():
    statefulset = WORKLOADS["postgres"]
    (claim,) = statefulset["spec"]["volumeClaimTemplates"]
    assert claim["spec"]["resources"]["requests"]["storage"] == "2Gi"
    assert claim["spec"]["accessModes"] == ["ReadWriteOnce"]
    assert "storageClassName" not in claim["spec"], "use the cluster default (kind: standard)"
    postgres = _main("postgres")
    mounts = {m["mountPath"]: m for m in postgres["volumeMounts"]}
    assert mounts["/var/lib/postgresql/data"]["name"] == claim["metadata"]["name"]
    assert mounts["/docker-entrypoint-initdb.d"]["readOnly"] is True
    schema = next(v for v in _spec("postgres")["volumes"] if v["name"] == "schema")
    assert schema["configMap"]["name"] == "clinicase-db-schema"
    assert not any(doc["metadata"]["name"] == "clinicase-db-schema" for doc in _of("ConfigMap"))
    pgdata = _env(postgres)["PGDATA"]["value"]
    assert pgdata.startswith("/var/lib/postgresql/data/") and pgdata != "/var/lib/postgresql/data/"
    assert {"/var/run/postgresql", "/tmp"} <= set(mounts)  # writable socket dir on a read-only root
    assert _spec("postgres")["securityContext"]["fsGroup"] == 999


def test_nginx_proxies_to_the_api_service_and_serves_healthz():
    nginx = NGINX_CONF.read_text(encoding="utf-8")
    targets = set(re.findall(r"proxy_pass\s+http://([A-Za-z0-9.-]+):(\d+)", nginx))
    api_port = _named("Service", "api")["spec"]["ports"][0]["port"]
    assert targets == {("api", str(api_port))}, "service name `api` is load-bearing in nginx.conf"
    listen = re.search(r"listen\s+(\d+);", nginx)
    assert listen
    assert int(listen.group(1)) == _named("Service", "frontend")["spec"]["ports"][0]["port"]
    assert re.search(r"location\s*=\s*/healthz", nginx)


def test_kind_config_publishes_the_nodeport_on_loopback_only():
    config = yaml.safe_load((K8S / "kind-config.yaml").read_text(encoding="utf-8"))
    assert config["kind"] == "Cluster"
    assert re.fullmatch(r"kindest/node:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", config["nodes"][0]["image"])
    (mapping,) = config["nodes"][0]["extraPortMappings"]
    assert mapping["containerPort"] == _named("Service", "frontend")["spec"]["ports"][0]["nodePort"]
    assert mapping["hostPort"] == 8080
    assert mapping["listenAddress"] == "127.0.0.1"


# --- RBAC: none ----------------------------------------------------------------------------------


def test_no_rbac_objects_and_no_cluster_admin():
    rbac = {"Role", "ClusterRole", "RoleBinding", "ClusterRoleBinding"}
    assert [doc["metadata"]["name"] for _, doc in RESOURCES if doc["kind"] in rbac] == []
    for path in (*K8S.glob("*.yaml"), K8S / "cluster.py"):
        assert "cluster-admin" not in path.read_text(encoding="utf-8"), path.name


def test_each_workload_has_a_dedicated_token_less_service_account():
    accounts = {doc["metadata"]["name"]: doc for doc in _of("ServiceAccount")}
    assert set(accounts) == set(WORKLOADS)
    for name, account in accounts.items():
        assert account["automountServiceAccountToken"] is False, name


# --- NetworkPolicy ---------------------------------------------------------------------------------


def _selected_names(selector_list: list[dict]) -> set[str]:
    return {item["podSelector"]["matchLabels"]["app.kubernetes.io/name"] for item in selector_list}


def _ports(rule: dict) -> set[tuple[str, int]]:
    return {(p["protocol"], p["port"]) for p in rule["ports"]}


def test_default_deny_and_dns_floor():
    deny = _named("NetworkPolicy", "default-deny-all")["spec"]
    assert deny["podSelector"] == {}
    assert set(deny["policyTypes"]) == {"Ingress", "Egress"}
    assert not deny.get("ingress") and not deny.get("egress")
    dns = _named("NetworkPolicy", "allow-dns-egress")["spec"]
    assert dns["podSelector"] == {} and dns["policyTypes"] == ["Egress"]
    (rule,) = dns["egress"]
    (peer,) = rule["to"]
    assert peer["namespaceSelector"]["matchLabels"] == {"kubernetes.io/metadata.name": "kube-system"}
    assert peer["podSelector"]["matchLabels"] == {"k8s-app": "kube-dns"}
    assert _ports(rule) == {("UDP", 53), ("TCP", 53)}


def test_every_workload_is_selected_by_a_named_policy():
    names = {
        doc["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"]
        for doc in _of("NetworkPolicy")
        if doc["spec"]["podSelector"]
    }
    assert names == set(WORKLOADS)


def test_ingress_edges_are_exactly_the_contract():
    expected = {"api": ({"frontend"}, 8000), "receiver": ({"api"}, 8091), "postgres": ({"api"}, 5432)}
    for name, (sources, port) in expected.items():
        (rule,) = _named("NetworkPolicy", name)["spec"]["ingress"]
        assert _selected_names(rule["from"]) == sources, name
        assert _ports(rule) == {("TCP", port)}, name
    (frontend_rule,) = _named("NetworkPolicy", "frontend")["spec"]["ingress"]
    assert "from" not in frontend_rule, "frontend is the public entry point"
    assert _ports(frontend_rule) == {("TCP", 5173)}


def test_egress_edges_are_exactly_the_contract():
    (frontend_rule,) = _named("NetworkPolicy", "frontend")["spec"]["egress"]
    assert _selected_names(frontend_rule["to"]) == {"api"}
    assert _ports(frontend_rule) == {("TCP", 8000)}

    rules = _named("NetworkPolicy", "api")["spec"]["egress"]
    pod_rules = {
        next(iter(_selected_names(rule["to"]))): _ports(rule)
        for rule in rules
        if "podSelector" in rule["to"][0]
    }
    assert pod_rules == {
        "postgres": {("TCP", 5432)},
        "receiver": {("TCP", 8091)},
        "frontend": {("TCP", 5173)},  # GET /healthz probe behind the /runtime page
    }
    (internet,) = (rule for rule in rules if "ipBlock" in rule["to"][0])
    assert _ports(internet) == {("TCP", 443)}
    assert internet["to"][0]["ipBlock"]["cidr"] == "0.0.0.0/0"
    private = {"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16"}
    assert private <= set(internet["to"][0]["ipBlock"]["except"]), "443 must be public-only"

    # The receiver and the database initiate nothing: only ingress is declared for them, so the
    # namespace-wide default-deny covers their egress.
    for name in ("receiver", "postgres"):
        assert _named("NetworkPolicy", name)["spec"]["policyTypes"] == ["Ingress"]


# --- the orchestrator agrees with the manifests ----------------------------------------------------


def test_orchestrator_constants_match_the_manifests():
    cluster = _orchestrator()
    kind_config = yaml.safe_load((K8S / "kind-config.yaml").read_text(encoding="utf-8"))
    postgres_env = _env(_main("postgres"))
    schema = next(v for v in _spec("postgres")["volumes"] if v["name"] == "schema")
    node_port = _named("Service", "frontend")["spec"]["ports"][0]["nodePort"]
    host_port = kind_config["nodes"][0]["extraPortMappings"][0]["hostPort"]
    assert _named("Namespace", "clinicase")["metadata"]["name"] == cluster.NAMESPACE
    assert (API_IMAGE, WEB_IMAGE, POSTGRES_IMAGE) == (
        cluster.API_IMAGE,
        cluster.WEB_IMAGE,
        cluster.POSTGRES_IMAGE,
    )
    assert schema["configMap"]["name"] == cluster.SCHEMA_CONFIGMAP
    assert postgres_env["POSTGRES_USER"]["value"] == cluster.DB_USER
    assert postgres_env["POSTGRES_DB"]["value"] == cluster.DB_NAME
    assert (node_port, host_port) == (cluster.NODE_PORT, cluster.DEFAULT_HOST_PORT)
    assert (kind_config["name"], f"kind-{kind_config['name']}") == (cluster.CLUSTER, cluster.CONTEXT)
    for resource, _seconds in cluster.ROLLOUTS:
        kind, name = resource.split("/")
        assert WORKLOADS[name]["kind"].lower() == kind
    secret_names = {
        ref["name"]
        for _, _, c in CONTAINERS
        for item in c.get("env", [])
        if (ref := item.get("valueFrom", {}).get("secretKeyRef"))
    }
    assert secret_names == {cluster.SECRET_NAME}
    source = (K8S / "cluster.py").read_text(encoding="utf-8")
    for key in SECRET_KEYS:
        assert f'"{key}"' in source, f"cluster.py does not generate {key}"


@pytest.mark.parametrize("context", ["backend", "frontend"])
def test_build_ca_injection_touches_only_the_first_stage_and_keeps_every_original_line(context):
    cluster = _orchestrator()
    original = (ROOT / context / "Dockerfile").read_text(encoding="utf-8").splitlines()
    derived = cluster.with_build_ca("\n".join(original) + "\n").splitlines()
    first_from = next(i for i, line in enumerate(original) if line.upper().startswith("FROM "))
    inserted = list(cluster.BUILD_CA_STEPS)
    assert derived[: first_from + 1] == original[: first_from + 1]
    assert derived[first_from + 1 : first_from + 1 + len(inserted)] == inserted
    assert derived[first_from + 1 + len(inserted) :] == original[first_from + 1 :]
    assert inserted[0].startswith("COPY --from=buildca ")


def test_kubectl_transports_are_pinned_to_the_kind_cluster():
    """Host kubectl never relies on the current context; the in-node fallback uses the node's own admin kubeconfig."""
    cluster = _orchestrator()
    args = ("get", "pods")
    host = cluster.kubectl_command(args, via_node=False)
    node = cluster.kubectl_command(args, via_node=True)
    assert host == ["kubectl", "--context", "kind-clinicase", "-n", "clinicase", "get", "pods"]
    assert node[:5] == ["docker", "exec", "-i", "clinicase-control-plane", "kubectl"]
    assert node[5:] == ["--kubeconfig", "/etc/kubernetes/admin.conf", "-n", "clinicase", "get", "pods"]
    assert "x509: certificate signed by unknown authority" in cluster.TLS_INSPECTION_MARKERS


def test_orchestrator_is_stdlib_only_and_never_uses_a_shell():
    source = (K8S / "cluster.py").read_text(encoding="utf-8")
    imported = set()
    shell_calls = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            shell_calls += [
                kw for kw in node.keywords if kw.arg == "shell" and getattr(kw.value, "value", None)
            ]
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
    assert shell_calls == []
    assert "os.system" not in source
    assert "secrets.token_urlsafe(32)" in source
