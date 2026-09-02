/*
 * Contact form.
 *
 * Posts to a Google Apps Script web app, which appends a row to a Sheet and
 * emails the message (see design/apps-script/). The body is sent as
 * URL-encoded form data on purpose: that's a "simple" request, so the
 * browser skips the CORS preflight, which Apps Script does not answer.
 * Sending JSON here would trigger an OPTIONS request and fail.
 *
 * The form works without this script — it's a real <form> with a real
 * action, so submitting it unenhanced posts normally. This only upgrades
 * the experience to stay on the page.
 */
(function () {
  var form = document.querySelector(".contact-form");
  if (!form) return;

  var status = form.querySelector("[data-form-status]");
  var submit = form.querySelector('button[type="submit"]');
  var endpoint = form.getAttribute("action");
  var configured = endpoint && endpoint.indexOf("PASTE_YOUR") === -1;

  form.addEventListener("submit", function (event) {
    // Always intercept. Without a real endpoint the browser would
    // otherwise navigate to the placeholder and lose whatever was typed.
    event.preventDefault();
    status.hidden = false;

    if (!configured) {
      status.textContent =
        "The form isn't connected yet — email angelo.outlaw@gmail.com directly.";
      return;
    }

    submit.disabled = true;
    status.textContent = "Sending…";

    fetch(endpoint, {
      method: "POST",
      body: new URLSearchParams(new FormData(form)),
    })
      .then(function (response) {
        return response.json().catch(function () {
          // A readable JSON body is a bonus, not a guarantee; a 2xx is
          // enough to treat as success either way.
          return { ok: response.ok };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.error || "Send failed");
        status.textContent = "Thanks — I'll get back to you soon.";
        form.reset();
      })
      .catch(function (err) {
        status.textContent =
          (err && err.message) || "Something went wrong. Please try again.";
      })
      .finally(function () {
        submit.disabled = false;
      });
  });
})();
