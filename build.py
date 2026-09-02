#!/usr/bin/env python3
"""
Static builder for designoutlaw.com.

Same approach as firefighterpfister: content lives in content/site.json
(verbatim copy pulled from the live Figma Sites scene graph, see
research/build_content.py), and this script is the only thing that turns
it into HTML. Plain files out -- dist/ is deployed to GitHub Pages as-is,
no build step runs on the server.

Run:  python3 build.py
"""

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
SITE_URL = "https://www.designoutlaw.com"
GA_MEASUREMENT_ID = "G-Q2X1WJ7ZW9"

# Google Apps Script web app endpoint for the contact form (appends to a
# Sheet, emails the message on). Static hosting has no server of its own to
# receive a POST, so the form submits here instead -- see
# design/apps-script/README.md for setup. Left as a placeholder, the
# frontend (src/scripts/contact-form.js) detects it and shows a
# "not connected yet" message instead of silently swallowing submissions.
CONTACT_FORM_ENDPOINT = "https://script.google.com/macros/s/AKfycby7-yunqJZTOfhBPakWaN-VWJ99yxFlPbp-DpsXxcAwP1mqdSZBx0kSoWJfvk2zX0I/exec"

SITE = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
MANIFEST = json.loads(
    (ROOT / "public" / "images" / "manifest.json").read_text(encoding="utf-8")
)


def esc(text):
    return html.escape(text or "", quote=True)


def img(ref):
    """Resolve a Figma asset ref to its downloaded public path, or None if
    it failed to download (some embedded phone videos aren't reachable from
    designoutlaw.com's static asset CDN -- see research/download_images.py).
    Callers are expected to skip gracefully when this returns None."""
    entry = MANIFEST.get(ref)
    return f"/images/{entry['file']}" if entry else None


def nav(current="/"):
    home = SITE["home"]
    links = "".join(
        f'<a href="/#{label.lower()}" class="nav-link">{esc(label)}</a>'
        for label in home["nav"]
    )
    return f"""
<header class="site-nav">
  <div class="nav-inner">
    <a href="/" class="nav-wordmark">{esc(home["name"])}</a>
    <nav class="nav-links" aria-label="Primary">{links}</nav>
    <button class="nav-hamburger" id="nav-hamburger" aria-label="Open menu" aria-expanded="false" aria-controls="mobile-drawer">
      <span></span><span></span><span></span>
    </button>
  </div>
</header>
<div class="mobile-drawer" id="mobile-drawer" hidden>
  <nav aria-label="Mobile">
    {"".join(f'<a href="/#{l.lower()}" class="drawer-link">{esc(l)}</a>' for l in home["nav"])}
  </nav>
</div>
"""


def footer():
    return f'<footer class="site-footer"><p>{esc(SITE["home"]["footer"])}</p></footer>'


def page_shell(title, description, body, *, canonical_path="/", social_image_ref=None, extra_head=""):
    social = img(social_image_ref) if social_image_ref else img("b80fb14f673a87c88b326e80ed5e8ab3ebcfa4f6")
    favicon = img("2c11be535154e2888ea69e34a9f039c562568f0d")
    canonical = SITE_URL + canonical_path
    ga = f"""
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_MEASUREMENT_ID}');
</script>""" if GA_MEASUREMENT_ID else ""

    return f"""<!doctype html>
<html lang="{esc(SITE["meta"]["lang"])}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}" />
<link rel="canonical" href="{esc(canonical)}" />
<link rel="icon" href="{esc(favicon)}" type="image/png" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(canonical)}" />
<meta property="og:type" content="website" />
{f'<meta property="og:image" content="{esc(SITE_URL + social)}" />' if social else ""}
<meta name="twitter:card" content="summary_large_image" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Gelasio:ital,wght@0,400;0,700;1,400&amp;family=Poppins:wght@400;500;600;700&amp;family=Yesteryear&amp;display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/styles/tokens.css" />
<link rel="stylesheet" href="/styles/base.css" />
<link rel="stylesheet" href="/styles/chrome.css" />
{extra_head}
{ga}
</head>
<body>
{body}
</body>
</html>
"""


def paragraphs_html(paras, class_=""):
    cls = f' class="{class_}"' if class_ else ""
    return "\n".join(f"<p{cls}>{esc(p)}</p>" for p in paras)


def render_home():
    home = SITE["home"]
    hero_photo = img("8ef2313d21392339ee72d1c88322a363a4d38a04")

    jobs_html = []
    for i, job in enumerate(home["experience"]["jobs"]):
        open_attr = " open" if job["expanded"] else ""
        jobs_html.append(f"""
      <details class="job-row"{open_attr}>
        <summary class="job-summary">
          <span class="job-heading">
            <span class="job-company">{esc(job["company"])}</span>
            <span class="job-title">{esc(job["title"])}</span>
          </span>
          <span class="job-dates">{esc(job["dates"])}</span>
          <span class="job-chevron" aria-hidden="true"></span>
        </summary>
        <p class="job-description">{esc(job["description"])}</p>
      </details>""")

    work_html = []
    for item in home["work"]["items"]:
        image = img(item["image_ref"])
        style = f' style="background-image:url(\'{esc(image)}\')"' if image else ""
        title = item["slug"].replace("-", " ").title()
        work_html.append(f"""
      <a class="work-card" href="/{esc(item["slug"])}/" aria-label="View {esc(title)} case study"{style}></a>""")

    body = f"""
{nav()}
<main>
  <section class="hero">
    <div class="hero-inner">
      <div class="hero-text">
        <h1 class="wordmark">{esc(home["name"])}</h1>
        <p class="tagline">{esc(home["tagline"])}</p>
      </div>
    </div>
  </section>

  <section id="about" class="section section-inverse">
    <div class="section-inner about-grid">
      <div>
        <h2>{esc(home["about"]["heading"])}</h2>
        {paragraphs_html(home["about"]["paragraphs"], "about-paragraph")}
      </div>
      <img class="about-photo" src="{esc(hero_photo)}" alt="{esc(home["name"])}" width="600" height="800" loading="eager" />
    </div>
  </section>

  <section id="experience" class="section">
    <div class="section-inner">
      <h2>{esc(home["experience"]["heading"])}</h2>
      <div class="job-list">{"".join(jobs_html)}</div>
    </div>
  </section>

  <section id="work" class="section section-inverse">
    <div class="section-inner">
      <h2>{esc(home["work"]["heading"])}</h2>
      <div class="work-grid">{"".join(work_html)}</div>
    </div>
  </section>

  <section id="contact" class="section">
    <div class="section-inner contact-grid">
      <div>
        <h2>{esc(home["contact"]["heading"])}</h2>
        {paragraphs_html(home["contact"]["paragraphs"], "contact-paragraph")}
      </div>
      <form class="contact-form" action="{esc(CONTACT_FORM_ENDPOINT)}" method="POST">
        <label class="visually-hidden" for="name">Your Name</label>
        <input id="name" name="name" type="text" placeholder="Your Name" required />
        <label class="visually-hidden" for="email">Your Email</label>
        <input id="email" name="email" type="email" placeholder="Your Email" required />
        <label class="visually-hidden" for="message">What do you want to talk about?</label>
        <textarea id="message" name="message" placeholder="What do you want to talk about?" rows="4" required></textarea>
        <div class="visually-hidden" aria-hidden="true">
          <label for="company">Company</label>
          <input id="company" name="company" type="text" tabindex="-1" autocomplete="off" />
        </div>
        <button type="submit" class="button-primary">Send It</button>
        <p class="form-status" data-form-status hidden></p>
      </form>
    </div>
  </section>
</main>
{footer()}
<script src="/scripts/nav.js" defer></script>
<script src="/scripts/contact-form.js" defer></script>
"""
    return page_shell(
        SITE["meta"]["title"],
        SITE["meta"]["description"],
        body,
        canonical_path="/",
        extra_head='<link rel="stylesheet" href="/styles/home.css" />',
    )


def render_project(project):
    hero_photo = img("8ef2313d21392339ee72d1c88322a363a4d38a04")
    title = project["title"]

    gallery_html = []
    for m in project["gallery"]:
        if m["type"] == "image":
            src = img(m["ref"])
            if not src:
                continue
            gallery_html.append(
                f'<img class="gallery-item" src="{esc(src)}" alt="" loading="lazy" />'
            )
        elif m["type"] == "video":
            src = img(m["ref"])
            poster = img(m.get("poster_ref")) if m.get("poster_ref") else None
            if not src:
                # Not reachable from the static asset CDN -- fall back to
                # the poster frame if that downloaded, otherwise skip.
                if poster:
                    gallery_html.append(
                        f'<img class="gallery-item" src="{esc(poster)}" alt="" loading="lazy" />'
                    )
                continue
            poster_attr = f' poster="{esc(poster)}"' if poster else ""
            gallery_html.append(
                f'<video class="gallery-item" src="{esc(src)}"{poster_attr} autoplay muted loop playsinline></video>'
            )

    notes_html = (
        f'<p class="project-notes">{" · ".join(esc(n) for n in project["extra_notes"])}</p>'
        if project["extra_notes"]
        else ""
    )

    body = f"""
{nav()}
<main>
  <article class="project">
    <div class="section-inner">
      <a class="back-link" href="/#work">&larr; Back to Work</a>
      <h1>{esc(title)}</h1>
      {paragraphs_html(project["intro"], "project-intro")}

      <div class="project-columns">
        <section>
          <h2>Challenge</h2>
          {paragraphs_html(project["challenge"])}
        </section>
        <section>
          <h2>Solution</h2>
          {paragraphs_html(project["solution"])}
        </section>
        <section>
          <h2>Results</h2>
          {paragraphs_html(project["results"])}
        </section>
      </div>

      {notes_html}
      <div class="project-gallery">{"".join(gallery_html)}</div>
    </div>
  </article>
</main>
{footer()}
<script src="/scripts/nav.js" defer></script>
"""
    return page_shell(
        f"{title} — {SITE['home']['name']}",
        (project["intro"][0] if project["intro"] else SITE["meta"]["description"]),
        body,
        canonical_path=f"/{project['slug']}/",
        extra_head='<link rel="stylesheet" href="/styles/project.css" />',
    )


def render_404():
    body = f"""
{nav()}
<main>
  <section class="section not-found">
    <div class="section-inner">
      <h1>Page not found</h1>
      <p><a href="/">Back home</a></p>
    </div>
  </section>
</main>
{footer()}
"""
    return page_shell("Page not found", "Page not found.", body, canonical_path="/404.html")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    write(DIST / "index.html", render_home())
    for project in SITE["projects"]:
        write(DIST / project["slug"] / "index.html", render_project(project))
    write(DIST / "404.html", render_404())

    shutil.copytree(ROOT / "public" / "images", DIST / "images")
    shutil.copytree(ROOT / "src" / "styles", DIST / "styles")
    (DIST / "styles" / "tokens.css").write_text(
        (ROOT / "design" / "tokens" / "tokens.css").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    shutil.copytree(ROOT / "src" / "scripts", DIST / "scripts")

    (DIST / "CNAME").write_text("www.designoutlaw.com\n", encoding="utf-8")

    pages = 2 + len(SITE["projects"])
    print(f"wrote {pages} pages to {DIST}")


if __name__ == "__main__":
    main()
