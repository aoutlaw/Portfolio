/*
 * Harvest the live gallery geometry into research/raw_geometry/<slug>.json.
 *
 * Figma Sites ships one server-rendered subtree per breakpoint, and the
 * gallery's whole character lives in values that change between them:
 * the row's flex-direction and gap, each cell's fixed pixel height, and
 * the aspect box's ratio. Parsing that back out of the `ssr-css` block is
 * brittle (the same class names recur across breakpoints), so this reads
 * the values the browser actually resolves, at each breakpoint, from a
 * local mirror of the live pages.
 *
 * Usage (mirror served on :8898, see research/mirror_live.py):
 *   node research/harvest_geometry.js
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const SLUGS = ['spaceabet', 'y-conference', 'firefighter-pfister',
               'travelcover', 'generalitravelinsurance'];
// Each breakpoint is measured twice, at its narrow edge and wider inside
// it. That second sample is what tells a cell with a fixed pixel height
// from one that simply follows its image, and a box with a fixed width
// from one that fills its cell -- the two look identical at a single
// viewport but behave differently everywhere else.
const WIDTHS = {
  mobile: 375, mobileWide: 500,
  tablet: 768, tabletWide: 900,
  desktop: 1000, desktopWide: 1440,
};
const OUT = path.join(__dirname, 'raw_geometry');

// Walk every gallery image/video, and for each report the cell it sits in
// (fixed height + clip) and the aspect box inside it, plus the row that
// groups the cells. Rows are identified by the cell's parent element, so
// the grouping survives the column/row switch at the mobile breakpoint.
const PROBE = `(() => {
  // Gallery rows are the flex containers capped at the 1280px content
  // width whose children are all clipped fixed-height cells. Walking the
  // rows (rather than the images) keeps the video cells, which hold no
  // <img> because Figma's client runtime mounts those after hydration.
  const isCell = el => {
    const s = getComputedStyle(el);
    return s.overflow === 'clip' && /^[0-9.]+px$/.test(s.height);
  };
  const rows = [];
  document.querySelectorAll('div').forEach(row => {
    // Figma Sites ships every breakpoint's subtree; only one is laid out.
    if (!row.getClientRects().length) return;
    const s = getComputedStyle(row);
    if (s.display !== 'flex' || s.maxWidth !== '1280px') return;
    const kids = Array.from(row.children);
    if (!kids.length || !kids.every(isCell)) return;
    // A gallery row can be introduced by a heading ("Before",
    // "Wireframes", "After" on Travel Cover), which sits as the row's
    // immediate previous sibling.
    const prev = row.previousElementSibling;
    const label = prev && !prev.querySelector('img,video')
      ? prev.textContent.trim() : '';
    rows.push({
      label: label,
      direction: s.flexDirection,
      gap: s.columnGap,
      align: s.alignItems,
      items: kids.map(cell => {
        const cs = getComputedStyle(cell);
        const box = cell.firstElementChild;
        const bs = box ? getComputedStyle(box) : cs;
        const img = cell.querySelector('img');
        const cr = cell.getBoundingClientRect();
        const br = box ? box.getBoundingClientRect() : cr;
        // Figma bakes an image's crop into the <img> itself: it is sized
        // and offset relative to its box rather than filling it, and the
        // cell clips whatever hangs out. Recorded relative to the box so
        // it can be replayed as percentages.
        const mr = (img || cell.querySelector('video') || box || cell).getBoundingClientRect();
        return {
          type: img ? 'image' : 'video',
          src: img ? (img.getAttribute('src') || '').split('?')[0] : null,
          alt: img ? img.getAttribute('alt') : null,
          height: cs.height,
          flex: cs.flex,
          // How the cell places the box inside itself -- which is what
          // decides whether an overflowing shot is cropped evenly top and
          // bottom or hangs off one edge.
          cellDirection: cs.flexDirection,
          cellAlign: cs.alignItems,
          cellJustify: cs.justifyContent,
          aspect: bs.aspectRatio,
          // Whether the box spans the cell's width (and so overflows and
          // gets cropped) or its height (and so sits inside it) is the
          // difference between a cropped shot and a contained one; it is
          // read back from the measured boxes rather than guessed.
          cellBox: [cr.width, cr.height],
          shotBox: [br.width, br.height],
          mediaBox: [mr.width, mr.height],
          mediaAt: [mr.x - br.x, mr.y - br.y],
        };
      }),
    });
  });
  return rows;
})()`;

const padOf = `const padOf = el => {
    let pad = null, up = el.parentElement;
    for (let i = 0; i < 3 && up && !pad; i++) {
      const s = getComputedStyle(up);
      if (s.padding !== '0px') pad = s.padding;
      up = up.parentElement;
    }
    return pad;
  };`;

// The cream body block (the Challenge/Solution/Results sections) and the
// gallery block below it. Their padding and gap are set per page as well as
// per breakpoint, same as the header's.
const BLOCK_PROBE = `(() => {
  ${padOf}
  const isCell = el => { const s = getComputedStyle(el);
    return s.overflow === 'clip' && /^[0-9.]+px$/.test(s.height); };
  const blocks = Array.from(document.querySelectorAll('div')).filter(el => {
    if (!el.getClientRects().length) return false;
    return getComputedStyle(el).maxWidth === '1280px';
  });
  const isRow = el => {
    const kids = Array.from(el.children);
    return getComputedStyle(el).display === 'flex' && kids.length && kids.every(isCell);
  };
  const body = blocks.find(el => !isRow(el) && el.querySelector('p')
    && !el.querySelector('img,video') && el.getBoundingClientRect().y > 300);
  const rows = blocks.filter(isRow);
  const gallery = rows.length ? rows[0].parentElement : null;
  const info = el => el ? { padding: padOf(el), gap: getComputedStyle(el).rowGap,
                            y: Math.round(el.getBoundingClientRect().y) } : null;
  return { body: info(body), gallery: gallery ? {
    padding: padOf(rows[0]), gap: getComputedStyle(gallery).rowGap,
    y: Math.round(gallery.getBoundingClientRect().y) } : null };
})()`;

// The home page's work cards. Each is a box at a fixed ratio with the
// image either covering it or -- where Figma cropped a tall source --
// scaled past it and nudged. Both the ratio and the crop change per
// breakpoint, so they are measured the same way the gallery is.
const CARD_PROBE = `(() => {
  const out = [];
  document.querySelectorAll('img').forEach(img => {
    const src = (img.getAttribute('src') || '').split('?')[0];
    if (src.endsWith('.svg') || !img.getClientRects().length) return;
    // Work-card images are the ones inside a link; the About photo isn't.
    let link = img.parentElement;
    while (link && !(link.tagName === 'A' || link.getAttribute('role') === 'link'))
      link = link.parentElement;
    if (!link) return;
    // The link itself is the card -- it is the box that clips -- except
    // where one anchor wraps a whole row of cards, in which case the card
    // is the outermost ratio box under it.
    const photos = Array.from(link.querySelectorAll('img'))
      .filter(i => !(i.getAttribute('src') || '').endsWith('.svg'));
    let box = link;
    if (photos.length > 1) {
      box = img;
      let el = img;
      while (el && el !== link) {
        if (getComputedStyle(el).aspectRatio.includes('/')) box = el;
        el = el.parentElement;
      }
    }
    const r = box.getBoundingClientRect(), ir = img.getBoundingClientRect();
    out.push({
      src: src,
      aspect: getComputedStyle(box).aspectRatio,
      card: [r.width, r.height],
      media: [ir.width, ir.height],
      at: [ir.x - r.x, ir.y - r.y],
      fit: getComputedStyle(img).objectFit,
    });
  });
  return out;
})()`;

const HEAD_PROBE = `(() => {
  // The navy header block: back link, heading + intro, CTA. Its gap is set
  // per page as well as per breakpoint (the tablet value is 32px on some
  // case studies and 64px on others), so it has to be measured rather than
  // written into the stylesheet once.
  const inner = Array.from(document.querySelectorAll('div')).find(el => {
    if (!el.getClientRects().length) return false;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.maxWidth === '1280px' && s.flexDirection === 'column'
        && r.y < 400 && r.height > 200;
  });
  if (!inner) return null;
  const intro = Array.from(inner.children).find(c =>
    c.querySelectorAll('p').length >= 1 && !c.querySelector('img')
    && getComputedStyle(c).display === 'flex');
  // The padding sits on a wrapper outside the 1280px box, and one case
  // study carries a different one at desktop.
  let pad = null, el = inner.parentElement;
  for (let i = 0; i < 3 && el && !pad; i++) {
    const s = getComputedStyle(el);
    if (s.padding !== '0px') pad = s.padding;
    el = el.parentElement;
  }
  return {
    gap: getComputedStyle(inner).rowGap,
    introGap: intro ? getComputedStyle(intro).rowGap : null,
    padding: pad,
  };
})()`;

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  for (const slug of SLUGS) {
    const out = {};
    for (const [name, width] of Object.entries(WIDTHS)) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      // The mirror still carries the live analytics tags; they can't be
      // reached from here, so drop anything off-localhost rather than
      // waiting on it.
      await page.route('**/*', route =>
        route.request().url().startsWith('http://localhost:') ? route.continue() : route.abort());
      await page.goto(`http://localhost:8898/${slug}.html`, { waitUntil: 'load' });
      // Lazy images never enter the viewport during a scripted visit, so
      // force them eager and sweep the page before measuring.
      await page.evaluate(async () => {
        document.querySelectorAll('img[loading=lazy]').forEach(i => (i.loading = 'eager'));
        await new Promise(done => {
          let y = 0;
          const step = () => {
            y += 600; scrollTo(0, y);
            y < document.body.scrollHeight ? setTimeout(step, 25)
                                           : (scrollTo(0, 0), setTimeout(done, 500));
          };
          step();
        });
      });
      out[name] = { rows: await page.evaluate(PROBE),
                    head: await page.evaluate(HEAD_PROBE),
                    blocks: await page.evaluate(BLOCK_PROBE) };
      await page.close();
    }
    fs.writeFileSync(path.join(OUT, `${slug}.json`), JSON.stringify(out, null, 2) + '\n');
    const n = Object.entries(out).map(([k, v]) =>
      `${k} ${v.rows.length} rows/${v.rows.reduce((a, r) => a + r.items.length, 0)} items`);
    console.log(`  ${slug}: ${n.join(', ')}`);
  }
  // The home page: work cards only.
  const home = {};
  for (const [name, width] of Object.entries(WIDTHS)) {
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    await page.route('**/*', route =>
      route.request().url().startsWith('http://localhost:') ? route.continue() : route.abort());
    await page.goto('http://localhost:8898/index.html', { waitUntil: 'load' });
    await page.evaluate(async () => {
      document.querySelectorAll('img[loading=lazy]').forEach(i => (i.loading = 'eager'));
      await new Promise(done => {
        let y = 0;
        const step = () => {
          y += 600; scrollTo(0, y);
          y < document.body.scrollHeight ? setTimeout(step, 25)
                                         : (scrollTo(0, 0), setTimeout(done, 500));
        };
        step();
      });
    });
    home[name] = { cards: await page.evaluate(CARD_PROBE) };
    await page.close();
  }
  fs.writeFileSync(path.join(OUT, 'home.json'), JSON.stringify(home, null, 2) + '\n');
  console.log(`  home: ${Object.entries(home).map(([k, v]) => `${k} ${v.cards.length} cards`).join(', ')}`);

  await browser.close();
})();
