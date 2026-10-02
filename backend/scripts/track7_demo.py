"""One-command local Track 7 demo; starts owned processes and preserves existing users."""

import argparse
import asyncio
import base64
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CACHE = BACKEND / ".cache/track7"


def demo_signing_key() -> str:
    """A persistent demo-only Ed25519 seed, so passports exported earlier still verify after a restart."""
    path = CACHE / "passport-signing.key"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(base64.b64encode(secrets.token_bytes(32)).decode("ascii"), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def available(port: int) -> None:
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"Port {port} is already used; stop that service or select another demo port. No existing process was stopped."
            ) from exc


async def wait_url(url: str, process: subprocess.Popen, startup_seconds: int = 120) -> None:
    async with httpx.AsyncClient(timeout=2) as client:
        deadline = time.monotonic() + startup_seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Demo service exited; inspect backend/.cache/track7 logs")
            try:
                if (await client.get(url)).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise RuntimeError("Demo service startup timed out; inspect backend/.cache/track7 logs")


async def seed_user(dsn: str, email: str, password: str) -> None:
    import asyncpg

    from app.auth import hash_password

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO organizations(id,name,slug) VALUES ('org_demo','ClinCase Demo Health','clincase-demo') ON CONFLICT DO NOTHING"
        )
        await conn.execute(
            "INSERT INTO users(id,email,password_hash,full_name,organization_id,role) VALUES ($1,$2,$3,'Synthetic Track 7 reviewer','org_demo','reviewer')",
            "track7-" + secrets.token_hex(12),
            email,
            hash_password(password),
        )
    finally:
        await conn.close()


async def main(args) -> None:
    from interop_demo import demo

    CACHE.mkdir(parents=True, exist_ok=True)
    ports = (args.api_port, args.receiver_port)
    if not args.network_only:
        ports += (args.frontend_port,)
    for port in ports:
        available(port)
    password = secrets.token_urlsafe(24)
    email = "track7-" + secrets.token_hex(6) + "@clincase.health"
    token = secrets.token_urlsafe(32)
    dsn = os.getenv(
        "TRACK7_DATABASE_URL", "postgresql://clincase:clincase@127.0.0.1:15432/clincase"
    )
    if not args.sqlite:
        if not shutil.which("docker"):
            raise RuntimeError(
                "Docker is required for PostgreSQL. Install/start Docker or use --sqlite (synthetic deterministic mode only)."
            )
        await asyncio.to_thread(
            subprocess.run, ["docker", "compose", "up", "-d", "postgres"], cwd=ROOT, check=True
        )
    base = f"http://127.0.0.1:{args.api_port}"
    frontend = f"http://127.0.0.1:{args.frontend_port}"
    env = {
        **os.environ,
        "ENVIRONMENT": "dev",
        "DATABASE_URL": "postgresql://disabled/demo" if args.sqlite else dsn,
        "AUTH_DBLESS_DEMO_ENABLED": "true" if args.sqlite else "false",
        "DEMO_USER_PASSWORD": password,
        "JWT_SECRET": secrets.token_urlsafe(48),
        "INTEROP_RECEIVER_TOKEN": token,
        "PASSPORT_SIGNING_KEY": os.environ.get("PASSPORT_SIGNING_KEY") or demo_signing_key(),
        "INTEROP_RECEIVER_URL": f"http://127.0.0.1:{args.receiver_port}",
        "INTEROP_RECEIVER_DB": str(CACHE / "receiver.sqlite"),
        "TRACK7_DEMO_DB": str(CACHE / "evidence.sqlite") if args.sqlite else "",
        "CORS_ORIGINS": frontend,
        "VITE_API_BASE": base,
        "NODE_OPTIONS": "--use-system-ca",
    }
    if os.name == "nt":
        # Match Windows' existing trusted roots (including local TLS inspection).
        # Certificate verification stays enabled; no global trust store is changed.
        import certifi

        roots = Path(certifi.where()).read_text(encoding="ascii")
        for certificate, encoding, _trust in ssl.enum_certificates("ROOT"):
            if encoding == "x509_asn":
                roots += ssl.DER_cert_to_PEM_cert(certificate)
        bundle_path = CACHE / "trusted-windows-roots.pem"
        bundle_path.write_text(roots, encoding="ascii")
        env["SSL_CERT_FILE"] = str(bundle_path)
    if args.sqlite:
        email = "reviewer@clincase.health"
    (CACHE / "demo-login.json").write_text(
        json.dumps({"email": email, "password": password, "frontend": frontend}, indent=2),
        encoding="utf-8",
    )
    processes = []
    logs = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def start(command, cwd, name):
        log = (CACHE / (name + ".log")).open("w", encoding="utf-8")
        logs.append(log)
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags
        )
        processes.append(process)
        return process

    try:
        receiver = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.interop.receiver:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.receiver_port),
            ],
            BACKEND,
            "receiver",
        )
        await wait_url(env["INTEROP_RECEIVER_URL"] + "/openapi.json", receiver)
        gateway = start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.api_port),
            ],
            BACKEND,
            "gateway",
        )
        await wait_url(base + "/api/v1/healthz", gateway)
        if not args.sqlite:
            # Seed a unique reviewer instead of changing passwords of any existing account.
            await seed_user(dsn, email, password)
        print("Gateway and independent receiver ready.", flush=True)
        if not args.network_only:
            npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
            if not npm:
                raise RuntimeError("Node/npm required; install Node 20+ and run npm ci in frontend")
            if not (ROOT / "frontend/node_modules").exists():
                await asyncio.to_thread(
                    subprocess.run,
                    [npm, "ci"],
                    cwd=ROOT / "frontend",
                    env=env,
                    check=True,
                    creationflags=flags,
                )
            ui = start(
                [
                    npm,
                    "run",
                    "dev",
                    "--",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.frontend_port),
                    "--strictPort",
                ],
                ROOT / "frontend",
                "frontend",
            )
            await wait_url(frontend, ui)
        print(
            "Track 7 services ready: PostgreSQL"
            if not args.sqlite
            else "Track 7 services ready: durable SYNTHETIC-only SQLite"
        )
        print(
            "Private local login: backend/.cache/track7/demo-login.json (ignored by Git)",
            flush=True,
        )
        await demo(argparse.Namespace(base_url=base, email=email, password=password, ai=args.ai))
        if args.open:
            webbrowser.open(frontend + "/onehealth")
        if args.keep_running:
            print("Demo remains running. Ctrl+C stops only the processes started by this command.")
            await asyncio.gather(*(asyncio.to_thread(p.wait) for p in processes))
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs:
            log.close()


if __name__ == "__main__":
    sys.path.insert(0, str(BACKEND))
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", action="store_true")
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--network-only", action="store_true", help="Skip the frontend process")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--receiver-port", type=int, default=8091)
    parser.add_argument("--frontend-port", type=int, default=5173)
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        print("Track 7 demo stopped")
