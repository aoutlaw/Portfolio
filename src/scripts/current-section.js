/*
 * Marks the nav link for the section currently in view, so the kingfisher
 * rule under it tracks the page as you scroll.
 *
 * Home page only in practice: a case-study page's nav links point at
 * "/#work" and friends, which aren't on that page, so every link filters
 * out and this does nothing. Both copies of each link are marked -- the
 * desktop bar and the mobile panel render the same set.
 */
(function () {
  var groups = {};
  var order = [];

  document.querySelectorAll('.nav__link[href*="#"]').forEach(function (a) {
    var href = a.getAttribute("href");
    var path = href.split("#")[0];
    // A link to another document is a real navigation, not a section here.
    if (path && path !== location.pathname) return;
    var id = href.split("#")[1];
    var section = id && document.getElementById(id);
    if (!section) return;
    if (!groups[id]) {
      groups[id] = { section: section, links: [] };
      order.push(id);
    }
    groups[id].links.push(a);
  });
  if (!order.length) return;

  order.sort(function (a, b) {
    return groups[a].section.offsetTop - groups[b].section.offsetTop;
  });

  var current = null;
  var queued = false;

  function apply(id) {
    if (id === current) return;
    if (current) {
      groups[current].links.forEach(function (a) { a.removeAttribute("aria-current"); });
    }
    current = id;
    if (current) {
      groups[current].links.forEach(function (a) { a.setAttribute("aria-current", "true"); });
    }
  }

  function update() {
    queued = false;
    // Whichever section has crossed a line a third of the way down the
    // viewport is the one being read. Above the first one -- the hero --
    // nothing is current, which is why this can clear back to null.
    var line = window.innerHeight / 3;
    var found = null;
    for (var i = 0; i < order.length; i++) {
      if (groups[order[i]].section.getBoundingClientRect().top <= line) found = order[i];
    }
    // At the very bottom the last section may never cross the line -- if the
    // page can't scroll any further, it's the one you're looking at.
    if (window.innerHeight + window.pageYOffset >= document.documentElement.scrollHeight - 2) {
      found = order[order.length - 1];
    }
    apply(found);
  }

  function onScroll() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(update);
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  // Rows 5-10 appearing changes every offset below them.
  document.addEventListener("click", onScroll);
  update();
})();
