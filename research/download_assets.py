#!/usr/bin/env python3
"""
Download every asset content/site.json references from designoutlaw.com's
own CDN into public/images/, re-encode the rasters as capped WebP, and
write a manifest mapping the live /_assets/v11/<hash>.<ext> path to the
local file.

Supersedes download_images.py + optimize_images.py: those keyed off Figma
scene-graph ref hashes, this keys off the live asset URLs the extractor
records, so the two stay in step automatically.

Run after research/extract_live.py. Needs Pillow.
"""

import json
import re
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
OUT = ROOT / "public" / "images"
BASE = "https://www.designoutlaw.com"

# Page chrome that isn't reachable from content/site.json.
CHROME = {
    "/_assets/v11/8ef2313d21392339ee72d1c88322a363a4d38a04.png": "hero-photo",
    "/_assets/v11/2c11be535154e2888ea69e34a9f039c562568f0d.png": "favicon",
    "/_assets/v11/b80fb14f673a87c88b326e80ed5e8ab3ebcfa4f6.png": "social-card",
    # Firefighter Pfister's work-card wordmark, drawn over the photo.
    "/_assets/v11/adf4b875ecf5ed87b05f9196440ea6def7b9910d.svg": "ffp-wordmark",
}

# Longest edge by role; SVGs and the favicon pass through untouched.
MAX_DIM = {"hero-photo": 1400, "work-": 1200, "social-card": 1200}
DEFAULT_MAX_DIM = 1600
QUALITY = 82


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def cap_for(stem):
    for prefix, dim in MAX_DIM.items():
        if stem.startswith(prefix):
            return dim
    return DEFAULT_MAX_DIM


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = dict(CHROME)

    for i, item in enumerate(SITE["home"]["work"], 1):
        wanted[item["src"]] = f"work-{item['slug'] or f'card{i}'}"
    for p in SITE["projects"]:
        n = 0
        for row in p["gallery"]:
            for it in row["items"]:
                if it["type"] == "image":
                    n += 1
                    wanted[it["src"]] = f"{p['slug']}-{n}"

    manifest = {}
    for path, stem in wanted.items():
        ext = path.rsplit(".", 1)[-1].lower()
        try:
            data = fetch(path)
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"  FAILED {path}: {e}")
            continue

        if ext == "svg" or stem == "favicon":
            dest = OUT / f"{stem}.{ext}"
            dest.write_bytes(data)
        else:
            tmp = OUT / f".{stem}.orig"
            tmp.write_bytes(data)
            im = Image.open(tmp)
            cap = cap_for(stem)
            if max(im.size) > cap:
                r = cap / max(im.size)
                im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
            dest = OUT / f"{stem}.webp"
            im.save(dest, "WEBP", quality=QUALITY, method=6)
            tmp.unlink()

        manifest[path] = dest.name
        print(f"  {path.split('/')[-1][:14]}… -> {dest.name} ({dest.stat().st_size:,}B)")

    # Videos were supplied by hand (Figma's video CDN isn't publicly
    # reachable); research/import_videos.py puts them here and they are
    # matched positionally to the gallery's video slots.
    for f in sorted(OUT.glob("*.mp4")):
        manifest.setdefault(f"video:{f.stem}", f.name)

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nwrote manifest ({len(manifest)} entries)")


if __name__ == "__main__":
    main()
