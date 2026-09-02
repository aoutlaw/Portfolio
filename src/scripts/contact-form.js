/*
 * Contact form.
 *
 * Posts to a Google Apps Script web app, which appends a row to a Sheet
 * and emails the message (see design/apps-script/). The body goes as
 * URL-encoded form data on purpose: that's a "simple" request, so the
 * browser skips the CORS preflight, which Apps Script doesn't answer.
 *
 * The confirmation copy is the live site's, word for word — it used a
 * plain alert() and so does this, rather than inventing new wording.
 */
(function () {
  var form = document.querySelector(".form");
  if (!form) return;

  var submit = form.querySelector('button[type="submit"]');
  var endpoint = form.getAttribute("action");
  var label = submit.textContent;

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var name = form.querySelector("#name").value.trim();
    var email = form.querySelector("#email").value.trim();
    var message = form.querySelector("#message").value.trim();
    if (!name || !email || !message) {
      alert("Please fill in all fields");
      return;
    }

    submit.disabled = true;
    submit.textContent = "Sending...";

    fetch(endpoint, {
      method: "POST",
      body: new URLSearchParams(new FormData(form)),
    })
      .then(function (response) {
        return response.json().catch(function () {
          // A readable JSON body is a bonus, not a guarantee.
          return { ok: response.ok };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.error || "Send failed");
        alert("Success! I look forward to talking with you.");
        form.reset();
      })
      .catch(function () {
        alert(
          "Weird...there was an error submitting your message. Please try again."
        );
      })
      .finally(function () {
        submit.disabled = false;
        submit.textContent = label;
      });
  });
})();
