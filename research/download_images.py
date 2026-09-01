#!/usr/bin/env python3
"""
Download every image/video referenced in content/site.json from
designoutlaw.com's own asset CDN (Figma Sites serves them at
/_assets/v11/<hash>.<ext>, unauthenticated) into public/images/, and write
a manifest mapping ref hash -> {ext, width, height} so build.py can turn a
bare hash into a real path without re-guessing the extension.

Run after research/build_content.py, whenever content/site.json changes.
"""

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
OUT = ROOT / "public" / "images"
BASE = "https://www.designoutlaw.com/_assets/v11"

# Known up front: the home page's hero photo, favicon, and social card
# aren't reachable from content/site.json (they're chrome, not content) so
# they're listed explicitly, by hash, alongside their intended filename.
EXTRA = {
    "8ef2313d21392339ee72d1c88322a363a4d38a04": ("hero-photo", "image"),
    "2c11be535154e2888ea69e34a9f039c562568f0d": ("favicon", "image"),
    "b80fb14f673a87c88b326e80ed5e8ab3ebcfa4f6": ("social-card", "image"),
}

IMAGE_EXTS = ["png", "jpg", "webp"]
VIDEO_EXTS = ["mp4", "webm"]


def try_download(ref, kind, dest_stem):
    exts = VIDEO_EXTS if kind == "video" else IMAGE_EXTS
    for ext in exts:
        url = f"{BASE}/{ref}.{ext}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status != 200:
                    continue
                data = r.read()
        except Exception:
            continue
        dest = OUT / f"{dest_stem}.{ext}"
        dest.write_bytes(data)
        return ext, len(data)
    return None, 0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}

    def add(ref, kind, stem):
        if ref in manifest:
            return
        ext, size = try_download(ref, kind, stem)
        if ext:
            manifest[ref] = {"ext": ext, "file": f"{stem}.{ext}"}
            print(f"  {stem}.{ext}  ({size:,} bytes)")
        else:
            print(f"  FAILED: {ref} ({kind})")

    for ref, (stem, kind) in EXTRA.items():
        add(ref, kind, stem)

    for item in SITE["home"]["work"]["items"]:
        add(item["image_ref"], "image", f"work-{item['slug']}")

    for p in SITE["projects"]:
        for i, m in enumerate(p["gallery"], 1):
            stem = f"{p['slug']}-{i}"
            add(m["ref"], m["type"], stem)
            if m.get("poster_ref"):
                add(m["poster_ref"], "image", f"{stem}-poster")

    dest = OUT / "manifest.json"
    dest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {dest} ({len(manifest)} assets)")


if __name__ == "__main__":
    main()
