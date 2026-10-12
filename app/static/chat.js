"use strict";

function renderCitations(citations) {
  const list = document.getElementById("citations");
  list.replaceChildren();
  if (!citations.length) {
    list.append(createElement("li", "No permitted source was returned.", "muted"));
    return;
  }
  citations.forEach((citation) => {
    const page = citation.page_number ? `, page ${citation.page_number}` : "";
    list.append(createElement("li", `${citation.document_title}${page}`));
  });
}

function showResult(payload, preview) {
  document.getElementById("result-card").classList.remove("hidden");
  document.getElementById("result-role").textContent = payload.user_role;
  document.getElementById("result-status").textContent =
    payload.status === "no_accessible_source" ? "No accessible source" : (preview ? "Safe context ready" : "Grounded answer");

  const answer = document.getElementById("answer");
  const contextBlock = document.getElementById("context-block");
  if (preview) {
    answer.textContent = payload.status === "ready"
      ? "The following permitted excerpts are eligible to be sent to the model."
      : "No document excerpt available to your current role matched this question.";
    document.getElementById("context-text").textContent = payload.context || "No context was prepared.";
    contextBlock.classList.remove("hidden");
    document.getElementById("timings").textContent = "Gemini was not called for this preview.";
  } else {
    answer.textContent = payload.answer;
    contextBlock.classList.add("hidden");
    const timing = payload.timings_ms;
    document.getElementById("timings").textContent =
      `Context preparation: ${timing.context_preparation} ms · Gemini generation: ${timing.gemini_generation} ms`;
  }
  renderCitations(payload.citations || []);
}

async function submitQuestion(preview) {
  const message = document.getElementById("query-message");
  const query = document.getElementById("question").value.trim();
  if (!query) {
    setMessage(message, "Enter a question first.", "error");
    return;
  }
  setMessage(message, preview ? "Preparing authorized context…" : "Retrieving permitted sources and generating an answer…");
  document.getElementById("ask-button").disabled = true;
  document.getElementById("preview-button").disabled = true;
  try {
    const payload = await apiFetch(preview ? "/rag/context-preview" : "/rag/ask", {
      method: "POST",
      body: JSON.stringify({ query, top_k: Number(document.getElementById("top-k").value) }),
    });
    showResult(payload, preview);
    setMessage(message, "Request completed.", "success");
  } catch (error) {
    setMessage(message, error.message, "error");
  } finally {
    document.getElementById("ask-button").disabled = false;
    document.getElementById("preview-button").disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const user = await loadCurrentUser();
    document.getElementById("identity").textContent = `${user.username} · ${user.role}`;
    if (user.role === "Admin") document.getElementById("admin-link").classList.remove("hidden");
  } catch (_error) {
    return;
  }

  document.getElementById("logout-button").addEventListener("click", logoutCurrentSession);
  document.getElementById("question-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitQuestion(false);
  });
  document.getElementById("preview-button").addEventListener("click", () => submitQuestion(true));
});
