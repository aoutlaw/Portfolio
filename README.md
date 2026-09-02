# designoutlaw.com

Rebuild of [www.designoutlaw.com](https://www.designoutlaw.com), moving it off Figma
Sites hosting and onto GitHub Pages. This first pass is a **faithful port**: same
content, same layout, same color and type system as the live Figma Sites version.
Redesign work happens after the migration itself is verified and DNS is cut over.

## Layout

```
content/site.json       Canonical content. Verbatim copy from the live site.
research/raw/            Crawled Figma Sites scene graphs (one per page).
research/build_content.py   Turns research/raw/*.json into content/site.json.
research/download_images.py Downloads every image/video content/site.json references.
design/tokens/            Design tokens + the generator that emits them.
src/                       Site source: styles, scripts.
public/images/             Downloaded imagery + manifest.json (ref hash -> file).
build.py                   Static builder. Plain HTML out, no JS framework.
dist/                      Build output (gitignored, built by CI on every push).
```

## Where the content comes from

Same situation as firefighterpfister: the live site is built with Figma Sites, which
serves its full scene graph as JSON at `/_json/<site-id>/<slug>.json`. `TEXT` nodes
carry the exact string in `characters`. designoutlaw.com is a single scrolling page
(About/Experience/Work/Contact are anchors, not routes) with five case-study pages
reached by internal `NAVIGATE` interactions — `/spaceabet`, `/y-conference`,
`/firefighter-pfister`, `/travelcover`, `/generalitravelinsurance`.

Rebuild the content and image files with:

```bash
python3 research/build_content.py
python3 research/download_images.py
```

`research/build_content.py` does **not** re-fetch from the live site — it reads the
snapshots already committed in `research/raw/`. To refresh those snapshots from a
live edit in Figma, fetch `https://www.designoutlaw.com/_json/2075e7b5-06d4-494b-beab-69ce6a3a4949/<slug>.json`
for `_index` (home) and each of the five project slugs above, and overwrite the
matching file in `research/raw/`.

**Resolved gap:** short process/demo videos embedded in the Spaceabet, Y Conference,
and Generali Travel Insurance pages are uploaded Figma video assets, not served from
the same static `/_assets/v11/<hash>.<ext>` path as images — fetching them 404s.
`download_images.py` skips them and falls back to the poster frame where one
downloaded, otherwise nothing.

All five clips were recovered by having Angelo supply the original files directly;
`research/import_videos.py` wires them in — copies each into `public/images/` (an
`.mp4` source as-is; a `.mov` source re-encoded to `.mp4` with PyAV/libx264, since
QuickTime's B-frame edit lists don't survive a packet-copy remux into plain MP4),
extracts a poster frame, and adds both to `manifest.json` under the ref hashes
`content/site.json` already points at, so `build.py` needed no changes.

## Design tokens

`design/tokens/tokens.css` is generated — edit the tables in
`design/tokens/generate_tokens.py` instead:

```bash
python3 design/tokens/generate_tokens.py
```

Figma pins three discrete breakpoint stops; the tokens interpolate fluidly between
the mobile (375px) and desktop (1440px) anchors. Colors and their semantic aliases
(e.g. `--text-h1` = Kingfisher navy, `--accent` = Salmon) were resolved by matching
each Figma variable alias to the primitive color it points at — see the comments in
`generate_tokens.py`.

## Building

```bash
python3 build.py
```

Writes plain HTML/CSS/JS to `dist/`: one page per case study
(`dist/spaceabet/index.html`, etc.) plus `dist/index.html` for the home page — clean
URLs work natively on GitHub Pages this way, no `.htaccess` rewrite needed.

Preview locally:

```bash
python3 build.py && python3 -m http.server -d dist 8000
```

## Deploying

`.github/workflows/deploy.yml` builds and publishes to GitHub Pages automatically on
every push to `main`. No manual deploy step, no server credentials to manage — this
is the main practical difference from firefighterpfister's `rsync`-over-SSH pattern
(see that repo's README for the tradeoffs that led to trying GitHub Pages here
instead).

One-time repo setting: **Settings → Pages → Source → GitHub Actions**. `dist/CNAME`
(written by `build.py`) points the custom domain at `www.designoutlaw.com`; update
DNS at your registrar to GitHub Pages' target once a deploy has gone out successfully
and you've checked it on the `*.github.io` URL first — same "confirm before cutting
DNS" order firefighterpfister's README recommends.

## Contact form

The live Sites version ran its contact form through Figma's own backend, which goes
away with the migration. This rebuild posts to a Google Apps Script web app instead
— same pattern as firefighterpfister's contact form: it appends each message to a
Sheet in your Drive and emails it to you, no server to run and no third-party form
service account to create.

Setup is in `design/apps-script/README.md`; `CONTACT_FORM_ENDPOINT` in `build.py` is
now wired to the deployed endpoint and verified end-to-end (row appended to the
Sheet, notification email sent). If it's ever redeployed as a fresh deployment
(rather than a new version of the same one), Apps Script issues a new `/exec` URL —
update `CONTACT_FORM_ENDPOINT` to match.

## Open items

- This is the faithful-port pass. Design/interaction refinement is deliberately
  deferred to a follow-up pass once the migration itself is confirmed working.
