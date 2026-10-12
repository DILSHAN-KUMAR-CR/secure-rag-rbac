"use strict";

const TOKEN_KEY = "secure_rag_access_token";

function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, { ...options, headers });
  let payload = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) payload = await response.json();

  if (response.status === 401 && path !== "/auth/login") {
    clearToken();
    window.location.replace("/ui");
    throw new Error("Your session expired. Please sign in again.");
  }
  if (!response.ok) {
    const detail = payload && payload.detail;
    const message = typeof detail === "string" ? detail : "The request could not be completed.";
    throw new Error(message);
  }
  return payload;
}

function setMessage(element, message, kind = "info") {
  element.textContent = message;
  element.dataset.kind = kind;
}

function createElement(tag, text = "", className = "") {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

async function loadCurrentUser() {
  if (!getToken()) {
    window.location.replace("/ui");
    throw new Error("Authentication required.");
  }
  return apiFetch("/auth/me");
}

async function logoutCurrentSession() {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } finally {
    clearToken();
    window.location.replace("/ui");
  }
}
