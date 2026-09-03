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
  });

  // Arriving with a hash (from "Back to Work", say) should land on the
  // section, not part-way through a lazy-loading page.
  window.addEventListener("load", function () {
    var el = target(location.hash);
    if (el) window.scrollTo(0, offsetOf(el));
  });
})();
