#!/usr/bin/env python3
"""Local Kubernetes (kind) orchestration for the WHOLE CLINI-CASE stack.

    python k8s/cluster.py up            # cluster + images + secrets + deploy, wait until Ready
    python k8s/cluster.py verify        # health, login, Track 7 network demo, NetworkPolicy proof
    python k8s/cluster.py credentials   # print the demo login (explicit opt-in)
    python k8s/cluster.py down          # delete the cluster and everything in it

Python 3.11+, standard library only. External tools: docker, kubectl and kind (`--kind PATH` or the
KIND environment variable). Local use only: no registry, no cloud, no shell=True. Secrets are generated
here, handed to kubectl on stdin, and never printed or placed on a command line.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = ROOT / "k8s"
SCHEMA_FILE = ROOT / "backend" / "db" / "schema.sql"
DEMO_SCRIPT = ROOT / "backend" / "scripts" / "interop_demo.py"

CLUSTER = "clinicase"
CONTEXT = f"kind-{CLUSTER}"  # every kubectl call is pinned to this context, never "whatever is current"
NODE_CONTAINER = f"{CLUSTER}-control-plane"
NAMESPACE = "clinicase"
API_IMAGE, WEB_IMAGE = "clinicase-api:local", "clinicase-web:local"
POSTGRES_IMAGE = "pgvector/pgvector:pg16"  # keep in sync with k8s/postgres.yaml
SECRET_NAME, SCHEMA_CONFIGMAP = "clinicase-secrets", "clinicase-db-schema"
IMAGE_IDS_ANNOTATION = "clinicase.local/image-ids"  # on the node: content ids of the images last loaded
DB_USER = DB_NAME = "clincase"  # must match POSTGRES_USER / POSTGRES_DB in k8s/postgres.yaml
NODE_PORT, DEFAULT_HOST_PORT = 30080, 8080
DEMO_EMAIL = "reviewer@clincase.health"
# (resource, timeout in seconds) in dependency order.
ROLLOUTS = (
    ("statefulset/postgres", 300),
    ("deployment/receiver", 240),
    ("deployment/api", 420),
    ("deployment/frontend", 240),
)


class ClusterError(RuntimeError):
    """A failure whose message is safe to show: it never contains secret values."""


def say(message: str) -> None:
    print(f"[cluster] {message}", flush=True)


def run(
    cmd: list[str],
    *,
    timeout: int,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    stream: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run one external tool (no shell) with a timeout; capture its output unless `stream`."""
    cmd = [shutil.which(cmd[0]) or cmd[0], *cmd[1:]]
    try:
        return subprocess.run(
            cmd,
            input=stdin,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=check,
            capture_output=not stream,
        )
    except FileNotFoundError:
        raise ClusterError(f"required tool not found: {cmd[0]} (install it or fix PATH)") from None
    except subprocess.TimeoutExpired:
        raise ClusterError(f"timed out after {timeout}s: {Path(cmd[0]).name} {' '.join(cmd[1:3])}") from None
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or exc.stdout or "").strip().splitlines()[-8:]
        head = f"{Path(cmd[0]).name} {' '.join(cmd[1:3])} failed (exit {exc.returncode})"
        raise ClusterError("\n  ".join([head, *tail])) from None


# kubectl's wording when something between it and the API server presents a certificate its kubeconfig does
# not trust. A TLS-inspecting antivirus re-signs the loopback connection to the kind API server for minutes at
# a time (seen with AVG, typically right after a build or image load). The call is then repeated with the
# kubectl inside the kind node (`docker exec`), which reaches the API server over the node's own loopback, and
# the rest of the run stays on that path.
TLS_INSPECTION_MARKERS = ("x509: certificate signed by unknown authority", "failed to verify certificate")
NODE_KUBECONFIG = "/etc/kubernetes/admin.conf"
TRANSPORT = {"via_node": False}


def kubectl_command(args: tuple[str, ...], *, via_node: bool) -> list[str]:
    if via_node:
        node = ["docker", "exec", "-i", NODE_CONTAINER, "kubectl", "--kubeconfig", NODE_KUBECONFIG]
        return [*node, "-n", NAMESPACE, *args]
    return ["kubectl", "--context", CONTEXT, "-n", NAMESPACE, *args]  # never "whatever context is current"


def kubectl(
    *args: str, timeout: int = 60, check: bool = True, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """kubectl for the kind cluster (pinned context, app namespace); `stdin` carries manifests and secrets."""
    while True:
        via_node = TRANSPORT["via_node"]
        result = run(kubectl_command(args, via_node=via_node), timeout=timeout, stdin=stdin or "", check=False)
        if via_node or result.returncode == 0 or not any(m in result.stderr for m in TLS_INSPECTION_MARKERS):
            break
        say("host kubectl cannot verify the API server certificate (antivirus HTTPS inspection?)")
        say("using the kubectl inside the kind node for the rest of this run")
        TRANSPORT["via_node"] = True
    if check and result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-8:]
        raise ClusterError("\n  ".join([f"kubectl {' '.join(args[:2])} failed (exit {result.returncode})", *tail]))
    return result


def expect(condition: bool, ok: str, failure: str) -> str:
    if not condition:
        raise ClusterError(failure)
    return ok


# --------------------------------------------------------------------------------------- up


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def host_port() -> int:
    """The host port the running cluster publishes for the frontend NodePort."""
    out = run(["docker", "port", NODE_CONTAINER, f"{NODE_PORT}/tcp"], timeout=30, check=False).stdout
    match = re.search(r":(\d+)\s*$", out.strip().splitlines()[0]) if out.strip() else None
    return int(match.group(1)) if match else DEFAULT_HOST_PORT


def ensure_cluster(kind: str, port: int) -> None:
    if CLUSTER in run([kind, "get", "clusters"], timeout=60).stdout.split():
        say(f"kind cluster '{CLUSTER}' already exists; reusing it (frontend on host port {host_port()})")
        return
    if port_in_use(port):
        raise ClusterError(f"host port {port} is already in use; free it or run: up --host-port <free port>")
    config = re.sub(r"hostPort:\s*\d+", f"hostPort: {port}", (K8S_DIR / "kind-config.yaml").read_text("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "kind-config.yaml"
        path.write_text(config, encoding="utf-8")
        say(f"creating kind cluster '{CLUSTER}' (first run downloads the node image)")
        run([kind, "create", "cluster", "--config", str(path), "--wait", "180s"], timeout=1200, stream=True)


def image_id(tag: str) -> str:
    """Content identity of a local image: its config and layer digests, "" when it does not exist.

    The engine's own `.Id` is not usable: with Docker's containerd image store it is the index digest, which
    changes on every build because BuildKit adds a provenance attestation, even when every layer was cached.
    """
    fmt = "{{json .Config}}{{json .RootFS.Layers}}"
    result = run(["docker", "image", "inspect", "--format", fmt, tag], timeout=30, check=False)
    return hashlib.sha256(result.stdout.encode()).hexdigest()[:24] if result.returncode == 0 else ""


# Added after the FIRST `FROM` of a Dockerfile (the stage that runs pip / npm) when --build-ca is used.
BUILD_CA_STEPS = (
    "COPY --from=buildca ca.pem /usr/local/share/build-ca.pem",
    "RUN cat /etc/ssl/certs/ca-certificates.crt /usr/local/share/build-ca.pem"
    " > /usr/local/share/build-bundle.pem",
    "ENV PIP_CERT=/usr/local/share/build-bundle.pem NODE_EXTRA_CA_CERTS=/usr/local/share/build-ca.pem",
)


def with_build_ca(dockerfile: str) -> str:
    """The same Dockerfile, with pip and npm told to trust the extra root CA in its first stage only."""
    lines = dockerfile.splitlines()
    first_stage = next(i for i, line in enumerate(lines) if line.upper().startswith("FROM ")) + 1
    return "\n".join([*lines[:first_stage], *BUILD_CA_STEPS, *lines[first_stage:]]) + "\n"


def build_image(tag: str, context: Path, build_ca: Path | None, timeout: int) -> None:
    """`docker build` `context`, optionally with an extra root CA that pip/npm trust during the build.

    A TLS-inspecting antivirus or proxy re-signs HTTPS with a root the build containers do not trust, so
    `pip install` / `npm ci` fail with CERTIFICATE_VERIFY_FAILED. The repo's Dockerfiles stay untouched: a
    derived Dockerfile in a temp dir gets the certificate through a BuildKit named context.
    """
    with tempfile.TemporaryDirectory() as tmp:
        command = ["docker", "build", "-t", tag]
        if build_ca:
            work = Path(tmp)
            shutil.copyfile(build_ca, work / "ca.pem")
            original = (context / "Dockerfile").read_text(encoding="utf-8")
            (work / "Dockerfile").write_text(with_build_ca(original), encoding="utf-8")
            command += ["-f", str(work / "Dockerfile"), "--build-context", f"buildca={work}"]
        try:
            run([*command, str(context)], timeout=timeout, stream=True)
        except ClusterError as exc:
            hint = "" if build_ca else (
                "\n  If the log above shows CERTIFICATE_VERIFY_FAILED, an antivirus or proxy is re-signing HTTPS:"
                " export its root CA as PEM and pass --build-ca (see docs/KUBERNETES.md, Troubleshooting)"
            )  # fmt: skip
            raise ClusterError(f"{exc}{hint}") from None


def build_images(build_ca: Path | None) -> None:
    if build_ca and not build_ca.is_file():
        raise ClusterError(f"--build-ca file not found: {build_ca}")
    say(f"building {API_IMAGE} (backend/Dockerfile; also runs the receiver)")
    build_image(API_IMAGE, ROOT / "backend", build_ca, timeout=2400)
    say(f"building {WEB_IMAGE} (frontend/Dockerfile)")
    build_image(WEB_IMAGE, ROOT / "frontend", build_ca, timeout=1800)


def loaded_image_ids() -> dict[str, str]:
    """{tag: docker image id} recorded on the node by the last successful load."""
    node = json.loads(kubectl("get", "node", NODE_CONTAINER, "-o", "json").stdout)
    value = node["metadata"].get("annotations", {}).get(IMAGE_IDS_ANNOTATION, "")
    return dict(pair.rsplit("=", 1) for pair in value.split(",") if "=" in pair)


def load_images(kind: str) -> tuple[bool, str | None]:
    """Side-load local images that are new or changed since the last load.

    Returns (restart, record): whether an app image was loaded, and the annotation value to store via
    `record_loaded` once the deploy has succeeded. Recording earlier would let a failed rollout be
    mistaken for success on the next run, leaving pods on the old :local image.

    `kind load docker-image` imports every platform in an image index, but Docker's containerd image store
    keeps BuildKit attestation manifests (and other platforms' manifests of pulled images) whose blobs are not
    exported, so it fails with "ctr: content digest ... not found" after minutes. Saving the daemon's own
    platform to an archive and loading that is fast and avoids it; engines without `docker save --platform`
    fall back to the plain command.
    """
    wanted = {tag: image_id(tag) for tag in (API_IMAGE, WEB_IMAGE, POSTGRES_IMAGE)}
    wanted = {tag: ident for tag, ident in wanted.items() if ident}  # postgres is side-loaded only if cached
    loaded = loaded_image_ids()
    stale = [tag for tag, ident in wanted.items() if loaded.get(tag) != ident]
    if not stale:
        say("images already on the node; nothing to load")
        return False, None
    say(f"loading {', '.join(stale)} into the cluster")
    daemon = run(["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"], timeout=30).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "images.tar"
        saved = run(["docker", "save", "--platform", daemon, "-o", str(archive), *stale], timeout=1800, check=False)
        if saved.returncode == 0:
            run([kind, "load", "image-archive", str(archive), "--name", CLUSTER], timeout=1800, stream=True)
        else:
            run([kind, "load", "docker-image", *stale, "--name", CLUSTER], timeout=1800, stream=True)
    record = ",".join(f"{tag}={ident}" for tag, ident in {**loaded, **wanted}.items())
    return any(tag in (API_IMAGE, WEB_IMAGE) for tag in stale), record


def record_loaded(record: str | None) -> None:
    if record:
        kubectl("annotate", "node", NODE_CONTAINER, "--overwrite", f"{IMAGE_IDS_ANNOTATION}={record}")


def ensure_secret() -> None:
    """Create clinicase-secrets only when absent: re-running `up` must never rotate live credentials."""
    if kubectl("get", "secret", SECRET_NAME, check=False).returncode == 0:
        say(f"secret {SECRET_NAME} already exists; keeping it")
        return
    db_password = secrets.token_urlsafe(32)
    manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": SECRET_NAME,
            "namespace": NAMESPACE,
            "labels": {"app.kubernetes.io/part-of": "clinicase"},
        },
        "stringData": {
            "POSTGRES_PASSWORD": db_password,
            "DATABASE_URL": f"postgresql://{DB_USER}:{quote(db_password, safe='')}@postgres:5432/{DB_NAME}",
            "JWT_SECRET": secrets.token_urlsafe(32),
            "INTEROP_RECEIVER_TOKEN": secrets.token_urlsafe(32),
            "DEMO_USER_PASSWORD": secrets.token_urlsafe(32),
        },
    }
    kubectl("create", "-f", "-", stdin=json.dumps(manifest))  # values travel on stdin, not argv
    say(f"generated secret {SECRET_NAME} (random values, kept only in the cluster)")


def refresh_configmap(name: str, source: str, origin: Path) -> None:
    """Create or update a ConfigMap straight from files in the repo (never committed as YAML)."""
    # Rendered on the host (client-side only, no API server involved: the files live there), applied via stdin.
    create = ["kubectl", "-n", NAMESPACE, "create", "configmap", name, source, "--dry-run=client", "-o", "yaml"]
    kubectl("apply", "-f", "-", stdin=run(create, timeout=60).stdout)
    kubectl("label", "configmap", name, "app.kubernetes.io/part-of=clinicase", "--overwrite")
    say(f"configmap {name} refreshed from {origin.relative_to(ROOT).as_posix()}")


def refresh_configmaps() -> None:
    # postgres runs the schema from /docker-entrypoint-initdb.d on first start of an empty volume.
    refresh_configmap(SCHEMA_CONFIGMAP, f"--from-file=01-schema.sql={SCHEMA_FILE}", SCHEMA_FILE)


def diagnose() -> None:
    """Print what an operator would look at first when a rollout does not become Ready."""
    print(kubectl("get", "pods", "-o", "wide", check=False).stdout)
    events = kubectl("get", "events", "--sort-by=.lastTimestamp", check=False).stdout.splitlines()
    print("\n".join(events[-12:]))
    pods = json.loads(kubectl("get", "pods", "-o", "json", check=False).stdout or '{"items": []}')
    for pod in pods["items"]:
        statuses = pod["status"].get("initContainerStatuses", []) + pod["status"].get("containerStatuses", [])
        for status in statuses:
            if not status.get("ready") and "terminated" not in status.get("state", {}):
                name = pod["metadata"]["name"]
                print(f"--- logs {name}/{status['name']}")
                print(kubectl("logs", name, "-c", status["name"], "--tail=15", check=False).stdout)


def deploy(restart: bool) -> None:
    kubectl("apply", "-f", "-", stdin=(K8S_DIR / "namespace.yaml").read_text(encoding="utf-8"))
    ensure_secret()
    refresh_configmaps()
    existed = kubectl("get", "deployment", "api", check=False).returncode == 0
    manifests = run(["kubectl", "kustomize", str(K8S_DIR)], timeout=60).stdout  # offline render of k8s/
    applied = kubectl("apply", "-f", "-", stdin=manifests, timeout=120)
    print(applied.stdout.strip())
    if applied.stderr.strip():  # e.g. Pod Security Admission warnings, which would name a violating pod
        print(applied.stderr.strip(), file=sys.stderr)
    if restart and existed:  # a rebuilt image under the same :local tag is only picked up by new pods
        say("images changed: restarting api, receiver and frontend")
        kubectl("rollout", "restart", "deployment/api", "deployment/receiver", "deployment/frontend")
    for resource, seconds in ROLLOUTS:
        say(f"waiting for {resource} (up to {seconds}s)")
        try:
            kubectl("rollout", "status", resource, f"--timeout={seconds}s", timeout=seconds + 30)
        except ClusterError:
            diagnose()
            raise


def cmd_up(args: argparse.Namespace) -> int:
    run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=60)  # fails fast if the engine is down
    ensure_cluster(args.kind, args.host_port)
    if args.skip_build:
        missing = [tag for tag in (API_IMAGE, WEB_IMAGE) if not image_id(tag)]
        if missing:
            raise ClusterError(f"--skip-build but image(s) not built yet: {', '.join(missing)}")
    else:
        build_images(Path(args.build_ca) if args.build_ca else None)
    restart, record = load_images(args.kind)
    deploy(restart=restart)
    record_loaded(record)  # only after a successful rollout, so a failed run is retried in full
    print(kubectl("get", "pods", "-o", "wide").stdout)
    say(f"ready: http://localhost:{host_port()}  (next: python k8s/cluster.py verify)")
    return 0


# ----------------------------------------------------------------------------------- verify


def http(
    method: str, url: str, body: dict | None = None, *, token: str | None = None, timeout: int = 20
) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def secret_value(key: str) -> str:
    encoded = kubectl("get", "secret", SECRET_NAME, "-o", f"jsonpath={{.data.{key}}}").stdout
    return base64.b64decode(encoded).decode()


def probe_tcp(workload: str, host: str, port: int) -> bool:
    """True if `workload`'s pod can open a TCP connection to host:port (a timeout counts as blocked)."""
    if workload == "frontend":  # nginx:alpine has busybox nc and no python
        cmd = ["sh", "-c", f"nc -w 3 {host} {port} </dev/null && echo connected || echo blocked"]
    else:  # api image (also used by the receiver): python is always there
        code = (
            "import socket;s=socket.socket();s.settimeout(3)"
            f";print('connected' if s.connect_ex(('{host}',{port}))==0 else 'blocked')"
        )
        cmd = ["python", "-c", code]
    out = kubectl("exec", f"deploy/{workload}", "--", *cmd, timeout=60).stdout.strip().splitlines()
    return bool(out) and out[-1] == "connected"


def service_ip(name: str) -> str:
    return kubectl("get", "service", name, "-o", "jsonpath={.spec.clusterIP}").stdout.strip()


def check_get(base: str, path: str, exact: str | None = None) -> str:
    status, body = http("GET", base + path)
    ok = status == 200 and (exact is None or body.strip() == exact)  # nginx would answer an unknown path with the SPA
    return expect(ok, f"HTTP 200 {body.strip()[:60]}", f"HTTP {status} {body.strip()[:80]}")


def login(base: str, password: str) -> tuple[int, str | None]:
    credentials = {"email": DEMO_EMAIL, "password": password}
    status, body = http("POST", f"{base}/api/v1/auth/login", credentials)
    return status, (json.loads(body).get("access_token") if status == 200 else None)


def check_login(base: str, password: str) -> str:
    status, token = login(base, password)
    return expect(bool(token), "HTTP 200 token issued", f"HTTP {status}")


def check_runtime(base: str, password: str) -> str:
    """The api's own view of the cluster: Downward API identity plus live probes of its peers."""
    _, token = login(base, password)
    status, body = http("GET", f"{base}/api/v1/runtime", token=token)
    expect(status == 200, "", f"HTTP {status}")
    data = json.loads(body)
    services = data.get("services", [])
    down = [s.get("id") for s in services if s.get("status") != "up"]
    pod = (data.get("platform") or {}).get("pod")
    expect(data.get("live") is True and bool(pod), "", f"not running as a pod (live={data.get('live')})")
    expect(bool(services) and not down, "", f"services not up: {', '.join(map(str, down)) or 'none listed'}")
    return f"{data.get('label')}; pod {pod}; up: {', '.join(s['id'] for s in services)}"


def check_demo(base: str, password: str, python: str) -> str:
    env = {**os.environ, "DEMO_USER_PASSWORD": password, "PYTHONIOENCODING": "utf-8"}  # env, not argv
    proc = run([python, str(DEMO_SCRIPT), "--base-url", base], timeout=900, env=env, check=False)
    if proc.returncode != 0:
        tail = " | ".join(proc.stderr.replace(password, "***").strip().splitlines()[-3:])
        raise ClusterError(f"interop_demo.py exit {proc.returncode}: {tail[:240]}")
    start = proc.stdout.rfind("\n{\n") + 1  # the pretty-printed result, after any log lines
    result = json.loads(proc.stdout[start:])
    mode = result.get("receiver_mode")
    expect(mode == "HTTP network", "", f"receiver_mode={mode!r}, expected 'HTTP network'")
    return f"receiver_mode={mode}; round-trip {result['roundtrip_status']}; retest {result['retest_exchange_status']}"


def check_connect(workload: str, target: str, port: int, *, allowed: bool) -> str:
    connected = probe_tcp(workload, service_ip(target), port)
    if connected == allowed:
        return "connected" if allowed else "blocked (connection did not complete)"
    if allowed:
        raise ClusterError("expected connection was refused: policy too strict")
    raise ClusterError("connection succeeded: NetworkPolicy is NOT enforced by this cluster's CNI")


# (from workload, to service, port, expected to connect). Each denied edge is paired with an allowed
# one from the same tool, so a "blocked" result cannot be a broken probe.
NETPOL_EDGES = (
    ("frontend", "api", 8000, True),
    ("frontend", "postgres", 5432, False),
    ("api", "postgres", 5432, True),
    ("receiver", "postgres", 5432, False),
)


def cmd_verify(args: argparse.Namespace) -> int:
    # 127.0.0.1, not "localhost": the kind mapping listens on IPv4 loopback only, and on Windows a "localhost"
    # lookup tries ::1 first, adding about two seconds to every new connection.
    base = f"http://127.0.0.1:{host_port()}"
    say(f"verifying the cluster through {base} (frontend NodePort {NODE_PORT}) and kubectl exec")
    password = secret_value("DEMO_USER_PASSWORD")
    checks: list[tuple[str, Callable[[], str]]] = [
        ("web  GET /healthz via NodePort", lambda: check_get(base, "/healthz", exact="ok")),
        ("api  GET /api/v1/healthz via nginx", lambda: check_get(base, "/api/v1/healthz")),
        ("api  GET /api/v1/readyz via nginx", lambda: check_get(base, "/api/v1/readyz")),
        (f"auth POST login {DEMO_EMAIL}", lambda: check_login(base, password)),
        ("api  GET /api/v1/runtime (live topology)", lambda: check_runtime(base, password)),
        ("Track 7 interop_demo.py over HTTP", lambda: check_demo(base, password, args.python)),
    ]
    for src, dst, port, allowed in NETPOL_EDGES:
        label = f"netpol {src} -> {dst}:{port} {'allowed' if allowed else 'denied'}"
        checks.append((label, lambda s=src, d=dst, p=port, a=allowed: check_connect(s, d, p, allowed=a)))
    rows = []
    for name, check in checks:
        started = time.monotonic()
        try:
            rows.append((name, True, check()))
        except (ClusterError, OSError, ValueError, KeyError, AttributeError) as exc:
            message = (str(exc) or type(exc).__name__).replace(password, "***")
            rows.append((name, False, message.splitlines()[0]))
        say(f"{'PASS' if rows[-1][1] else 'FAIL'} {name} ({time.monotonic() - started:.1f}s)")
    width = max(len(name) for name, *_ in rows)
    print(f"\n{'CHECK'.ljust(width)}  RESULT  DETAIL")
    for name, ok, detail in rows:
        print(f"{name.ljust(width)}  {'PASS  ' if ok else 'FAIL  '}  {detail}")
    failed = [name for name, ok, _ in rows if not ok]
    summary = f"{len(rows) - len(failed)}/{len(rows)} checks passed"
    print(f"\n{summary}" + (f"; {len(failed)} FAILED" if failed else ""))
    return 1 if failed else 0


# ------------------------------------------------------------------- credentials and down


def cmd_credentials(_args: argparse.Namespace) -> int:
    print(f"URL:      http://localhost:{host_port()}")
    print(f"Email:    {DEMO_EMAIL}  (also admin@clincase.health, coordinator@clincase.health)")
    print(f"Password: {secret_value('DEMO_USER_PASSWORD')}")
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    say(f"deleting kind cluster '{CLUSTER}' (all pods, volumes and the generated secret go with it)")
    run([args.kind, "delete", "cluster", "--name", CLUSTER], timeout=300, stream=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--kind", default=os.environ.get("KIND", "kind"), help="kind binary (env KIND; default: kind)")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up", parents=[common], help="create the cluster and deploy the whole stack (idempotent)")
    up.add_argument("--skip-build", action="store_true", help="reuse existing local images")
    up.add_argument(
        "--build-ca", default=os.environ.get("CLINICASE_BUILD_CA"), metavar="PEM",
        help="extra root CA (PEM) for pip/npm during image builds, for TLS-inspecting antivirus or proxies",
    )  # fmt: skip
    up.add_argument(
        "--host-port", type=int, default=int(os.environ.get("CLINICASE_HOST_PORT", DEFAULT_HOST_PORT)),
        help="host port for the frontend when creating the cluster (default 8080)",
    )  # fmt: skip
    verify = sub.add_parser("verify", parents=[common], help="health, login, Track 7 demo, NetworkPolicy checks")
    verify.add_argument("--python", default=sys.executable, help="interpreter with the backend deps for interop_demo.py")
    sub.add_parser("credentials", parents=[common], help="print the demo login")
    sub.add_parser("down", parents=[common], help="delete the kind cluster")
    args = parser.parse_args(argv)
    commands = {"up": cmd_up, "verify": cmd_verify, "credentials": cmd_credentials, "down": cmd_down}
    try:
        return commands[args.command](args)
    except ClusterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
