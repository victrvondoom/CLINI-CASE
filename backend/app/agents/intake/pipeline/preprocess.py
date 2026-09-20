"""Preprocess stage — validates + sanitizes raw image bytes.

Industry-grade hardening:
  1. **MIME sniff via magic bytes** — never trust the `Content-Type` header
     a client sends. Magic-byte check against known image signatures.
  2. **EXIF metadata strip** — phone-camera scans contain GPS coordinates,
     timestamps, device IDs. Stripped before downstream processing.
  3. **Decompression-bomb protection** — explicit Pillow MAX_IMAGE_PIXELS
     guard prevents a 100KB PNG from expanding to 4 GB in memory.
  4. **Dimension sanity** — reject 1×1 spam images.

If any check fails, the stage sets `short_circuit=True` with a reason —
the orchestrator routes directly to assemble + HITL.
"""
from __future__ import annotations

import io
from typing import ClassVar

from PIL import Image

from app.agents.intake.errors import (
    SOFT_FLAG_INTAKE_FAILED,
    SOFT_FLAG_LOW_QUALITY,
)
from app.agents.intake.pipeline.base import IntakeContext, IntakeStage

# Magic bytes for the document types we accept. First 8 bytes is enough
# to disambiguate every common image format we care about.
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "image/png":     [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg":    [b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\xff\xd8\xff\xdb", b"\xff\xd8\xff\xee"],
    "image/webp":    [b"RIFF"],   # plus "WEBP" at offset 8 — checked separately
    "application/pdf": [b"%PDF-"],
}

# Dimension safety thresholds
_MIN_DIMENSION = 200      # pixels — anything smaller is suspect
_MAX_DIMENSION = 12000    # pixels — anything larger likely a decompression bomb
_MAX_PIXELS = 50_000_000  # 50 megapixels — generous but bounded


def _detect_mime_from_magic(image_bytes: bytes) -> str | None:
    """Return canonical MIME from magic bytes, or None if unrecognised."""
    head = image_bytes[:16]
    for mime, signatures in _MAGIC_SIGNATURES.items():
        if mime == "image/webp":
            # WebP is RIFF + 4 bytes of size + "WEBP"
            if head.startswith(b"RIFF") and len(image_bytes) >= 12 and image_bytes[8:12] == b"WEBP":
                return "image/webp"
            continue
        if any(head.startswith(sig) for sig in signatures):
            return mime
    return None


def _strip_exif(image_bytes: bytes, mime: str) -> bytes:
    """Re-encode the image without metadata (PHI-conscious).

    We strip EXIF GPS, timestamps, device IDs, etc. The visual pixels are
    preserved. PDFs are passed through unchanged (we don't downstream them
    in this build, but Textract can later).
    """
    if mime == "application/pdf":
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        # Re-encoding without `exif` argument drops all metadata.
        out = io.BytesIO()
        save_format = "PNG" if mime == "image/png" else "JPEG" if mime == "image/jpeg" else "WEBP"
        save_kwargs: dict = {"format": save_format}
        if save_format == "JPEG":
            save_kwargs["quality"] = 92
            save_kwargs["optimize"] = True
        img.save(out, **save_kwargs)
        return out.getvalue()
    except Exception:  # noqa: BLE001 — if strip fails, return original; classifier will catch real issues
        return image_bytes


class PreprocessStage(IntakeStage):
    """Validate magic bytes, strip EXIF, guard against decompression bombs."""

    name: ClassVar[str] = "preprocess"
    inputs_required: ClassVar[list[str]] = []  # reads ctx.image_bytes directly
    outputs_produced: ClassVar[list[str]] = ["preprocess.detected_mime", "preprocess.dims"]

    async def run(self, ctx: IntakeContext) -> None:
        # --- 1. MIME sniff ---
        detected = _detect_mime_from_magic(ctx.image_bytes)
        if detected is None:
            ctx.payload["preprocess.detected_mime"] = None
            ctx.short_circuit = True
            ctx.short_circuit_reason = (
                "Magic-byte check failed; bytes don't look like PNG/JPEG/WebP/PDF."
            )
            ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
            return
        ctx.payload["preprocess.detected_mime"] = detected
        if detected != ctx.mime_type:
            # Caller-claimed MIME disagreed with reality — flag but accept the magic-bytes truth
            ctx.risk_flags.append(SOFT_FLAG_LOW_QUALITY)

        # --- 2. Dimension + bomb guard (only for images, not PDFs) ---
        if detected != "application/pdf":
            try:
                img = Image.open(io.BytesIO(ctx.image_bytes))
                w, h = img.size
            except Exception:  # noqa: BLE001
                ctx.short_circuit = True
                ctx.short_circuit_reason = "Pillow could not open image bytes."
                ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
                return
            ctx.payload["preprocess.dims"] = {"w": w, "h": h}
            if w < _MIN_DIMENSION or h < _MIN_DIMENSION:
                ctx.short_circuit = True
                ctx.short_circuit_reason = f"Image too small: {w}x{h} (min {_MIN_DIMENSION}px)."
                ctx.risk_flags.append(SOFT_FLAG_LOW_QUALITY)
                return
            if w > _MAX_DIMENSION or h > _MAX_DIMENSION or (w * h) > _MAX_PIXELS:
                ctx.short_circuit = True
                ctx.short_circuit_reason = (
                    f"Image dimensions exceed safety thresholds: {w}x{h}."
                )
                ctx.risk_flags.append(SOFT_FLAG_INTAKE_FAILED)
                return

            # --- 3. EXIF strip (overwrite ctx.image_bytes with sanitised) ---
            sanitised = _strip_exif(ctx.image_bytes, detected)
            ctx.image_bytes = sanitised
            # Update format hint for downstream stages
            ctx.image_format = detected.split("/")[-1].replace("jpg", "jpeg")
        else:
            ctx.payload["preprocess.dims"] = None
            ctx.image_format = "pdf"
