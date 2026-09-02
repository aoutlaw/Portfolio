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


def scoped(doc, which="widest"):
    """Lines of one breakpoint's subtree, plus the page's resolved rules."""
    rules = ssr_rules(doc)
    lines = body_lines(doc)
    bps = breakpoints(doc)
    bp = (bps[0] if which == "narrowest" else bps[-1])[0]
    start = next(i for i, l in enumerate(lines) if bp in l)
    ends = [i for i, l in enumerate(lines) if "data-breakpoint-id" in l and i > start]
    return lines[start : (ends[0] if ends else len(lines))], rules


def images(lines, rules):
    """Every <img> in reading order with alt text and its wrapper aspect ratio."""
    out = []
    for i, l in enumerate(lines):
        m = re.match(r"<img[^>]*>", l)
        if not m:
            continue
        src = re.search(r'src="([^"]*)"', l)
        alt = re.search(r'alt="([^"]*)"', l)
        if not src:
            continue
        ar = None
        for j in range(i - 1, max(0, i - 5), -1):
            p = props(lines[j], rules)
            if "aspect-ratio" in p:
                ar = p["aspect-ratio"]
                break
        out.append(
            {
                "src": src.group(1),
                "alt": htmllib.unescape(alt.group(1)) if alt else "",
                "aspect": ar,
            }
        )
    return out


def project_gallery(lines, rules, after=0):
    """Gallery rows: each row is a flex line of items sharing a fixed height.

    The live markup nests row > item > aspect-box > img. Rows are the divs
    carrying both `gap:32px` and `max-width:1280px`; items carry a `height`
    in px, which is what makes each row's images line up.

    An aspect-box with no <img> under it is a video: Figma uploads those as
    VIDEO fills that its client runtime mounts after hydration, so they are
    absent from the server-rendered HTML. They are emitted here as typed
    placeholders and matched to the real files by build.py.
    """
    rows, current, current_h = [], [], None

    def flush():
        nonlocal current, current_h
        if current:
            rows.append({"height": current_h, "items": current})
        current, current_h = [], None

    for i, l in enumerate(lines):
        if i < after:
            continue
        p = props(l, rules)
        if p.get("gap") == "32px" and p.get("max-width") == "1280px":
            flush()
        if re.match(r"^[0-9.]+px$", p.get("height", "")) and p.get("flex") == "1 0 0":
            current_h = p["height"]
        if "aspect-ratio" in p:
            # Look ahead for the <img> this aspect box wraps. SVGs are the
            # page's own chrome icons (back arrow, CTA arrow), never gallery
            # content, so they don't count as filling the box.
            src = alt = None
            for j in range(i, min(len(lines), i + 4)):
                if re.match(r"<img[^>]*>", lines[j]) and "/_assets/" in lines[j]:
                    cand = re.search(r'src="([^"]*)"', lines[j]).group(1)
                    if cand.endswith(".svg"):
                        break
                    src = cand
                    a = re.search(r'alt="([^"]*)"', lines[j])
                    alt = htmllib.unescape(a.group(1)) if a else ""
                    break
                if "aspect-ratio" in props(lines[j], rules) and j > i:
                    break
            if src:
                current.append({"type": "image", "src": src, "alt": alt, "aspect": p["aspect-ratio"]})
            else:
                current.append({"type": "video", "aspect": p["aspect-ratio"]})
    flush()
    return [r for r in rows if r["items"]]


def build_project(slug, title):
    doc = load(slug)
    lines, rules = scoped(doc)

    heading = intro = None
    sections, cta = [], None
    pending_h2 = None
    last_section_line = 0  # noqa: F841 (kept for reference)

    for i, l in enumerate(lines):
        t = text_of(l)
        if not t:
            continue
        p = props(l, rules)
        fs, fam = p.get("font-size"), p.get("font-family", "")
        if fs == "96px" and heading is None:
            heading = t
        elif fs == "24px" and "Poppins" in fam and intro is None and heading:
            intro = t
        elif fs == "36px" and "SemiBold" in fam:
            pending_h2 = t
        elif fs == "20px" and "Regular" in fam and pending_h2:
            sections.append({"heading": pending_h2, "body": t})
            pending_h2 = None
            last_section_line = i

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
        "intro": intro or "",
        "sections": sections,
        "cta": cta,
        # TravelCover interleaves its Before/Wireframes/After imagery between
        # the text sections rather than gathering it all at the end, so the
        # gallery scan can't start after the last section -- it takes the
        # whole subtree, with SVG chrome icons filtered out inside.
        "gallery": project_gallery(lines, rules),
    }


def work_cards(lines, rules, by_image):
    """Work cards in DOM order: destination, image, alt, box ratio and crop."""
    cards, seen = [], set()
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

                # A card is a box at some aspect ratio, with the image either
                # covering it or -- where Figma cropped a tall source --
                # scaled past it and nudged with a top offset.
                box = None
                for k in range(j - 1, max(0, j - 7), -1):
                    q = props(lines[k], rules)
                    if "aspect-ratio" in q:
                        box = q["aspect-ratio"]
                        break
                ip = props(lines[j], rules)
                crop = None
                if ip.get("height", "").endswith("%") and ip["height"] != "100%":
                    crop = {"height": ip["height"], "top": ip.get("top", "0%")}

                cards.append(
                    {
                        "slug": by_image.get(digest, m.group(1).lstrip("/") if m else None),
                        "src": src,
                        "alt": htmllib.unescape(alt.group(1)) if alt else "",
                        "box": box,
                        "crop": crop,
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
