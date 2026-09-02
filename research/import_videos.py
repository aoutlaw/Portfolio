#!/usr/bin/env python3
"""
Import the three Spaceabet process-video clips Angelo supplied directly
(the live site's uploaded Figma video assets aren't reachable from the
static /_assets/v11/ CDN the way images are -- see the "Known gap" note in
README.md and research/download_images.py).

Copies each clip into public/images/, extracts its first frame as a poster
WebP (matching optimize_images.py's conventions), and adds both to
manifest.json under the same ref hashes content/site.json already
references -- so build.py needs no changes, it just finds the assets.

One-off / not re-runnable from a URL: re-run by hand only if the source
files change, with SOURCES below updated to the new upload paths.

Run:  python3 research/import_videos.py
"""

import json
import shutil
from pathlib import Path

import av
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "images"
MANIFEST_PATH = OUT / "manifest.json"
UPLOAD_DIR = Path(
    "/root/.claude/uploads/af236799-1381-5121-acd2-254dc67dd870"
)

# (source file, dest stem, video ref, poster ref) -- refs are the hashes
# research/build_content.py already put in content/site.json's spaceabet
# gallery (positions 0-2), matched to the uploaded filename Figma recorded
# for each (IMG_0780 / IMG_9394 / IMG_0735).
SOURCES = [
    (
        "60b91869-IMG_0780.mp4",
        "spaceabet-video-1",
        "5634e1b050c155d05eb5520e761b9dad080f8cd6",
        "2140fceec68560db4b0d64babfde6a925a2f83b2",
    ),
    (
        "1e063c68-IMG_9394.mp4",
        "spaceabet-video-2",
        "b6a14ea1d01aac778c78d2ebb4942ea7f34411fc",
        "be3c283ebbfc2af59ce64435d16b49c7c45d8d35",
    ),
    (
        "16b658ac-IMG_0735.mp4",
        "spaceabet-video-3",
        "12b6847d1c6ec05a03d51a50ee8c4f02dd06656a",
        "e5adcb6f2dc2ff88bee55afa3720e87d059025a3",
    ),
]

POSTER_MAX_DIM = 900


def extract_poster(video_path, dest):
    container = av.open(str(video_path))
    frame = next(container.decode(video=0))
    im = frame.to_image()
    if max(im.size) > POSTER_MAX_DIM:
        ratio = POSTER_MAX_DIM / max(im.size)
        im = im.resize(
            (round(im.width * ratio), round(im.height * ratio)), Image.LANCZOS
        )
    im.save(dest, "WEBP", quality=82, method=6)
    container.close()


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for src_name, stem, video_ref, poster_ref in SOURCES:
        src = UPLOAD_DIR / src_name
        video_dest = OUT / f"{stem}.mp4"
        shutil.copyfile(src, video_dest)
        manifest[video_ref] = {"ext": "mp4", "file": video_dest.name}
        print(f"  {src_name} -> {video_dest.name} ({video_dest.stat().st_size:,}B)")

        poster_dest = OUT / f"{stem}-poster.webp"
        extract_poster(src, poster_dest)
        manifest[poster_ref] = {"ext": "webp", "file": poster_dest.name}
        print(f"    poster -> {poster_dest.name} ({poster_dest.stat().st_size:,}B)")

    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
