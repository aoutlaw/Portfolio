#!/usr/bin/env python3
"""
Extract the live designoutlaw.com pages into content/site.json.

Supersedes the earlier scene-graph-only approach (research/build_content.py).
The Figma Sites JSON gives verbatim copy but not the rendered layout; the
live HTML gives both, because Figma Sites server-renders every breakpoint
and ships the resolved styles in a `#container .css-xxx {...}` block. This
reads the *rendered* pages, so what lands in content/site.json is what the
live site actually shows -- including gallery row grouping, image alt text,
row heights and aspect ratios, which the scene graph does not express.

Pages are read from research/raw_html/*.html. Refresh those with:

    for s in "" spaceabet y-conference firefighter-pfister travelcover \\
             generalitravelinsurance; do
      curl -sL "https://www.designoutlaw.com/$s" -o "research/raw_html/${s:-home}.html"
    done
"""

import html as htmllib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "raw_html"

# Desktop breakpoint (>=1000px) per page -- the widest server-rendered copy.
PROJECTS = [
    ("spaceabet", "Spaceabet"),
    ("y-conference", "Y Conference"),
    ("firefighter-pfister", "Firefighter Pfister"),
    ("travelcover", "Travel Cover"),
    ("generalitravelinsurance", "Generali Travel Insurance"),
]


def load(slug):
    return (RAW / f"{slug}.html").read_text(encoding="utf-8")


def ssr_rules(doc):
    m = re.search(r'<style[^>]*id="ssr-css"[^>]*>(.*?)</style>', doc, re.S)
    rules = {}
    if not m:
        return rules
    for x in re.finditer(r"#container\s+\.([a-zA-Z0-9_-]+)\s*\{([^}]*)\}", m.group(1)):
        rules[x.group(1)] = rules.get(x.group(1), "") + x.group(2).strip() + ";"
    return rules


def widest_breakpoint(doc):
    """The >=1000px copy: Figma Sites renders one subtree per breakpoint."""
    best, best_w = None, -1
    for m in re.finditer(r'data-breakpoint-id="([^"]+)"[^>]*data-width="([0-9.]+)"', doc):
        w = float(m.group(2))
        if w > best_w:
            best, best_w = m.group(1), w
    return best


def body_lines(doc):
    doc = re.sub(r"<script.*?</script>", "", doc, flags=re.S)
    b, e = doc.find("<body"), doc.rfind("</body>")
    return re.sub(r">\s*<", ">\n<", doc[b:e]).split("\n")


def props(line, rules):
    out = {}
    for c in re.findall(r'class="([^"]*)"', line):
        for cls in c.split():
            for d in rules.get(cls, "").split(";"):
                if ":" in d:
                    k, v = d.split(":", 1)
                    out[k.strip()] = v.strip()
    return out


def text_of(line):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", line)).strip()


def breakpoints(doc):
    """(id, width) for each server-rendered copy, narrowest first."""
    found = [
        (m.group(1), float(m.group(2)))
        for m in re.finditer(r'data-breakpoint-id="([^"]+)"[^>]*data-width="([0-9.]+)"', doc)
    ]
    return sorted(found, key=lambda x: x[1])


def scoped(doc):
    """Lines of the widest breakpoint's subtree, plus the page's resolved
    rules. Copy is identical across the server-rendered copies, and the
    layout that isn't comes from the measured geometry instead."""
    rules = ssr_rules(doc)
    lines = body_lines(doc)
    start = next(i for i, l in enumerate(lines) if breakpoints(doc)[-1][0] in l)
    ends = [i for i, l in enumerate(lines) if "data-breakpoint-id" in l and i > start]
    return lines[start : (ends[0] if ends else len(lines))], rules


GEOMETRY = ROOT / "research" / "raw_geometry"
BREAKPOINTS = ("mobile", "tablet", "desktop")
# Each breakpoint's second, wider sample. Comparing the two tells a value
# Figma pinned in pixels from one that tracks the viewport.
WIDER = {bp: bp + "Wide" for bp in BREAKPOINTS}
DEFAULT_GAP = {"mobile": "16px", "tablet": "24px", "desktop": "32px"}


def box_fit(item, wide):
    """How the aspect box is sized inside its cell.

    "cover" is the common case: the box spans the cell's width, overflows
    its fixed height and gets cropped by it. A few cells size the box to
    their *height* instead ("contain"), so it sits inside them with room
    either side; one carries no ratio at all and just takes the cell's box
    ("fill"). And one holds a fixed pixel width, which only shows up in the
    wider sample -- at its own breakpoint's narrow edge it looks exactly
    like a box that fills its cell.

    All of it is read back from the measured boxes rather than guessed."""
    if item["aspect"] == "auto":
        return "fill"
    (cw, ch), (bw, bh) = item["cellBox"], item["shotBox"]
    if abs(wide["shotBox"][0] - bw) < 1.5 and wide["cellBox"][0] - bw > 1.5:
        return f"{bw:.0f}px"
    if abs(bw - cw) < 1.5:
        return "cover"
    return "contain" if abs(bh - ch) < 1.5 else "cover"


def media_crop(twins):
    """The image's placement inside its box, as percentages.

    Figma bakes a fill's crop into the <img>: it is sized and offset
    relative to its box rather than filling it, and the cell clips what
    hangs out. The percentages are the same at every breakpoint, so one set
    is emitted; None means the image simply fills its box."""
    crops = set()
    for t in twins.values():
        bw, bh = t["shotBox"]
        mw, mh = t["mediaBox"]
        mx, my = t["mediaAt"]
        if not bw or not bh:
            continue
        crops.add(tuple(round(v, 2) for v in
                        (mw / bw * 100, mh / bh * 100, mx / bw * 100, my / bh * 100)))
    if not crops:
        return None
    if len(crops) > 1:
        print(f"  !! crop differs across breakpoints: {crops}")
    crop = max(crops)
    return None if crop == (100.0, 100.0, 0.0, 0.0) else list(crop)


def cell_ratio(item):
    """The box's own ratio where it has one, else the ratio its cell is
    holding -- a couple of boxes carry no ratio and take the cell's."""
    if item["aspect"] != "auto":
        return item["aspect"]
    w, h = item["cellBox"]
    return f"{w:.4g} / {h:.4g}"


def cell_height(item, wide):
    """The cell's height: a pixel value it holds whatever the viewport
    does, or `auto` where it just follows the shot inside it."""
    if abs(wide["cellBox"][1] - item["cellBox"][1]) > 1.5:
        return "auto"
    return item["height"]


def project_gallery(slug):
    """Gallery rows for one project, read from the harvested geometry.

    The live markup nests row > cell > aspect-box > img. The row is a flex
    line capped at the 1280px content width; the cell has a *fixed* pixel
    height and `overflow: clip` and centres its contents; the aspect box
    inside is width-driven, so a tall image overflows its cell and is
    centre-cropped by it. Every one of those values -- the row's direction
    and gap, the cell's height, the box's ratio -- is set per breakpoint
    with no derivable rule, so all three are carried per item.

    The values come from research/raw_geometry/*.json rather than from the
    `ssr-css` block, because Figma reuses class names across breakpoints
    and the resolved cascade is what actually matters. Refresh them with
    research/harvest_geometry.js.

    Videos have no <img>: Figma uploads them as VIDEO fills that its client
    runtime mounts after hydration, so they are typed placeholders here and
    matched to the real files by build.py.
    """
    path = GEOMETRY / f"{slug}.json"
    if not path.exists():
        raise SystemExit(f"missing geometry for {slug}; run research/harvest_geometry.js")
    doc = json.loads(path.read_text(encoding="utf-8"))
    head = {bp: doc[bp]["head"] for bp in BREAKPOINTS}
    blocks = {bp: doc[bp]["blocks"] for bp in BREAKPOINTS}
    per_bp = {bp: v["rows"] for bp, v in doc.items()}
    local_to_live = {v: k for k, v in
                     json.loads((ROOT / "public" / "images" / "manifest.json")
                                .read_text(encoding="utf-8")).items()}

    counts = {bp: sum(len(r["items"]) for r in rows) for bp, rows in per_bp.items()}
    if len(set(counts.values())) != 1:
        raise SystemExit(f"{slug}: gallery item counts differ across breakpoints: {counts}")

    rows = []
    for i, row in enumerate(per_bp["desktop"]):
        out_items = []
        for j, item in enumerate(row["items"]):
            twins = {bp: per_bp[bp][i]["items"][j] for bp in BREAKPOINTS}
            wider = {bp: per_bp[WIDER[bp]][i]["items"][j] for bp in BREAKPOINTS}
            entry = {
                "type": item["type"],
                "aspect": {bp: cell_ratio(t) for bp, t in twins.items()},
                "crop": media_crop(twins),
                "cell": {bp: cell_height(t, wider[bp]) for bp, t in twins.items()},
                "fit": {bp: box_fit(t, wider[bp]) for bp, t in twins.items()},
                # How the cell places the box: which axis it lays out on,
                # and where the overflow hangs.
                "place": {bp: [t["cellDirection"], t["cellAlign"], t["cellJustify"]]
                          for bp, t in twins.items()},
            }
            if item["type"] == "image":
                local = item["src"].rsplit("/", 1)[-1]
                entry["src"] = local_to_live.get(local, item["src"])
                entry["alt"] = item["alt"] or ""
            out_items.append(entry)
        rows.append({
            "label": per_bp["desktop"][i]["label"],
            "direction": {bp: per_bp[bp][i]["direction"] for bp in BREAKPOINTS},
            "align": {bp: per_bp[bp][i]["align"] for bp in BREAKPOINTS},
            "gap": {bp: (per_bp[bp][i]["gap"] if per_bp[bp][i]["gap"].endswith("px")
                         else DEFAULT_GAP[bp]) for bp in BREAKPOINTS},
            "items": out_items,
        })
    return {"head": head, "blocks": blocks, "rows": rows}


def paragraphs_after(lines, start):
    """The <p> children of the rich-text block opening at `start`."""
    out, depth = [], 0
    for l in lines[start:]:
        if l.startswith("<div"):
            depth += 1
        elif l.startswith("</div"):
            depth -= 1
            if depth <= 0:
                break
        t = text_of(l)
        if t and l.startswith("<p"):
            out.append(t)
    return out


def build_project(slug, title):
    doc = load(slug)
    lines, rules = scoped(doc)

    gallery = project_gallery(slug)
    labels = {r["label"] for r in gallery["rows"] if r["label"]}

    heading = None
    intro = []
    sections, cta = [], None
    pending_h2 = None

    for i, l in enumerate(lines):
        t = text_of(l)
        p = props(l, rules)
        fs, fam = p.get("font-size"), p.get("font-family", "")
        # The intro can be a single paragraph or a rich-text block of
        # several. In the latter the type is declared on the wrapper, which
        # carries no text of its own, so this runs before the text filter.
        if fs == "24px" and "Poppins" in fam and not intro and heading:
            intro = [t] if t else paragraphs_after(lines, i)
            continue
        if not t:
            continue
        if fs == "96px" and heading is None:
            heading = t
        elif fs == "36px" and "SemiBold" in fam:
            pending_h2 = t
        elif fs == "20px" and "Regular" in fam and pending_h2:
            if pending_h2 not in labels:
                sections.append({"heading": pending_h2, "body": t})
            pending_h2 = None

    # The CTA is the one external link on the page; its label is the
    # uppercase SemiBold text a few nodes below the anchor.
    for i, l in enumerate(lines):
        m = re.search(r'<a[^>]*href="(https?://[^"]+)"', l)
        if not m:
            continue
        for j in range(i, min(len(lines), i + 12)):
            t = text_of(lines[j])
            if not t:
                continue
            p = dict(props(lines[j], rules))
            for k in range(j - 1, max(0, j - 4), -1):
                up = props(lines[k], rules)
                if "font-family" in up:
                    p.setdefault("font-family", up["font-family"])
                    break
            if "SemiBold" in p.get("font-family", ""):
                cta = {"label": t, "href": m.group(1)}
                break
        if cta:
            break

    return {
        "slug": slug,
        "title": title,
        "heading": heading or title,
        "intro": intro,
        "sections": sections,
        "cta": cta,
        # TravelCover interleaves its Before/Wireframes/After imagery between
        # the text sections rather than gathering it all at the end, so the
        # gallery scan can't start after the last section -- it takes the
        # whole subtree, with SVG chrome icons filtered out inside.
        "head": gallery["head"],
        "blocks": gallery["blocks"],
        "gallery": gallery["rows"],
    }


def card_geometry():
    """Each work card's box ratio per breakpoint and its image's crop.

    The card is a box at a fixed ratio; the image either covers it or --
    where Figma cropped a tall source -- is scaled past it and nudged up.
    The ratio changes between breakpoints (Y Conference's card is squarer
    on a phone than it is anywhere else), so it is measured rather than
    taken from the one server-rendered copy.
    """
    path = GEOMETRY / "home.json"
    if not path.exists():
        raise SystemExit("missing home geometry; run research/harvest_geometry.js")
    per_bp = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for bp in BREAKPOINTS:
        for card in per_bp[bp]["cards"]:
            local = card["src"].rsplit("/", 1)[-1]
            entry = out.setdefault(local, {"box": {}, "crop": {}})
            cw, ch = card["card"]
            mw, mh = card["media"]
            _, my = card["at"]
            entry["box"][bp] = f"{cw:.6g} / {ch:.6g}"
            if abs(mh - ch) > 1.5 or abs(my) > 1.5:
                entry["crop"][bp] = {"height": f"{mh / ch * 100:.4g}%",
                                     "top": f"{my / ch * 100:.4g}%"}
    return out


def work_cards(lines, rules, by_image):
    """Work cards in DOM order: destination, image, alt, box ratio and crop."""
    cards, seen = [], set()
    geometry = card_geometry()
    local_names = json.loads((ROOT / "public" / "images" / "manifest.json")
                             .read_text(encoding="utf-8"))
    for i, l in enumerate(lines):
        m = re.search(r'<a[^>]*href="(/[a-z-]+)"', l)
        if not (m or 'role="link"' in l or "aspect-ratio" in props(l, rules)):
            continue
        for j in range(i, min(len(lines), i + 14)):
            if re.match(r"<img[^>]*>", lines[j]) and "/_assets/" in lines[j]:
                src = re.search(r'src="([^"]*)"', lines[j]).group(1)
                if src.endswith(".svg") or src in seen:
                    break
                seen.add(src)
                digest = src.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                alt = re.search(r'alt="([^"]*)"', lines[j])

                geom = geometry.get(local_names.get(src, ""), {})
                if not geom:
                    print(f"  !! no measured geometry for {src}")
                cards.append(
                    {
                        "slug": by_image.get(digest, m.group(1).lstrip("/") if m else None),
                        "src": src,
                        "alt": htmllib.unescape(alt.group(1)) if alt else "",
                        "box": geom.get("box", {}),
                        "crop": geom.get("crop"),
                    }
                )
                break
    return cards


def build_home():
    doc = load("home")
    lines, rules = scoped(doc)

    # Figma Sites puts the font on a wrapper div and the text inside a <p>,
    # so a text line's own classes carry only line-height -- the family and
    # size live a couple of lines up. Merge the nearest ancestor's props in.
    texts = []
    for i, l in enumerate(lines):
        t = text_of(l)
        if not t:
            continue
        p = dict(props(l, rules))
        for j in range(i - 1, max(0, i - 4), -1):
            up = props(lines[j], rules)
            if "font-family" in up:
                for k, v in up.items():
                    p.setdefault(k, v)
                break
        texts.append((t, p))

    def first(pred):
        for t, p in texts:
            if pred(t, p):
                return t
        return None

    tagline = first(lambda t, p: p.get("font-size") == "40px")
    about_para = first(lambda t, p: t.startswith("I'm a digital designer"))
    about_highlight = first(lambda t, p: p.get("color") == "#efbb23")
    contact_para = first(lambda t, p: t.startswith("I’d love to hear"))
    footer = first(lambda t, p: t.startswith("© Angelo Outlaw"))

    # Job rows: company (Bold) / title (Regular) / dates (Regular, nowrap).
    jobs, buf = [], []
    for t, p in texts:
        fam = p.get("font-family", "")
        if "Poppins:Bold" in fam:
            buf = [t]
        elif buf and "Poppins:Regular" in fam and len(buf) < 3:
            buf.append(t)
            if len(buf) == 3:
                jobs.append({"company": buf[0], "title": buf[1], "dates": buf[2]})
                buf = []

    # Work cards. Only the first two and the row-2 wrapper are real <a>
    # elements; the cards nested inside that wrapper are role="link" divs
    # whose targets Figma's runtime attaches on click, so the destination
    # isn't in the HTML. The scene graph records them (each card FRAME has
    # its own ON_CLICK NAVIGATE action), so they're mapped by image hash.
    BY_IMAGE = {
        "64c6d4154d6ebfdc38f4d5dc9d5d742a1b59f606": "spaceabet",
        "7d76be65f157d202d38c18e7715b40b52bce1121": "generalitravelinsurance",
        "774c80de08300b712dadadcbad63c5669e0db2b8": "travelcover",
    }

    work = work_cards(lines, rules, BY_IMAGE)

    # The rendered HTML only carries the rows that are visible before "See
    # More"; the scene graph has all ten, plus each row's description.
    visible = len(jobs)
    full = scene_graph_jobs()
    if full:
        for i, j in enumerate(full[:visible]):
            if j["company"] != jobs[i]["company"]:
                print(f"  !! row {i} differs: {j['company']!r} vs {jobs[i]['company']!r}")
        jobs = full

    return {
        "name": "Angelo Outlaw",
        "tagline": tagline,
        "about": {"paragraph": about_para, "highlight": about_highlight},
        "jobs": jobs,
        "jobs_visible": visible,
        "work": work,
        "contact": {"paragraph": contact_para},
        "footer": footer,
    }


def scene_graph_jobs():
    """All ten Experience rows, with descriptions, from the Figma scene
    graph (research/raw/home.json). Each Job Row instance stores its copy
    as override deltas against the component's defaults; a row with no
    overrides at all *is* the component default (Point Loma)."""
    path = ROOT / "research" / "raw" / "home.json"
    if not path.exists():
        return []
    nodes = json.loads(path.read_text(encoding="utf-8"))["nodeById"]

    D_CO = "Point Loma Nazarene University"
    D_TI = "Adjunct Professor - Art Department"
    D_DA = "May 2023 - May 2026"
    D_DE = (
        "I crafted and taught a curriculum built to be accessible to "
        "students with no digital design experience. This curriculum used a "
        "human-centered approach that referenced real-world scenarios "
        "intended build comfort levels among students. By the end of the "
        "course, students were confident working in digital environments "
        "and comfortable articulating their decisions using "
        "industry-standard language and best practices."
    )

    def get(over, default):
        for o in over:
            key = o.get("key") or []
            val = o.get("value", {})
            if key and "characters" in val and (key[-1] == default or key[-1][:-1] == default):
                return val["characters"]
        return None

    rows = []
    for n in nodes.values():
        if n.get("type") != "INSTANCE" or n.get("name") != "Job Row":
            continue
        box = n.get("absoluteBoundingBox") or {}
        if box.get("x") != -54.0:  # one breakpoint's copy only
            continue
        ov = n.get("overrides") or []
        rows.append(
            (
                box.get("y", 0),
                {
                    "company": get(ov, D_CO) or D_CO,
                    "title": get(ov, D_TI) or D_TI,
                    "dates": get(ov, D_DA) or D_DA,
                    "description": get(ov, D_DE) or D_DE,
                },
            )
        )
    rows.sort(key=lambda r: r[0])
    return [r[1] for r in rows]


def main():
    site = {
        "meta": {
            "title": "Angelo Outlaw's Portfolio",
            "description": (
                "I'm a designer, front-end developer, and educator with a "
                "unique blend of creative sensibility and technical "
                "ability. And yes that really is my last name!"
            ),
            "lang": "en",
        },
        "home": build_home(),
        "projects": [build_project(s, t) for s, t in PROJECTS],
    }
    dest = ROOT / "content" / "site.json"
    dest.write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest}")
    h = site["home"]
    print(f"  tagline: {h['tagline']!r}")
    print(f"  jobs: {len(h['jobs'])}  work: {len(h['work'])}")
    for p in site["projects"]:
        rows = sum(len(r["items"]) for r in p["gallery"])
        print(f"  {p['slug']}: {len(p['sections'])} sections, {len(p['gallery'])} rows/{rows} imgs, cta={bool(p['cta'])}")


if __name__ == "__main__":
    main()
