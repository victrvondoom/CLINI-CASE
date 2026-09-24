"""Generate a synthetic handwritten Indian oncology prescription as a PNG.

Used as the demo fixture for the Document Intake layer. Looks like a
phone-camera photograph of a real prescription — letterhead at top, hand-
written body, slight skew, paper texture, signature scribble.

Run with the project venv:
  .venv\\Scripts\\python.exe \\
    tests/fixtures/intake/_generate_handwritten_rx.py

Output: tests/fixtures/intake/handwritten_rx.png  (~600 KB, 1500x2000)

This file is checked in. To regenerate, edit the constants below and rerun.
"""
from __future__ import annotations

import io
import math
import pathlib
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = pathlib.Path(__file__).resolve().parent / "handwritten_rx.png"

# Output canvas dims — proportions of an A4 sheet at ~180 DPI
W, H = 1500, 2000

# Fonts (Windows system fonts; safe defaults across this dev box)
FONT_TYPED  = "C:/Windows/Fonts/segoeui.ttf"
FONT_HAND   = "C:/Windows/Fonts/Inkfree.ttf"        # doctor's hurried handwriting
FONT_HAND_2 = "C:/Windows/Fonts/segoepr.ttf"        # cleaner print-handwriting

# Slight randomness so two runs aren't pixel-identical (demo realism)
random.seed(42)


def _paper_texture(size: tuple[int, int]) -> Image.Image:
    """A faintly off-white paper texture — adds subtle gradients + noise."""
    base = Image.new("RGB", size, (252, 250, 245))
    noise = Image.effect_noise(size, 8).convert("RGB")
    img = Image.blend(base, noise, 0.06)
    # Cool shadow at one corner — phone-camera vignetting
    overlay = Image.new("RGB", size, (240, 240, 244))
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((-200, -200, 800, 800), fill=80)  # top-left vignette
    md.ellipse((size[0]-700, size[1]-700, size[0]+200, size[1]+200), fill=110)
    img = Image.composite(overlay, img, mask.filter(ImageFilter.GaussianBlur(80)))
    return img


def _hand(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_HAND, size)


def _hand2(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_HAND_2, size)


def _typed(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_TYPED, size)


def _hand_draw(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int = 50,
               color: tuple = (28, 32, 60), jitter: int = 2) -> int:
    """Draw text with slight per-character vertical jitter (mimics handwriting)."""
    x, y = xy
    font = _hand(size)
    for ch in text:
        dy = random.randint(-jitter, jitter)
        d.text((x, y + dy), ch, font=font, fill=color)
        bbox = font.getbbox(ch)
        x += bbox[2] - bbox[0] + random.randint(0, 2)
    return x


def main() -> int:
    img = _paper_texture((W, H))
    d = ImageDraw.Draw(img)

    # ---- Typed letterhead (printed at top of the Rx pad) ----
    d.rectangle((90, 80, W - 90, 240), fill=(22, 30, 80))
    d.text((130, 100), "ABC ONCOLOGY CENTRE",      font=_typed(38), fill=(252, 248, 230))
    d.text((130, 150), "Dr. Priya Menon, MD (Med Onc) · Reg No. KMC-48201",
                                                    font=_typed(22), fill=(208, 218, 245))
    d.text((130, 180), "Pune, Maharashtra · +91-20-2555-0140 · pmc@abconco.in",
                                                    font=_typed(20), fill=(208, 218, 245))
    d.text((130, 210), "Practice fields: Breast oncology · HER2-targeted therapy",
                                                    font=_typed(18), fill=(208, 218, 245))

    # ---- Patient header (handwritten, top-right) ----
    _hand_draw(d, (1020,  280), "Date: 06/05/26", size=36)
    _hand_draw(d, (1020,  330), "Pt name: Rajesh Sharma", size=34)
    _hand_draw(d, (1020,  380), "Age: 57  Sex: M", size=34)
    _hand_draw(d, (1020,  430), "Wt: 68 kg  Ht: 174 cm", size=34)

    # ---- Diagnosis line (handwritten, left column) ----
    d.text((130, 290), "Dx:", font=_hand(46), fill=(50, 50, 80))
    _hand_draw(d, (220, 285), "Ca Breast Lt - Stage IIIA",        size=46, jitter=3)
    _hand_draw(d, (220, 350), "HER2 + (IHC 3+, FISH amp.)",       size=42, jitter=3)
    _hand_draw(d, (220, 410), "ER 88% pos, PR 62% pos",           size=42, jitter=3)
    _hand_draw(d, (220, 470), "Post-op RT done 03/2026",          size=40, jitter=3)

    # ---- Hr divider (slightly wavy, like a hand-drawn line) ----
    pts = [(80 + i * 8, 560 + math.sin(i * 0.3) * 2) for i in range(0, (W - 160) // 8)]
    d.line(pts, fill=(50, 50, 80), width=3)

    # ---- Rx body (the prescription itself) ----
    d.text((130, 600), "Rx:", font=_hand(60), fill=(120, 25, 50))
    _hand_draw(d, (260, 600), "Inj. Herceptin 6 mg/kg IV q3w x 17 cycles",
               size=54, color=(120, 25, 50), jitter=4)
    _hand_draw(d, (200, 700), "(maintenance HER2-targeted therapy)",
               size=36, color=(120, 25, 50), jitter=2)

    _hand_draw(d, (130, 800), "Pre-medications:",          size=46, jitter=2)
    _hand_draw(d, (200, 870), "- Paracetamol 500 mg PO",   size=40, jitter=3)
    _hand_draw(d, (200, 925), "- Diphenhydramine 25 mg IV", size=40, jitter=3)

    # ---- Baseline labs (handwritten note) ----
    _hand_draw(d, (130,  1030), "Baseline cardiac:",        size=44, jitter=2)
    _hand_draw(d, (200,  1100), "LVEF 62% by 2D echo",      size=40, jitter=3)
    _hand_draw(d, (200,  1155), "Echo date: 15/04/2026",    size=40, jitter=3)
    _hand_draw(d, (200,  1210), "ECOG = 1",                 size=40, jitter=3)

    # ---- Plan / follow-up ----
    _hand_draw(d, (130, 1310), "Plan:",                    size=46, jitter=2)
    _hand_draw(d, (200, 1380), "- Cycle 1 on 12/05/2026",  size=40, jitter=3)
    _hand_draw(d, (200, 1435), "- Echo q3 months on Tx",   size=40, jitter=3)
    _hand_draw(d, (200, 1490), "- F/U OPD after C2",       size=40, jitter=3)

    # ---- Signature block (squiggly handwritten signature) ----
    sig_y = 1700
    d.text((130, sig_y - 30), "Signature:", font=_hand(36), fill=(50, 50, 80))
    sig_pts = []
    px = 320
    for i in range(60):
        sig_pts.append((px + i * 7, sig_y + 30 + math.sin(i * 0.6) * 18 + random.randint(-3, 3)))
    d.line(sig_pts, fill=(20, 20, 80), width=4)
    _hand_draw(d, (130, sig_y + 80), "Dr. Priya Menon, MD",  size=38, jitter=2)
    _hand_draw(d, (130, sig_y + 135), "Med Reg: KMC-48201",  size=30, color=(80, 80, 110), jitter=1)

    # ---- Stamp-style mark (oval 'GENUINE' overlay common on Indian Rx) ----
    d.ellipse((950, sig_y + 30, 1300, sig_y + 200), outline=(160, 30, 40), width=4)
    d.text((1000, sig_y + 75),  "ABC ONCO PUNE",  font=_typed(22), fill=(160, 30, 40))
    d.text((1010, sig_y + 110), "Dr. P. Menon",   font=_typed(20), fill=(160, 30, 40))
    d.text((1010, sig_y + 140), "Med Onc",        font=_typed(18), fill=(160, 30, 40))

    # ---- Slight rotation + downsample to simulate phone-camera ----
    img = img.rotate(0.6, fillcolor=(252, 250, 245))
    # Mild blur to simulate camera shake
    img = img.filter(ImageFilter.GaussianBlur(0.4))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Save via JPEG-then-decode trick — adds compression artefacts that make
    # the image feel like a real phone capture, then re-save as PNG so the
    # final file is one frame.
    bio = io.BytesIO()
    img.save(bio, "JPEG", quality=82)
    bio.seek(0)
    Image.open(bio).save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes, {img.size})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
