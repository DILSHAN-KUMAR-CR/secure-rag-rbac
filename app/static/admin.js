"use strict";

const ROLES = ["Employee", "HR", "Admin"];

function actionButton(label, handler, className = "small-button") {
  const button = createElement("button", label, className);
  button.type = "button";
  button.addEventListener("click", handler);
  return button;
}

async function loadUsers() {
  const users = await apiFetch("/admin/users");
  const body = document.getElementById("users-body");
  body.replaceChildren();
  users.forEach((user) => {
    const row = document.createElement("tr");
    row.append(createElement("td", `${user.username} (#${user.id})`));

    const roleCell = document.createElement("td");
    const roleSelect = document.createElement("select");
    ROLES.forEach((role) => {
      const option = createElement("option", role);
      option.value = role;
      option.selected = user.role === role;
      roleSelect.append(option);
    });
    roleCell.append(roleSelect);
    row.append(roleCell);
    row.append(createElement("td", user.is_active ? "Active" : "Inactive", user.is_active ? "status-ok" : "status-off"));
    row.append(createElement("td", String(user.permission_version)));

    const actions = document.createElement("td");
    actions.className = "action-group";
    actions.append(
      actionButton("Save role", async () => {
        await runAdminAction(async () => {
          await apiFetch(`/admin/users/${user.id}/role`, { method: "PATCH", body: JSON.stringify({ role: roleSelect.value }) });
          await loadUsers();
          return `Updated ${user.username}'s role.`;
        });
      }),
      actionButton(user.is_active ? "Deactivate" : "Activate", async () => {
        await runAdminAction(async () => {
          await apiFetch(`/admin/users/${user.id}/status`, { method: "PATCH", body: JSON.stringify({ is_active: !user.is_active }) });
          await loadUsers();
          return `${user.username} is now ${user.is_active ? "inactive" : "active"}.`;
        });
      }),
      actionButton("Revoke sessions", async () => {
        await runAdminAction(async () => {
          const result = await apiFetch(`/admin/users/${user.id}/revoke-sessions`, { method: "POST" });
          return `${result.revoked_sessions} session(s) revoked for ${user.username}.`;
        });
      }),
    );
    row.append(actions);
    body.append(row);
  });
}

function roleCheckboxes(selectedRoles) {
  const wrapper = createElement("div", "", "checkbox-row");
  ROLES.forEach((role) => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = role;
    checkbox.checked = selectedRoles.includes(role);
    label.append(checkbox, document.createTextNode(role));
    wrapper.append(label);
  });
  return wrapper;
}

async function loadDocuments() {
  const documents = await apiFetch("/admin/documents");
  const body = document.getElementById("documents-body");
  body.replaceChildren();
  documents.forEach((documentRecord) => {
    const row = document.createElement("tr");
    row.append(createElement("td", `${documentRecord.title}\n${documentRecord.file_name}`, "pre-line"));
    row.append(createElement("td", documentRecord.status));
    row.append(createElement("td", String(documentRecord.chunk_count)));
    const rolesCell = document.createElement("td");
    const choices = roleCheckboxes(documentRecord.allowed_roles);
    rolesCell.append(choices);
    row.append(rolesCell);
    const actionCell = document.createElement("td");
    actionCell.append(actionButton("Update access", async () => {
      const allowedRoles = [...choices.querySelectorAll("input:checked")].map((item) => item.value);
      await runAdminAction(async () => {
        await apiFetch(`/admin/documents/${documentRecord.id}/permissions`, {
          method: "PATCH",
          body: JSON.stringify({ allowed_roles: allowedRoles }),
        });
        await loadDocuments();
        return `Updated access for ${documentRecord.title}.`;
      });
    }));
    row.append(actionCell);
    body.append(row);
  });
}

async function loadAuditLogs() {
  const params = new URLSearchParams();
  const action = document.getElementById("audit-action").value.trim();
  const decision = document.getElementById("audit-decision").value;
  const userId = document.getElementById("audit-user-id").value;
  if (action) params.set("action", action);
  if (decision) params.set("decision", decision);
  if (userId) params.set("user_id", userId);
  params.set("limit", "100");

  const logs = await apiFetch(`/admin/audit-logs?${params.toString()}`);
  const body = document.getElementById("audit-body");
  body.replaceChildren();
  logs.forEach((log) => {
    const row = document.createElement("tr");
    row.append(createElement("td", new Date(log.created_at).toLocaleString()));
    row.append(createElement("td", log.username ? `${log.username}\n${log.role || ""}` : "Unknown", "pre-line"));
    row.append(createElement("td", log.action));
    row.append(createElement("td", log.decision));
    row.append(createElement("td", log.retrieved_document_ids.length ? log.retrieved_document_ids.join(", ") : "—"));
    row.append(createElement("td", log.gemini_called ? "Yes" : "No"));
    row.append(createElement("td", log.response_status));
    row.append(createElement("td", log.duration_ms == null ? "—" : `${log.duration_ms} ms`));
    body.append(row);
  });
}

async function runAdminAction(action) {
  const message = document.getElementById("admin-message");
  setMessage(message, "Working…");
  try {
    const successMessage = await action();
    setMessage(message, successMessage, "success");
    await loadAuditLogs();
  } catch (error) {
    setMessage(message, error.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const user = await loadCurrentUser();
    if (user.role !== "Admin") {
      window.location.replace("/ui/chat");
      return;
    }
    document.getElementById("identity").textContent = `${user.username} · ${user.role}`;
    await Promise.all([loadUsers(), loadDocuments(), loadAuditLogs()]);
  } catch (error) {
    setMessage(document.getElementById("admin-message"), error.message, "error");
  }

  document.getElementById("logout-button").addEventListener("click", logoutCurrentSession);
  document.getElementById("create-user-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runAdminAction(async () => {
      const username = document.getElementById("new-username").value;
      await apiFetch("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          username,
          password: document.getElementById("new-password").value,
          role: document.getElementById("new-role").value,
        }),
      });
      event.target.reset();
      await loadUsers();
      return `Created user ${username}.`;
    });
  });

  document.getElementById("upload-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runAdminAction(async () => {
      const roles = [...document.querySelectorAll("input[name='upload-role']:checked")].map((item) => item.value);
      if (!roles.length) throw new Error("Select at least one allowed role.");
      const formData = new FormData();
      formData.set("title", document.getElementById("document-title").value);
      formData.set("allowed_roles", roles.join(","));
      formData.set("file", document.getElementById("document-file").files[0]);
      await apiFetch("/admin/documents", { method: "POST", body: formData });
      event.target.reset();
      await loadDocuments();
      return "Document uploaded and indexed.";
    });
  });

  document.getElementById("reindex-button").addEventListener("click", () => {
    runAdminAction(async () => {
      const result = await apiFetch("/admin/documents/reindex", { method: "POST" });
      return `Indexed ${result.indexed_documents} document(s) and ${result.indexed_chunks} chunk(s).`;
    });
  });
  document.getElementById("audit-filter-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runAdminAction(async () => {
      await loadAuditLogs();
      return "Audit filters applied.";
    });
  });
  document.getElementById("refresh-audit").addEventListener("click", () => loadAuditLogs());
});
