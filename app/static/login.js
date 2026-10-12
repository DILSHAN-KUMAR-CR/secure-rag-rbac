"use strict";

document.addEventListener("DOMContentLoaded", () => {
  if (getToken()) window.location.replace("/ui/chat");

  const form = document.getElementById("login-form");
  const message = document.getElementById("login-message");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setMessage(message, "Signing in…");
    const submit = form.querySelector("button[type='submit']");
    submit.disabled = true;
    try {
      const payload = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      setToken(payload.access_token);
      window.location.replace("/ui/chat");
    } catch (error) {
      setMessage(message, error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });
});
