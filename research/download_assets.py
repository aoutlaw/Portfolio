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

# Every image on the site is laid out width-first: gallery boxes and work
# cards both fill their column and let the height fall out of the aspect
# ratio, and several sources are tall screenshots. Capping the *longest*
# edge therefore crushed those to a couple of hundred pixels wide, so the
# cap is on width, with a total-pixel ceiling to keep the tallest ones from
# turning into multi-megabyte files.
MAX_WIDTH = 1600
MAX_PIXELS = 6_000_000
QUALITY = 82


def downscale(im):
    """Fit the image under both ceilings, preserving its proportions."""
    ratio = min(1.0, MAX_WIDTH / im.width, (MAX_PIXELS / (im.width * im.height)) ** 0.5)
    if ratio >= 1.0:
        return im
    return im.resize((round(im.width * ratio), round(im.height * ratio)), Image.LANCZOS)


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


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
            im = downscale(Image.open(tmp))
            dest = OUT / f"{stem}.webp"
            im.save(dest, "WEBP", quality=QUALITY, method=6)
            tmp.unlink()

        manifest[path] = dest.name
        size = Image.open(dest).size if dest.suffix == ".webp" else ""
        print(f"  {path.split('/')[-1][:14]}… -> {dest.name} {size} ({dest.stat().st_size:,}B)")

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
