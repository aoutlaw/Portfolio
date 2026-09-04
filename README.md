# designoutlaw.com

Rebuild of [www.designoutlaw.com](https://www.designoutlaw.com), moving it off Figma
Sites hosting. This first pass is a **faithful port**: same content, same layout,
same color and type system as the live Figma Sites version. Redesign work happens
after the migration itself is verified and DNS is cut over.

GitHub Pages was the first hosting target tried here, and it worked, but
designoutlaw.com's own web root on Bluehost already hosts other things that were
never part of this repo. A GitHub Pages custom domain claims the *entire* domain —
every path that isn't in `dist/` 404s — so anything living outside this repo broke
the moment DNS pointed there. This deploys the same way firefighterpfister.com does
instead: GitHub for version control, `rsync` over SSH to Bluehost for serving,
`designoutlaw.com`'s own web root left otherwise untouched. See `deploy.sh` for how
that coexists safely with everything else already in that directory.

## Layout

```
content/site.json           Canonical content, extracted from the live pages.
research/raw_html/          Saved copies of the six live pages.
research/raw/               Figma Sites scene graphs (Experience descriptions).
research/extract_live.py    Turns the saved pages into content/site.json.
research/download_assets.py Downloads + re-encodes every asset it references.
research/import_videos.py   Wires in the video clips Figma won't serve.
design/apps-script/         Contact-form endpoint (Google Apps Script).
src/                        Site source: styles, scripts.
public/images/              Optimised imagery + manifest.json (live path -> file).
build.py                    Static builder. Plain HTML out, no JS framework.
dist/                       Build output (gitignored, built by CI on every push).
```

## Where the content comes from

The live site is built with Figma Sites, which server-renders **every breakpoint**
into the HTML and ships the resolved styles alongside as a `#container .css-xxx {…}`
block. That's richer than the scene-graph JSON Figma also exposes: it gives the
rendered geometry — gallery grouping, image alt text, per-breakpoint type sizes and
crops — not just the copy. So the extractor reads the rendered pages.

designoutlaw.com is a single scrolling page (About/Experience/Work/Contact are
anchors, not routes) plus five case-study pages: `/spaceabet`, `/y-conference`,
`/firefighter-pfister`, `/travelcover`, `/generalitravelinsurance`.

Rebuild content and assets with:

```bash
python3 research/extract_live.py     # research/raw_html/*.html -> content/site.json
python3 research/download_assets.py  # needs Pillow
```

Neither re-fetches on its own — refresh `research/raw_html/` first:

```bash
for s in "" spaceabet y-conference firefighter-pfister travelcover \
         generalitravelinsurance; do
  curl -sL "https://www.designoutlaw.com/$s" -o "research/raw_html/${s:-home}.html"
done
```

Two things aren't in the rendered HTML and come from elsewhere:

- **Experience descriptions.** The live page ships only the first four rows
  collapsed, fetching the rest (and every description) through Figma's runtime.
  Those live in the scene graph, so `extract_live.py` merges them in from
  `research/raw/home.json` and records how many the live page shows collapsed.
- **Videos.** The process/demo clips on Spaceabet, Y Conference and Generali are
  uploaded Figma video assets, not served from the static `/_assets/v11/` path that
  images use — fetching them 404s. Angelo supplied the originals;
  `research/import_videos.py` wires them in (an `.mp4` source as-is; a `.mov`
  re-encoded with PyAV/libx264, since QuickTime's B-frame edit lists don't survive a
  packet-copy remux into plain MP4) and extracts a poster frame for each.

## Matching the live build

The rebuild is verified against the live site rather than eyeballed. Save the live
pages, point a local server at them, and compare rendered geometry at each of the
three breakpoints the live site uses (mobile <768, tablet 768–999, desktop ≥1000).
As of the last pass, section positions, type sizes, card dimensions and total page
height all match to within a few pixels at 375 / 768 / 1000 / 1440.

A few live-build quirks are reproduced deliberately rather than "corrected", and are
commented where they appear: the Work heading jumps to 96px from tablet up while its
siblings step 48 → 64 → 96; the About paragraph's closing lemon clause keeps its
desktop size at mobile; and the Y21 work card is pinned to a fixed height below
desktop, cropping its image, where every other card takes its image's own ratio.

## Design tokens

Tokens live at the top of `src/styles/base.css` — the palette (Kingfisher navy,
Desert Cream, Shallow Lagoon teal, Salmon, Zesty Lemon) plus the per-breakpoint
padding and gap scale.

An earlier pass generated these from the Figma variables, interpolating fluidly
between a mobile and a desktop anchor. That was the wrong model: the live site does
not interpolate — it renders three discrete breakpoints and switches between them at
768px and 1000px. The generator has been removed and the values written directly, so
the stylesheet says what the site actually does.

Figma Sites also sets no root font-size, which means its "unsized" text (nav links,
job rows, the See More button) renders at the browser default 16px. `base.css` keeps
that deliberately.

## Building

```bash
python3 build.py
```

Writes plain HTML/CSS/JS to `dist/`: one page per case study
(`dist/spaceabet/index.html`, etc.) plus `dist/index.html` for the home page — clean
URLs work natively this way (Apache serves a directory's `index.html` by default,
same as GitHub Pages did), no `.htaccess` rewrite needed.

Preview locally:

```bash
python3 build.py && python3 -m http.server -d dist 8000
```

## Deploying

```bash
git pull            # start of a session
./deploy.sh --live  # publish
git push            # save the change
```

Nothing enforces that order — the deploy reads `dist/`, not git — so it is possible
to publish something you never committed. Pushing after deploying keeps the repo
honest about what is live.

`deploy.sh` rsyncs `dist/` to designoutlaw.com's own web root over SSH. Unlike
firefighterpfister.com's version of this script, it never runs `--delete` — not
scoped, not at all. That root is shared with a bunch of things that were never
part of this repo, and it turned out that included `images/` specifically: a
first dry run here found 300+ unrelated files already in `public_html/images/`
(old aquarium and car-project photo galleries going back over a decade), sharing
a folder name this build also uses. Even `--delete` scoped to just that one
subtree would have erased all of it. So every sync is purely additive — files get
added or updated, nothing already on the server is ever removed by this script,
regardless of what name it shares with something this build also owns. The real
cost: a page or file permanently dropped from a future build leaves its old copy
on the server forever, since safely cleaning it up would require knowing every
remote name is safe to touch — which `images/` just proved isn't a safe
assumption here. Removing something needs a manual pass on the server when that
actually happens.

Dry run is the default — `./deploy.sh` alone lists every file it would add or change
without uploading anything.

### One-time setup

Same Bluehost account firefighterpfister.com uses, so if that repo is already set up
on this machine, `REMOTE_USER` and `REMOTE_HOST` are the same values — only
`REMOTE_PATH` differs (designoutlaw.com's own root, not an addon-domain
subdirectory). The SSH key can be shared too, or its own; either works.

```bash
cp .deploy.env.example .deploy.env
# fill in REMOTE_USER, REMOTE_HOST, REMOTE_PATH, SSH_PORT

ssh-keygen -t ed25519 -f ~/.ssh/designoutlaw_deploy -N "" -C "designoutlaw.com deploy"
pbcopy < ~/.ssh/designoutlaw_deploy.pub
```

Import that public key in cPanel → **SSH Access** → **Manage SSH Keys** → **Import
Key**, then **Manage → Authorize** it — importing alone does nothing. Confirm with:

```bash
ssh -i ~/.ssh/designoutlaw_deploy -p 22 youruser@your-bluehost-host
```

### Cutting over from GitHub Pages

DNS currently points `www.designoutlaw.com` at GitHub Pages, which is live and
working. To move back to Bluehost without an outage or an outright break:

1. `./deploy.sh --live` to publish to Bluehost while DNS still points elsewhere.
2. Check it through Bluehost's temporary URL or direct IP, not the domain — the
   things this whole move was about: `/transfer` and anything else outside this
   repo still resolve, alongside the site itself.
3. Only then repoint DNS at Bluehost, and remove the custom domain from GitHub
   Pages' settings so it stops trying to claim it.

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
