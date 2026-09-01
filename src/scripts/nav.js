// Mobile nav drawer: toggle open/closed, close on link click or Escape.
(function () {
  const button = document.getElementById("nav-hamburger");
  const drawer = document.getElementById("mobile-drawer");
  if (!button || !drawer) return;

  function setOpen(open) {
    drawer.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    document.body.style.overflow = open ? "hidden" : "";
  }

  button.addEventListener("click", () => setOpen(drawer.hidden));
  drawer.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => setOpen(false))
  );
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !drawer.hidden) setOpen(false);
  });
})();
