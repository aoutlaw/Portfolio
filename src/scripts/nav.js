/*
 * Mobile nav: the hamburger opens a panel pinned under the bar. Closes on
 * a link, on Escape, and on a click outside it.
 */
(function () {
  var button = document.getElementById("nav-toggle");
  var menu = document.getElementById("nav-menu");
  if (!button || !menu) return;

  function setOpen(open) {
    window.Motion.resize(menu, function () { menu.hidden = !open; },
                         256, window.Motion.EASE.gentleSpring);
    button.setAttribute("aria-expanded", String(open));
  }

  button.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(menu.hidden);
  });

  menu.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () { setOpen(false); });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !menu.hidden) setOpen(false);
  });

  document.addEventListener("click", function (e) {
    if (!menu.hidden && !menu.contains(e.target)) setOpen(false);
  });
})();
