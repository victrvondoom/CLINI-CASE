"""One-shot deployer: upload frontend/dist/ to s3://clincase-demo-26697/."""
from __future__ import annotations

import mimetypes
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv("../.env")

BUCKET = "clincase-demo-26697"
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

# Map Vite's index.html → ClinCase.html so it matches the bucket's IndexDocument
RENAMES = {"index.html": "ClinCase.html"}

# Cache headers — assets are content-hashed, so they can be cached aggressively;
# index.html must NOT be cached so users see the latest deploy.
CACHE_LONG = "public, max-age=31536000, immutable"
CACHE_NONE = "no-cache, no-store, must-revalidate"


def main() -> int:
    s3 = boto3.client("s3")
    if not DIST.exists():
        print(f"ERROR: {DIST} not found — run `npm run build` in frontend/ first.")
        return 1

    n_uploaded = 0
    total_bytes = 0
    for fp in DIST.rglob("*"):
        if not fp.is_file():
            continue
        rel = fp.relative_to(DIST).as_posix()
        s3_key = RENAMES.get(rel, rel)
        body = fp.read_bytes()
        ctype, _ = mimetypes.guess_type(s3_key)
        if ctype is None:
            ctype = "application/octet-stream"
        cache = CACHE_LONG if "/assets/" in rel else CACHE_NONE
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=body,
            ContentType=ctype,
            CacheControl=cache,
        )
        print(f"  PUT {s3_key:50s}  {len(body) // 1024} KB  {ctype}")
        n_uploaded += 1
        total_bytes += len(body)

    print(f"\nUploaded {n_uploaded} files, {total_bytes // 1024} KB total")
    print(f"Static site: http://{BUCKET}.s3-website-us-east-1.amazonaws.com")
    print(f"             http://{BUCKET}.s3-website.us-east-1.amazonaws.com  (alt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
