/*
 * Shared motion primitives.
 *
 * Durations and easings come from the interactions recorded in the Figma
 * Sites file (research/raw/home.json), so the ported site moves the way the
 * design specifies rather than at whatever the browser's defaults happen to
 * be:
 *
 *   anchor scroll   SCROLL_ANIMATE  300ms  EASE_OUT_CUBIC
 *   job row expand  SMART_ANIMATE   200ms  EASE_OUT_CUBIC
 *   See More        SMART_ANIMATE   383ms  GENTLE_SPRING
 *   mobile nav      SMART_ANIMATE   256ms  GENTLE_SPRING
 *
 * Figma's springs are simulations, not cubic-beziers; the approximations
 * below match their settle time and keep the slight overshoot-free glide of
 * a heavily damped spring.
 */
window.Motion = (function () {
  var EASE = {
    outCubic: "cubic-bezier(0, 0, 0.58, 1)",
    gentleSpring: "cubic-bezier(0.22, 0.61, 0.36, 1)",
  };

  var reduced = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)")
    : { matches: false };

  function canAnimate(el) {
    return !reduced.matches && typeof el.animate === "function";
  }

  /* Run a state change that resizes `el`, animating the height across it.
     `apply` makes the change; the height before and after is measured
     around it, so this works whether the growth comes from unhiding a
     child, revealing extra rows, or anything else. */
  function resize(el, apply, duration, easing) {
    if (!canAnimate(el)) { apply(); return; }
    var before = el.getBoundingClientRect().height;
    apply();
    var after = el.getBoundingClientRect().height;
    if (before === after) return;
    var anim = el.animate(
      [{ height: before + "px" }, { height: after + "px" }],
      { duration: duration, easing: easing, fill: "none" }
    );
    var prior = el.style.overflow;
    el.style.overflow = "hidden";
    anim.finished.then(restore, restore);
    function restore() { el.style.overflow = prior; }
  }

  /* Scroll the window to a y offset over a fixed duration. The native
     `scrollTo({behavior: "smooth"})` can't be timed, and its duration
     varies with distance, so the curve is driven here instead. */
  function scrollTo(y, duration, easing) {
    var start = window.pageYOffset;
    var delta = y - start;
    if (reduced.matches || !delta) {
      window.scrollTo(0, y);
      return;
    }
    var t0 = null;
    function step(now) {
      if (t0 === null) t0 = now;
      var p = Math.min(1, (now - t0) / duration);
      window.scrollTo(0, start + delta * easing(p));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  /* The cubic-bezier above, as a function, for the scroll driver. */
  function outCubic(t) { return 1 - Math.pow(1 - t, 3); }

  return {
    EASE: EASE,
    resize: resize,
    scrollTo: scrollTo,
    outCubic: outCubic,
    reduced: reduced,
  };
})();
