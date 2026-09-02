#!/usr/bin/env python3
"""
Import process-video clips Angelo supplied directly (the live site's
uploaded Figma video assets aren't reachable from the static
/_assets/v11/ CDN the way images are -- see the "Known gap" note in
README.md and research/download_images.py).

For an .mp4 source, copies it as-is. For a .mov source (H.264 in a
QuickTime container -- browsers play the codec fine but support for the
.mov container itself over <video> is inconsistent), remuxes into an .mp4
container: same encoded video stream, copied packet-for-packet with no
re-encode, just repackaged so every browser treats it as a normal
<video src>. Either way also extracts the first frame as a poster WebP
(matching optimize_images.py's conventions), and adds both to
manifest.json under the ref hashes content/site.json already references
-- so build.py needs no changes, it just finds the assets.

One-off / not re-runnable from a URL: re-run by hand only if the source
files change, with SOURCES below updated to the new upload paths.

Run:  python3 research/import_videos.py
"""

import json
import shutil
from fractions import Fraction
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
# research/build_content.py already put in content/site.json, matched to
# the uploaded filename Figma recorded for each clip.
SOURCES = [
    # Spaceabet gallery, positions 0-2 (IMG_0780 / IMG_9394 / IMG_0735).
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
    # Y Conference gallery, position 0.
    (
        "d32d07ec-Y21_Video_480p_2.mov",
        "y-conference-video",
        "c01bc3f9d7e31269b7edc5bae7fded2f7e2ac9fa",
        "6a97653961e92b004a80e09f88bfaf7582666534",
    ),
    # Generali Travel Insurance gallery, position 0 (its only item).
    (
        "74d81efc-GTI480_1.mov",
        "generalitravelinsurance-video",
        "83e595ec6a7b7b79e5a50ca93c7e88365134bb62",
        "f8954bd82b5ef92b74b4268c7e2c16c418d24b4b",
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


def remux_to_mp4(src, dest):
    """Re-encode src's video stream into an .mp4 at dest.

    A packet-copy remux (no re-encode) is the usual fast path, but these
    .mov sources carry negative DTS from B-frame reordering (QuickTime
    resolves that with an edit list; plain MP4 muxing does not support
    that and rejects the packets outright with EINVAL). Re-encoding
    sidesteps it -- these are short 14-19s clips at a modest source
    resolution (640px wide) for a muted, small gallery loop, so a clean
    CRF pass is not a meaningful quality loss.

    Rounds the source's frame rate (sometimes non-integer -- one of these
    two clips reports 4998/115) to a plain integer and assigns each frame
    a fresh sequential pts in that rate's time_base *after* reformatting
    it, not before: setting pts/time_base ahead of frame.reformat() left
    it echoing the source's original (and here, non-monotonic) timing and
    hit the same EINVAL. Keeping the rounded real fps (rather than a fixed
    24/30) preserves the original's actual playback duration."""
    input_ = av.open(str(src))
    in_stream = input_.streams.video[0]
    fps = round(in_stream.average_rate)
    time_base = Fraction(1, fps)

    output = av.open(str(dest), mode="w")
    out_stream = output.add_stream("libx264", rate=fps)
    out_stream.width = in_stream.codec_context.width
    out_stream.height = in_stream.codec_context.height
    out_stream.pix_fmt = "yuv420p"
    out_stream.options = {"crf": "23", "preset": "medium", "movflags": "faststart"}

    for n, frame in enumerate(input_.decode(in_stream)):
        frame = frame.reformat(format="yuv420p")
        frame.pts = n
        frame.time_base = time_base
        for packet in out_stream.encode(frame):
            output.mux(packet)
    for packet in out_stream.encode():
        output.mux(packet)

    output.close()
    input_.close()


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for src_name, stem, video_ref, poster_ref in SOURCES:
        src = UPLOAD_DIR / src_name
        video_dest = OUT / f"{stem}.mp4"
        if src.suffix.lower() == ".mp4":
            shutil.copyfile(src, video_dest)
        else:
            remux_to_mp4(src, video_dest)
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
