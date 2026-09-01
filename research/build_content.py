#!/usr/bin/env python3
"""
Turn the crawled Figma Sites scene graphs (research/raw/*.json) into the
canonical content file at content/site.json.

Same approach as firefighterpfister: TEXT nodes carry the exact copy in
`characters`. designoutlaw.com is a single-page site (nav anchors, not
routes) plus five case-study pages reached via internal NAVIGATE
interactions, so each is fetched and stored as its own raw file rather than
crawled by slug list.

Copy is verbatim. No smart-quote substitution, no tidying beyond splitting
paragraphs on newlines.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "research" / "raw"

PROJECTS = [
    ("spaceabet", "Spaceabet"),
    ("y-conference", "Y Conference"),
    ("firefighter-pfister", "Firefighter Pfister"),
    ("travelcover", "Travel Cover"),
    ("generalitravelinsurance", "Generali Travel Insurance"),
]


def load(slug):
    return json.loads((RAW / f"{slug}.json").read_text(encoding="utf-8"))


def paragraphs(text):
    return [p.strip() for p in re.split(r"[\n ]", text) if p.strip()]


def unique_texts(doc, exclude=("Ag", "Button Text")):
    """Dedup TEXT node characters across breakpoint triplicates, in
    reading order (top to bottom)."""
    nodes = doc["nodeById"]
    seen, out = set(), []
    items = sorted(
        (n for n in nodes.values() if n.get("type") == "TEXT"),
        key=lambda n: (n.get("absoluteBoundingBox") or {}).get("y", 0),
    )
    for n in items:
        chars = n.get("characters", "")
        if not chars.strip() or chars in seen or chars in exclude:
            continue
        seen.add(chars)
        out.append(chars)
    return out


def desktop_root(doc):
    """Project pages triplicate their whole layout once per breakpoint
    (Desktop / Tablet / Mobile), each a sibling under the WEBPAGE node.
    Scoping to the widest sibling avoids interleaving text or images from
    the other two copies, which the home page's single-frame sections
    don't need to worry about."""
    nodes = doc["nodeById"]
    page = next(n for n in nodes.values() if n.get("type") == "WEBPAGE")
    children = [nodes[c] for c in page.get("children", []) if c in nodes]
    return max(children, key=lambda n: (n.get("absoluteBoundingBox") or {}).get("width", 0))


def subtree_ids(doc, root):
    nodes = doc["nodeById"]
    ids, stack = set(), [root["id"]]
    while stack:
        nid = stack.pop()
        if nid in ids or nid not in nodes:
            continue
        ids.add(nid)
        stack.extend(nodes.get(nid, {}).get("children", []) or [])
    return ids


def scoped_texts(doc, root, exclude=("Ag", "Button Text")):
    nodes = doc["nodeById"]
    ids = subtree_ids(doc, root)
    seen, out = set(), []
    items = sorted(
        (nodes[i] for i in ids if nodes[i].get("type") == "TEXT"),
        key=lambda n: (n.get("absoluteBoundingBox") or {}).get("y", 0),
    )
    for n in items:
        chars = n.get("characters", "")
        if not chars.strip() or chars in seen or chars in exclude:
            continue
        seen.add(chars)
        out.append(chars)
    return out


def collect_job_rows(doc, anchor_x=-54.0):
    """Job Row instances carry per-row text as override deltas against the
    component's default text. A row with no overrides at all is the
    component's own default content (Point Loma Nazarene University)."""
    nodes = doc["nodeById"]

    def texts_by_key(overrides):
        out = {}
        for o in overrides:
            val = o.get("value", {})
            if "characters" in val:
                out[tuple(o.get("key", []))] = val["characters"]
        return out

    def get(texts, default_suffix):
        for k, v in texts.items():
            if k and (k[-1] == default_suffix or k[-1][:-1] == default_suffix):
                return v
        return None

    DEFAULT_COMPANY = "Point Loma Nazarene University"
    DEFAULT_TITLE = "Adjunct Professor - Art Department"
    DEFAULT_DATES = "May 2023 - May 2026"
    DEFAULT_DESC = (
        "I crafted and taught a curriculum built to be accessible to "
        "students with no digital design experience. This curriculum used "
        "a human-centered approach that referenced real-world scenarios "
        "intended build comfort levels among students. By the end of the "
        "course, students were confident working in digital environments "
        "and comfortable articulating their decisions using "
        "industry-standard language and best practices."
    )

    rows = []
    for n in nodes.values():
        if n.get("type") != "INSTANCE" or n.get("name") != "Job Row":
            continue
        box = n.get("absoluteBoundingBox") or {}
        if box.get("x") != anchor_x:
            continue
        texts = texts_by_key(n.get("overrides") or [])
        state = n.get("componentProperties", {}).get("expandedState", {}).get("value")
        rows.append((
            box.get("y", 0),
            {
                "company": get(texts, DEFAULT_COMPANY) or DEFAULT_COMPANY,
                "title": get(texts, DEFAULT_TITLE) or DEFAULT_TITLE,
                "dates": get(texts, DEFAULT_DATES) or DEFAULT_DATES,
                "expanded": state == "Expanded",
                "description": get(texts, DEFAULT_DESC) or DEFAULT_DESC,
            },
        ))
    rows.sort(key=lambda r: r[0])
    return [r[1] for r in rows]


def collect_work_links(doc):
    """Work-section cards: a clickable FRAME with an ON_CLICK NAVIGATE
    interaction wrapping an image fill (RECTANGLE, or nested inside a
    thumbnail FRAME for Firefighter Pfister's labeled version).

    A Row can hold several cards, and the interaction sits on whichever
    ancestor is the tightest click target -- sometimes the Row itself
    (when it holds exactly one card without its own override), sometimes
    an individual card FRAME nested inside a Row that also carries an
    unrelated interaction for a sibling card. Walking into a descendant
    that declares its own interactions would attribute a sibling card's
    image to this link, so the search stops at those boundaries."""
    nodes = doc["nodeById"]

    def image_ref(node):
        for f in node.get("fills") or []:
            if f.get("type") == "IMAGE":
                return f["imageRef"]
        for c in node.get("children") or []:
            child = nodes.get(c, {})
            if child.get("interactions"):
                continue
            ref = image_ref(child)
            if ref:
                return ref
        return None

    seen_slugs, links = set(), []
    for n in nodes.values():
        for it in n.get("interactions") or []:
            for action in it.get("actions", []):
                url = action.get("connectionURL")
                if not url or not url.startswith("/") or url in ("/", "/coming-soon"):
                    continue
                slug = url.lstrip("/")
                if slug in seen_slugs:
                    continue
                ref = image_ref(n)
                if not ref:
                    continue
                seen_slugs.add(slug)
                box = n.get("absoluteBoundingBox") or {}
                links.append((box.get("y", 0), slug, ref))
    links.sort(key=lambda r: r[0])
    return [{"slug": slug, "image_ref": ref} for _, slug, ref in links]


def collect_gallery(doc, root):
    """Ordered, deduped list of media items (images and, for
    generalitravelinsurance, an autoplaying muted demo VIDEO) used as
    RECTANGLE fills within one breakpoint's subtree. Excludes the small
    icon/divider SVGs (ASSET-fill SVG nodes, not RECTANGLE fills) and the
    hero/portrait shot reused from the home page plus the case-study's own
    thumbnail, which belong to page chrome, not the gallery."""
    nodes = doc["nodeById"]
    ids = subtree_ids(doc, root)
    skip_names = {"Angelo Outlaw Picture"}
    seen, out = set(), []
    items = sorted(
        (nodes[i] for i in ids if nodes[i].get("type") == "RECTANGLE"),
        key=lambda n: (n.get("absoluteBoundingBox") or {}).get("y", 0),
    )
    for n in items:
        if n.get("name") in skip_names:
            continue
        for f in n.get("fills") or []:
            if f.get("type") == "IMAGE":
                ref = f["imageRef"]
                if ref not in seen:
                    seen.add(ref)
                    out.append({"type": "image", "ref": ref})
            elif f.get("type") == "VIDEO":
                ref = f["videoRef"]
                if ref not in seen:
                    seen.add(ref)
                    out.append({
                        "type": "video",
                        "ref": ref,
                        "poster_ref": f.get("imageRef"),
                    })
    return out


def build_home():
    doc = load("home")
    texts = unique_texts(doc)

    tagline = next(t for t in texts if t.startswith("Designer"))
    about_body = next(
        t for t in texts if t.startswith("I'm a digital designer")
    )
    contact_body = next(t for t in texts if t.startswith("I’d love to hear"))
    footer = next(t for t in texts if t.startswith("© Angelo Outlaw"))

    jobs = collect_job_rows(doc)
    work_links = collect_work_links(doc)

    return {
        "name": "Angelo Outlaw",
        "tagline": tagline.replace("\xa0", " ").strip(),
        "nav": ["About", "Experience", "Work", "Contact"],
        "about": {"heading": "About", "paragraphs": paragraphs(about_body)},
        "experience": {"heading": "Experience", "jobs": jobs},
        "work": {"heading": "Work", "items": work_links},
        "contact": {
            "heading": "Contact",
            "paragraphs": paragraphs(contact_body),
        },
        "footer": footer,
    }


def build_project(slug, title):
    doc = load(slug)
    root = desktop_root(doc)
    texts = scoped_texts(doc, root)
    # Chrome strings common to every project page.
    chrome = {"Work", "Back to Work", title, "Angelo Outlaw"}
    chrome |= {t for t in texts if t.startswith("© Angelo Outlaw")}
    body = [t for t in texts if t not in chrome]

    def after(label):
        try:
            i = body.index(label)
        except ValueError:
            return None
        return body[i + 1] if i + 1 < len(body) else None

    intro = body[0] if body and body[0] not in ("Challenge", "Solution", "Results") else None
    sections = {
        "challenge": after("Challenge"),
        "solution": after("Solution"),
        "results": after("Results"),
    }
    extra_labels = [
        t for t in body
        if t not in (intro, sections["challenge"], sections["solution"], sections["results"])
        and t not in ("Challenge", "Solution", "Results")
    ]

    return {
        "slug": slug,
        "title": title,
        "intro": paragraphs(intro) if intro else [],
        "challenge": paragraphs(sections["challenge"]) if sections["challenge"] else [],
        "solution": paragraphs(sections["solution"]) if sections["solution"] else [],
        "results": paragraphs(sections["results"]) if sections["results"] else [],
        "extra_notes": extra_labels,
        "gallery": collect_gallery(doc, root),
    }


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
        "projects": [build_project(slug, title) for slug, title in PROJECTS],
    }

    dest = ROOT / "content" / "site.json"
    dest.write_text(
        json.dumps(site, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"wrote {dest}")
    print(f"experience: {len(site['home']['experience']['jobs'])} jobs")
    print(f"work links: {len(site['home']['work']['items'])}")
    for p in site["projects"]:
        print(
            f"  {p['slug']}: intro={len(p['intro'])}p "
            f"challenge={len(p['challenge'])}p solution={len(p['solution'])}p "
            f"results={len(p['results'])}p gallery={len(p['gallery'])} "
            f"extra={p['extra_notes']}"
        )


if __name__ == "__main__":
    main()
