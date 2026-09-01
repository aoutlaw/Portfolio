#!/usr/bin/env python3
"""
Re-encode public/images/*.png as capped-dimension WebP and rewrite
manifest.json to point at the new files.

The raw downloads are phone-camera and full-res design-export originals
(up to 4096px on a side, 12MB for a single portrait) -- fine as Figma
upload sources, wildly oversized for web delivery. This is a one-off pass,
run by hand after research/download_images.py pulls in new assets, not
part of the CI build (it needs Pillow; build.py deliberately doesn't).

Run:  pip install Pillow && python3 research/optimize_images.py
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "images"
MANIFEST_PATH = OUT / "manifest.json"

# Longest edge, by role. Hero/gallery images are viewed close to full width
# on desktop; work-card thumbnails only ever fill a grid cell.
MAX_DIM = {
    "hero-photo": 1400,
    "work-": 1000,
    "social-card": 1200,  # already the recommended og:image size -- leave as-is
}
DEFAULT_MAX_DIM = 1600
QUALITY = 82

# Small and already the right format for a <link rel="icon">; skip.
SKIP = {"favicon.png"}


def max_dim_for(stem):
    for prefix, dim in MAX_DIM.items():
        if stem.startswith(prefix):
            return dim
    return DEFAULT_MAX_DIM


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    total_before = total_after = 0

    for ref, entry in manifest.items():
        filename = entry["file"]
        if filename in SKIP or not filename.endswith(".png"):
            continue

        src = OUT / filename
        before = src.stat().st_size
        total_before += before

        stem = filename[: -len(".png")]
        im = Image.open(src)
        cap = max_dim_for(stem)
        if max(im.size) > cap:
            ratio = cap / max(im.size)
            im = im.resize(
                (round(im.width * ratio), round(im.height * ratio)), Image.LANCZOS
            )

        dest = OUT / f"{stem}.webp"
        im.save(dest, "WEBP", quality=QUALITY, method=6)
        src.unlink()

        after = dest.stat().st_size
        total_after += after
        entry["ext"] = "webp"
        entry["file"] = f"{stem}.webp"
        print(f"  {filename} ({before:,}B) -> {stem}.webp ({after:,}B)")

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"\n{total_before:,}B -> {total_after:,}B "
        f"({100 * (1 - total_after / total_before):.0f}% smaller)"
    )


if __name__ == "__main__":
    main()
