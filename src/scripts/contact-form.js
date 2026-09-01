// Submit the contact form to Formspree via fetch, so a successful send
// shows an inline status message instead of navigating away to
// Formspree's own thank-you page.
(function () {
  const form = document.querySelector(".contact-form");
  if (!form) return;
  const status = form.querySelector("[data-form-status]");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.hidden = false;
    status.textContent = "Sending…";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        status.textContent = "Thanks — I'll get back to you soon.";
        form.reset();
      } else {
        status.textContent = "Something went wrong. Please try again.";
      }
    } catch {
      status.textContent = "Something went wrong. Please try again.";
    }
  });
})();
