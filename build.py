#!/usr/bin/env python3
"""
Static builder for designoutlaw.com.

Content comes from content/site.json, extracted from the live site by
research/extract_live.py. This renders it as plain HTML/CSS/JS -- dist/ is
deployed to GitHub Pages as-is, no build step runs on the server.

The markup is deliberately semantic rather than a copy of Figma Sites'
nested wrapper divs: the goal is for the *rendered result* to match the
live site at all three of its breakpoints (mobile <768, tablet 768-999,
desktop >=1000), not to reproduce its DOM.

Run:  python3 build.py
"""

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SITE_URL = "https://www.designoutlaw.com"
PRELOAD_FONTS = (
    "Poppins-Regular_6",
    "Poppins-SemiBold_6",
    "Poppins-Bold_6",
    "Gelasio_wght__1",
    "Yesteryear-Regular_1",
)
GA_MEASUREMENT_ID = "G-Q2X1WJ7ZW9"

# Google Apps Script web app: appends to a Sheet and emails the message.
# See design/apps-script/README.md.
CONTACT_FORM_ENDPOINT = (
    "https://script.google.com/macros/s/"
    "AKfycby7-yunqJZTOfhBPakWaN-VWJ99yxFlPbp-DpsXxcAwP1mqdSZBx0kSoWJfvk2zX0I/exec"
)

SITE = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
MANIFEST = json.loads(
    (ROOT / "public" / "images" / "manifest.json").read_text(encoding="utf-8")
)

NAV = ["About", "Experience", "Work", "Contact"]

# Video slots, in the order research/extract_live.py finds them per project.
VIDEOS = {
    "spaceabet": ["spaceabet-video-1", "spaceabet-video-2", "spaceabet-video-3"],
    "y-conference": ["y-conference-video"],
    "generalitravelinsurance": ["generalitravelinsurance-video"],
}


def esc(t):
    return html.escape(t or "", quote=True)


def asset(src):
    """Live /_assets/ path -> local file, or None if it never downloaded."""
    name = MANIFEST.get(src)
    return f"/images/{name}" if name else None


def nav_links(prefix="/"):
    return "".join(
        f'<a class="nav__link" href="{prefix}#{l.lower()}">{esc(l)}</a>' for l in NAV
    )


def site_nav(*, wordmark=False):
    """Home has links only, right-aligned. Project pages add the cursive
    wordmark on the left, linking home, and space-between."""
    mark = (
        f'<a class="nav__wordmark" href="/">{esc(SITE["home"]["name"])}</a>'
        if wordmark
        else ""
    )
    return f"""
<header class="nav{' nav--split' if wordmark else ''}">
  <div class="nav__inner">
    {mark}
    <nav class="nav__links" aria-label="Primary">{nav_links()}</nav>
    <button class="nav__toggle" id="nav-toggle" aria-label="Menu"
            aria-expanded="false" aria-controls="nav-menu">
      <svg viewBox="0 0 26 26" aria-hidden="true" focusable="false">
        <path d="M4 7H22M4 13H22M4 19H22" stroke="#df6951" stroke-width="2"
              stroke-linecap="round" fill="none"/>
      </svg>
    </button>
    <div class="nav__menu" id="nav-menu" hidden>{nav_links()}</div>
  </div>
</header>"""


def footer():
    return (
        '<footer class="footer"><div class="footer__inner">'
        f'<p>{esc(SITE["home"]["footer"])}</p></div></footer>'
    )


def shell(title, description, body, *, path="/", styles=(), scripts=()):
    social = asset("/_assets/v11/b80fb14f673a87c88b326e80ed5e8ab3ebcfa4f6.png")
    favicon = asset("/_assets/v11/2c11be535154e2888ea69e34a9f039c562568f0d.png")
    # The live site loads this before anything else in <head> -- including the
    # viewport meta -- and sets Consent Mode defaults (denied until a visitor
    # opts in) alongside it, so both travel together here.
    ga = (
        f"""<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('js',new Date());
gtag('config','{GA_MEASUREMENT_ID}');
gtag('consent','default',{{'ad_storage':'denied','analytics_storage':'denied'}});</script>"""
        if GA_MEASUREMENT_ID
        else ""
    )
    css = "\n".join(f'<link rel="stylesheet" href="/styles/{s}">'
                   for s in ("fonts.css", "base.css") + tuple(styles))
    # The english subset covers every glyph the site actually uses, so preloading
    # it keeps the first paint from flashing a fallback face.
    preload = "\n".join(
        f'<link rel="preload" href="/fonts/{stem}-english.woff2" as="font" '
        f'type="font/woff2" crossorigin>'
        for stem in PRELOAD_FONTS
    )
    js = "\n".join(f'<script src="/scripts/{s}" defer></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="{esc(SITE["meta"]["lang"])}">
<head>
<meta charset="utf-8">
{ga}
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(SITE_URL + path)}">
<link rel="icon" href="{esc(favicon)}" type="image/png">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(SITE_URL + path)}">
<meta property="og:type" content="website">
{f'<meta property="og:image" content="{esc(SITE_URL + social)}">' if social else ""}
<meta name="twitter:card" content="summary_large_image">
{preload}
{css}
</head>
<body>
{body}
{js}
</body>
</html>
"""


def render_home():
    h = SITE["home"]
    photo = asset("/_assets/v11/8ef2313d21392339ee72d1c88322a363a4d38a04.png")

    # About is one paragraph split across two spans on the live site: the
    # body, then a closing clause in lemon. The extractor stores them
    # separately because they carry different styles, so rejoin them here
    # (the split point is mid-sentence -- "Also, yes," + "that really is my
    # last name!" -- so a space between them is required).
    para, highlight = h["about"]["paragraph"], h["about"]["highlight"]
    about_html = esc(para)
    if highlight:
        joiner = "" if para.endswith(" ") else " "
        about_html += f'{joiner}<span class="about__highlight">{esc(highlight)}</span>'

    jobs = []
    for i, job in enumerate(h["jobs"]):
        hidden = " job--extra" if i >= h["jobs_visible"] else ""
        jobs.append(f"""
      <div class="job{hidden}">
        <button class="job__head" aria-expanded="false">
          <span class="job__chevron" aria-hidden="true">
            <svg viewBox="0 0 8 14" focusable="false"><path d="M1 13L7 7L1 1"
              stroke="#df6951" stroke-width="2" stroke-linecap="round"
              stroke-linejoin="round" fill="none"/></svg>
          </span>
          <span class="job__text">
            <span class="job__who">
              <span class="job__company">{esc(job["company"])}</span>
              <span class="job__title">{esc(job["title"])}</span>
            </span>
            <span class="job__dates">{esc(job["dates"])}</span>
          </span>
        </button>
        <div class="job__body" hidden><p>{esc(job["description"])}</p></div>
      </div>""")

    def card_inner(item):
        """A card is a box at the image's own aspect ratio. Where Figma
        cropped a tall source, the image is scaled past the box and offset;
        otherwise it simply covers it."""
        src = asset(item["src"])
        if not src:
            return None
        crop = item.get("crop") or {}
        style = "" if crop else "height:100%;top:0;object-fit:cover"
        ratios = []
        for bp, sfx in BP_SUFFIX.items():
            if item["box"].get(bp):
                ratios.append(f"--ar{sfx}:{item['box'][bp]}")
            if crop.get(bp):
                ratios.append(f"--ch{sfx}:{crop[bp]['height']}")
                ratios.append(f"--ct{sfx}:{crop[bp]['top']}")
        ratios = ";".join(ratios)
        return (
            f' style="{ratios}">'
            f'<img class="work__photo" src="{esc(src)}" alt="{esc(item["alt"])}"'
            f' loading="lazy" style="{style}">'
        )

    def card(item, extra=""):
        inner = card_inner(item)
        if not inner:
            return ""
        return f'<a class="work__card {extra}" href="/{esc(item["slug"])}/"{inner}</a>'

    by_slug = {w["slug"]: w for w in h["work"]}
    ffp = by_slug.get("firefighter-pfister")
    ffp_mark = asset("/_assets/v11/adf4b875ecf5ed87b05f9196440ea6def7b9910d.svg")
    ffp_card = ""
    if ffp:
        inner = card_inner(ffp)
        ffp_card = f"""<a class="work__card work__card--ffp" href="/firefighter-pfister/"{inner}
            <span class="work__scrim" aria-hidden="true"></span>
            <img class="work__wordmark" src="{esc(ffp_mark)}" alt="" aria-hidden="true">
          </a>"""

    body = f"""{site_nav()}
<main>
  <section class="hero">
    <div class="hero__inner">
      <h1 class="hero__wordmark">{esc(h["name"])}</h1>
      <p class="hero__tagline">{esc(h["tagline"])}</p>
    </div>
  </section>

  <section class="about" id="about">
    <div class="about__inner">
      <div class="about__text">
        <h2 class="heading heading--teal">About</h2>
        <p class="about__body">{about_html}</p>
      </div>
      <div class="about__photo">
        <img src="{esc(photo)}" alt="Angelo headshot">
      </div>
    </div>
  </section>

  <section class="experience" id="experience">
    <div class="experience__inner">
      <h2 class="heading heading--navy">Experience</h2>
      <div class="experience__group">
        <div class="experience__list" id="experience-list">{"".join(jobs)}</div>
        <div class="experience__more">
          <button class="textbutton" id="experience-toggle" aria-expanded="false"
                  aria-controls="experience-list">
            <span data-label-more>See More Experience</span>
            <span data-label-less hidden>See Less Experience</span>
            <svg class="textbutton__arrow" viewBox="0 0 20 20" aria-hidden="true"
                 focusable="false"><path d="M10 4v12M4.5 10.5L10 16l5.5-5.5"
                 stroke="#df6951" stroke-width="2" stroke-linecap="round"
                 stroke-linejoin="round" fill="none"/></svg>
          </button>
        </div>
      </div>
    </div>
  </section>

  <section class="work" id="work">
    <div class="work__inner">
      <h2 class="heading heading--teal">Work</h2>
      <div class="work__grid">
        <div class="work__row work__row--two">
          {ffp_card}
          {card(by_slug["y-conference"], "work__card--y21") if "y-conference" in by_slug else ""}
        </div>
        <div class="work__row work__row--three">
          {card(by_slug["spaceabet"]) if "spaceabet" in by_slug else ""}
          {card(by_slug["generalitravelinsurance"]) if "generalitravelinsurance" in by_slug else ""}
          {card(by_slug["travelcover"]) if "travelcover" in by_slug else ""}
        </div>
      </div>
    </div>
  </section>

  <section class="contact" id="contact">
    <div class="contact__inner">
      <h2 class="heading heading--navy">Contact</h2>
      <p class="contact__body">{esc(h["contact"]["paragraph"])}</p>
      <form class="form" action="{esc(CONTACT_FORM_ENDPOINT)}" method="POST">
        <div class="form__group">
          <div class="form__row">
            <label class="visually-hidden" for="name">Your Name</label>
            <div class="form__field">
              <input id="name" name="name" type="text" placeholder="Your Name" required>
            </div>
            <label class="visually-hidden" for="email">Your Email</label>
            <div class="form__field">
              <input id="email" name="email" type="email" placeholder="Your Email" required>
            </div>
          </div>
          <label class="visually-hidden" for="message">What do you want to talk about?</label>
          <div class="form__field form__field--area">
            <textarea id="message" name="message" rows="3" required
              placeholder="What do you want to talk about?"></textarea>
          </div>
        </div>
        <div class="visually-hidden" aria-hidden="true">
          <label for="company">Company</label>
          <input id="company" name="company" type="text" tabindex="-1" autocomplete="off">
        </div>
        <button class="button" type="submit">Send It</button>
      </form>
    </div>
  </section>
</main>
{footer()}"""
    return shell(
        SITE["meta"]["title"],
        SITE["meta"]["description"],
        body,
        path="/",
        styles=("home.css",),
        scripts=("motion.js", "nav.js", "anchors.js", "experience.js",
                 "contact-form.js"),
    )


BP_SUFFIX = {"mobile": "", "tablet": "-t", "desktop": "-d"}


def gallery_vars(blocks):
    """The gallery block's padding, which the live build varies per page --
    the header and body blocks are on one pinned scale (see project.css), but
    the gallery still frames each set of shots on its own terms."""
    out = []
    for bp, sfx in BP_SUFFIX.items():
        pad = (blocks[bp].get("gallery") or {}).get("padding")
        if pad:
            out.append(f"--gal-pad{sfx}:{pad}")
    return ";".join(out)


def row_vars(row):
    """--dir and --al per breakpoint: rows stack into a column at narrow
    widths (and a few stay stacked at tablet), and most centre their
    overflowing cells while a couple align them to the top."""
    out = []
    for bp, sfx in BP_SUFFIX.items():
        row_axis = row["direction"][bp] == "row"
        out.append(f"--dir{sfx}:{row['direction'][bp]}")
        # In a stacked row the cross axis is horizontal, where the live
        # cells span the full width; only a side-by-side row's alignment
        # says anything about how the overflow sits.
        out.append(f"--al{sfx}:{row['align'][bp] if row_axis else 'stretch'}")
    return ";".join(out)


def cell_vars(item, row):
    """--h (the cell's fixed height), --f, and the three properties that
    place the box inside it. A cell laid out in a row shares the width with
    its siblings; a stacked one sizes to --h."""
    out = []
    for bp, sfx in BP_SUFFIX.items():
        cdir, cal, cjust = item["place"][bp]
        out.append(f"--h{sfx}:{item['cell'][bp]}")
        out.append(f"--f{sfx}:{'1 0 0' if row['direction'][bp] == 'row' else '0 0 auto'}")
        out.append(f"--cdir{sfx}:{cdir}")
        out.append(f"--cal{sfx}:{cal}")
        out.append(f"--cjust{sfx}:{cjust}")
    return ";".join(out)


BOX_FIT = {
    # width, height
    "cover": ("100%", "auto"),    # box spans the cell and overflows it
    "contain": ("auto", "100%"),  # box spans the cell's height instead
    "fill": ("100%", "100%"),     # no ratio of its own; takes the cell's
}


def box_vars(item):
    """--ar/--bw/--bh per breakpoint: the box's ratio and which of the
    cell's dimensions it spans. A fit that isn't one of the three named
    modes is a literal width the box holds however wide the cell gets.
    --iw/--ih/--ix/--iy carry a baked-in image crop where there is one."""
    out = []
    for bp, sfx in BP_SUFFIX.items():
        fit = item["fit"][bp]
        w, h = BOX_FIT.get(fit, (fit, "auto"))
        out.append(f"--ar{sfx}:{item['aspect'][bp]}")
        out.append(f"--bw{sfx}:{w}")
        out.append(f"--bh{sfx}:{h}")
    if item["crop"]:
        names = ("--iw", "--ih", "--ix", "--iy")
        out += [f"{n}:{v:g}%" for n, v in zip(names, item["crop"])]
    return ";".join(out)


def render_project(p):
    """Case-study page.

    The gallery mirrors the live nesting -- row > cell > aspect box > media.
    The cell has a fixed pixel height and clips; the box inside is
    width-driven, so a tall image overflows the cell and gets centre-cropped
    by it. Direction, gap, cell height and box ratio all change per
    breakpoint, so each is passed through as a custom property and picked up
    by the media queries in project.css.
    """
    videos = list(VIDEOS.get(p["slug"], []))
    rows = []
    for row in p["gallery"]:
        cells = []
        for it in row["items"]:
            if it["type"] == "video":
                stem = videos.pop(0) if videos else None
                if not stem:
                    continue
                media = (f'<video src="/images/{stem}.mp4"'
                         f' poster="/images/{stem}-poster.webp"'
                         f" autoplay muted loop playsinline></video>")
            else:
                src = asset(it["src"])
                if not src:
                    continue
                media = (f'<img src="{esc(src)}" alt="{esc(it["alt"])}"'
                         f" loading=\"lazy\">")
            cells.append(
                f'<div class="shot" style="{esc(cell_vars(it, row))}">'
                f'<div class="shot__box{" shot__box--crop" if it["crop"] else ""}"'
                f' style="{esc(box_vars(it))}">{media}</div></div>'
            )
        if cells:
            label = (f'<h2 class="gallery__label">{esc(row["label"])}</h2>'
                     if row["label"] else "")
            rows.append(
                f'<div class="gallery__group">{label}'
                f'<div class="gallery__row" style="{esc(row_vars(row))}">'
                f'{"".join(cells)}</div></div>'
            )

    sections = "".join(
        f'<section class="case__section"><h2>{esc(s["heading"])}</h2>'
        f'<p>{esc(s["body"])}</p></section>'
        for s in p["sections"]
    )

    cta = ""
    if p.get("cta"):
        cta = f"""<a class="button button--cta" href="{esc(p['cta']['href'])}"
             target="_blank" rel="noopener">{esc(p['cta']['label'])}
          <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path
            d="M5 15L15 5M7 5h8v8" stroke="#fff" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg></a>"""

    body = f"""{site_nav(wordmark=True)}
<main>
  <section class="case__head">
    <div class="case__head-inner">
      <a class="textbutton textbutton--back" href="/#work">
        <svg class="textbutton__arrow" viewBox="0 0 20 20" aria-hidden="true"
             focusable="false"><path d="M16 10H4M9.5 4.5L4 10l5.5 5.5"
             stroke="#df6951" stroke-width="2" stroke-linecap="round"
             stroke-linejoin="round" fill="none"/></svg>Back to Work</a>
      <div class="case__intro">
        <h1 class="heading heading--teal">{esc(p["heading"])}</h1>
        <div class="case__intro-text">
          {"".join(f"<p>{esc(t)}</p>" for t in p["intro"])}
        </div>
      </div>
      {cta}
    </div>
  </section>

  <section class="case__body">
    <div class="case__body-inner">{sections}</div>
  </section>

  <section class="gallery">
    <div class="gallery__inner" style="{esc(gallery_vars(p["blocks"]))}">{"".join(rows)}</div>
  </section>
</main>
{footer()}"""
    return shell(
        f"{p['title']} — {SITE['home']['name']}",
        (p["intro"][0][:200] if p["intro"] else SITE["meta"]["description"]),
        body,
        path=f"/{p['slug']}/",
        styles=("project.css",),
        scripts=("motion.js", "nav.js", "anchors.js"),
    )


def render_404():
    body = f"""{site_nav(wordmark=True)}
<main>
  <section class="case__head">
    <div class="case__head-inner">
      <div class="case__intro">
        <h1 class="heading heading--teal">Page not found</h1>
        <p><a href="/" style="color:#df6951">Back home</a></p>
      </div>
    </div>
  </section>
</main>
{footer()}"""
    return shell("Page not found", "Page not found.", body, path="/404.html",
                 styles=("project.css",), scripts=("motion.js", "nav.js", "anchors.js"))


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    write(DIST / "index.html", render_home())
    for p in SITE["projects"]:
        write(DIST / p["slug"] / "index.html", render_project(p))
    write(DIST / "404.html", render_404())

    shutil.copytree(ROOT / "public" / "images", DIST / "images")
    shutil.copytree(ROOT / "public" / "fonts", DIST / "fonts")
    shutil.copytree(ROOT / "src" / "styles", DIST / "styles")
    shutil.copytree(ROOT / "src" / "scripts", DIST / "scripts")

    print(f"wrote {2 + len(SITE['projects'])} pages to {DIST}")


if __name__ == "__main__":
    main()
