/*
 * In-page navigation. The live site animates the jump between sections
 * rather than snapping to them; Motion.scrollTo drives it over the 300ms
 * ease-out the Figma interaction specifies.
 */
(function () {
  var DURATION = 300;

  function target(hash) {
    if (!hash || hash === "#") return null;
    try { return document.querySelector(hash); } catch (e) { return null; }
  }

  function offsetOf(el) {
    return el.getBoundingClientRect().top + window.pageYOffset;
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="#"]');
    if (!a || a.target === "_blank") return;
    // Same-document links only: "/#work" from a case-study page is a real
    // navigation, and the hash is honoured on arrival instead.
    var path = a.getAttribute("href").split("#")[0];
    if (path && path !== location.pathname) return;
    var el = target("#" + a.getAttribute("href").split("#")[1]);
    if (!el) return;
    e.preventDefault();
    window.Motion.scrollTo(offsetOf(el), DURATION, window.Motion.outCubic);
    history.pushState(null, "", "#" + el.id);
    // preventDefault above cancels the browser's own fragment navigation,
    // and with it the focus move that normally comes with it -- so tabbing
    // after following one of these carried on from the nav rather than from
    // the section just jumped to, and the skip link skipped nothing. Move
    // focus by hand instead. preventScroll keeps it from fighting the
    // animation already underway.
    if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
    el.focus({ preventScroll: true });
  });

  // Arriving with a hash (from "Back to Work", say) should land on the
  // section, not part-way through a lazy-loading page.
  window.addEventListener("load", function () {
    var el = target(location.hash);
    if (el) window.scrollTo(0, offsetOf(el));
  });
})();
