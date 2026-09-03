/*
 * Experience list.
 *
 * Two independent interactions, both matching the live site:
 *   - "See More Experience" reveals rows 5-10 and flips its own label.
 *   - Each row expands to show its description, chevron rotating down.
 *
 * The live site ships only the first four rows and no descriptions at all,
 * fetching the rest through Figma's runtime. Here every row is in the HTML
 * and CSS hides the extras, so the page works without JavaScript and the
 * copy stays indexable.
 *
 * Both expansions are timed rather than instant, at the durations the Figma
 * interactions record (see src/scripts/motion.js).
 */
(function () {
  var list = document.getElementById("experience-list");
  var toggle = document.getElementById("experience-toggle");

  if (list && toggle) {
    var more = toggle.querySelector("[data-label-more]");
    var less = toggle.querySelector("[data-label-less]");
    toggle.addEventListener("click", function () {
      var open = list.hasAttribute("data-expanded");
      window.Motion.resize(list, function () {
        if (open) {
          list.removeAttribute("data-expanded");
        } else {
          list.setAttribute("data-expanded", "");
        }
      }, 383, window.Motion.EASE.gentleSpring);
      toggle.setAttribute("aria-expanded", String(!open));
      more.hidden = !open;
      less.hidden = open;
      toggle.classList.toggle("textbutton--up", !open);
    });
  }

  document.querySelectorAll(".job__head").forEach(function (head) {
    head.addEventListener("click", function () {
      var job = head.closest(".job");
      var body = job.querySelector(".job__body");
      var open = job.hasAttribute("data-open");
      window.Motion.resize(job, function () {
        if (open) {
          job.removeAttribute("data-open");
        } else {
          job.setAttribute("data-open", "");
        }
        body.hidden = open;
      }, 200, window.Motion.EASE.outCubic);
      head.setAttribute("aria-expanded", String(!open));
    });
  });
})();
