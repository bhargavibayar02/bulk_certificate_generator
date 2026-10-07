const MAX_RECIPIENTS = 500;
const POLL_INTERVAL_MS = 1400;
const ACTIVE_STATUSES = new Set(["queued", "processing"]);
const $ = (selector) => document.querySelector(selector);

const elements = {
  eventName: $("#event-name"),
  eventDate: $("#event-date"),
  recipientList: $("#recipient-list"),
  recipientCount: $("#recipient-count"),
  logoFiles: $("#logo-files"),
  logoSummary: $("#logo-summary"),
  borderStyle: $("#border-style"),
  borderColor: $("#border-color"),
  borderWidth: $("#border-width"),
  formMessage: $("#form-message"),
  createButton: $("#create-job"),
};

let nextRecipientId = 0;
let currentJobId = null;
let pollTimer = null;
let requestInProgress = false;

function addRecipient(name = "", email = "") {
  if (elements.recipientList.children.length >= MAX_RECIPIENTS) {
    showMessage(`A batch can contain up to ${MAX_RECIPIENTS} recipients.`, "error");
    return;
  }
  const row = document.createElement("div");
  row.className = "recipient-row";
  row.dataset.recipientId = String(nextRecipientId++);

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.maxLength = 150;
  nameInput.placeholder = "e.g. Alex Morgan";
  nameInput.setAttribute("aria-label", "Recipient full name");
  nameInput.value = name;
  nameInput.addEventListener("input", updatePreviewRecipient);

  const emailInput = document.createElement("input");
  emailInput.type = "email";
  emailInput.maxLength = 254;
  emailInput.placeholder = "alex@example.com";
  emailInput.setAttribute("aria-label", "Recipient email address");
  emailInput.value = email;

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "remove-recipient";
  removeButton.setAttribute("aria-label", "Remove recipient");
  removeButton.textContent = "×";
  removeButton.addEventListener("click", () => {
    row.remove();
    updateRecipientCount();
    updatePreviewRecipient();
  });

  row.append(nameInput, emailInput, removeButton);
  elements.recipientList.append(row);
  updateRecipientCount();
}

function updateRecipientCount() {
  elements.recipientCount.textContent = String(elements.recipientList.children.length);
}

function updatePreviewRecipient() {
  const firstName = elements.recipientList.querySelector(".recipient-row input")?.value.trim();
  $("#preview-recipient").textContent = firstName || "Your recipient";
}

function readRecipients() {
  return Array.from(elements.recipientList.querySelectorAll(".recipient-row"), (row) => {
    const [nameInput, emailInput] = row.querySelectorAll("input");
    return { name: nameInput.value.trim(), email: emailInput.value.trim() };
  });
}

function showMessage(message, type) {
  elements.formMessage.textContent = message;
  elements.formMessage.className = `form-message visible ${type}`;
}

function getErrorMessage(payload) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((error) => {
      const location = Array.isArray(error.loc) ? error.loc.slice(1).join(" → ") : "";
      return `${location ? `${location}: ` : ""}${error.msg || "Invalid value"}`;
    }).join(" · ");
  }
  return "The request could not be completed. Please check your details and try again.";
}

function getLogoFiles() {
  return Array.from(elements.logoFiles.files || []);
}

function validateForm(recipients, logos) {
  if (!elements.eventName.value.trim()) return "Add an event name before creating certificates.";
  if (!elements.eventDate.value) return "Choose the date your event took place.";
  if (!recipients.length) return "Add at least one recipient to your batch.";
  if (recipients.length > MAX_RECIPIENTS) return `A batch can contain up to ${MAX_RECIPIENTS} recipients.`;
  const invalidIndex = recipients.findIndex((recipient) => {
    return !recipient.name || recipient.name.length > 150 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient.email);
  });
  if (invalidIndex !== -1) return `Check the name and email address in recipient ${invalidIndex + 1}.`;
  if (logos.length > 10) return "You can add up to 10 logos.";
  const invalidLogo = logos.find((file) => {
    const extension = file.name.split(".").pop().toLowerCase();
    return !["png", "jpg", "jpeg"].includes(extension) || file.size > 2 * 1024 * 1024;
  });
  if (invalidLogo) return `${invalidLogo.name} must be a PNG or JPG image no larger than 2 MB.`;
  return "";
}

async function createJob() {
  if (requestInProgress) return;
  const recipients = readRecipients();
  const logos = getLogoFiles();
  const error = validateForm(recipients, logos);
  if (error) {
    showMessage(error, "error");
    return;
  }

  requestInProgress = true;
  elements.createButton.disabled = true;
  elements.createButton.querySelector("span:first-child").textContent = "Creating your batch…";
  elements.formMessage.className = "form-message";

  const form = new FormData();
  form.append("event_name", elements.eventName.value.trim());
  form.append("event_date", elements.eventDate.value);
  form.append("recipients", JSON.stringify(recipients));
  form.append("border_style", elements.borderStyle.value);
  form.append("border_color", elements.borderColor.value.toUpperCase());
  form.append("border_width", elements.borderWidth.value);
  for (const logo of logos) form.append("logos", logo);

  try {
    const response = await fetch("/api/jobs/upload", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(getErrorMessage(payload));
    await trackJob(payload.job_id);
    showMessage(`Batch #${payload.job_id} accepted. Your certificates are being generated.`, "success");
    $("#progress").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "Could not create the batch. Please try again.", "error");
  } finally {
    requestInProgress = false;
    elements.createButton.disabled = false;
    elements.createButton.querySelector("span:first-child").textContent = "Create certificates";
  }
}

function setJobSummary(summary) {
  $("#job-title").textContent = summary.event_name || `Batch #${summary.job_id}`;
  const status = $("#job-status");
  status.textContent = summary.status.replaceAll("_", " ");
  status.className = `status-chip ${summary.status}`;
  const percentage = Math.max(0, Math.min(100, Number(summary.progress_percentage) || 0));
  $("#progress-fill").style.width = `${percentage}%`;
  $("#progress-percent").textContent = `${Math.round(percentage)}%`;
  $("#progress-label").textContent = `${summary.success_count + summary.failure_count} of ${summary.total_count} processed`;
  $("#stat-total").textContent = String(summary.total_count);
  $("#stat-success").textContent = String(summary.success_count);
  $("#stat-failed").textContent = String(summary.failure_count);
  $("#job-id-value").textContent = String(summary.job_id);
  $("#job-id-line").hidden = false;
  $("#job-restore").hidden = true;
  $("#empty-progress").hidden = true;
}

function renderCertificates(certificates) {
  const list = $("#certificate-list");
  list.replaceChildren();
  $("#certificates-panel").hidden = false;
  $("#certificates-summary").textContent = `${certificates.length} recipient${certificates.length === 1 ? "" : "s"}`;
  for (const certificate of certificates) {
    const entry = document.createElement("div");
    entry.className = "certificate-entry";
    const badge = document.createElement("span");
    badge.className = "file-badge";
    badge.textContent = "PDF";
    const info = document.createElement("div");
    info.className = "recipient-info";
    const name = document.createElement("strong");
    name.textContent = certificate.recipient_name;
    const email = document.createElement("span");
    email.textContent = certificate.recipient_email;
    info.append(name, email);
    if (certificate.status === "completed") {
      const download = document.createElement("a");
      download.href = `/api/certificates/${encodeURIComponent(certificate.id)}`;
      download.textContent = "Download";
      download.setAttribute("aria-label", `Download ${certificate.recipient_name}'s certificate`);
      entry.append(badge, info, download);
    } else {
      const status = document.createElement("span");
      status.className = `entry-status ${certificate.status}`;
      status.textContent = certificate.status === "failed" ? "Failed" : certificate.status;
      if (certificate.error_message) status.title = certificate.error_message;
      entry.append(badge, info, status);
    }
    list.append(entry);
  }
}

async function refreshJob(jobId) {
  const [statusResponse, certificatesResponse] = await Promise.all([
    fetch(`/api/jobs/${encodeURIComponent(jobId)}`),
    fetch(`/api/jobs/${encodeURIComponent(jobId)}/certificates`),
  ]);
  const statusData = await statusResponse.json();
  if (!statusResponse.ok) throw new Error(getErrorMessage(statusData));
  const certificatesData = await certificatesResponse.json();
  if (!certificatesResponse.ok) throw new Error(getErrorMessage(certificatesData));
  setJobSummary(statusData);
  renderCertificates(certificatesData);
  return statusData.status;
}

async function pollJob(jobId) {
  if (currentJobId !== jobId || pollTimer) return;
  try {
    const status = await refreshJob(jobId);
    if (ACTIVE_STATUSES.has(status)) {
      pollTimer = window.setTimeout(() => {
        pollTimer = null;
        void pollJob(jobId);
      }, POLL_INTERVAL_MS);
    }
  } catch (error) {
    $("#job-status").textContent = "Unable to refresh";
    $("#job-status").className = "status-chip failed";
    showMessage(error instanceof Error ? error.message : "Unable to retrieve batch status.", "error");
  }
}

async function trackJob(jobId) {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
  currentJobId = Number(jobId);
  if (!Number.isInteger(currentJobId) || currentJobId < 1) {
    throw new Error("Enter a valid positive batch ID.");
  }
  await pollJob(currentJobId);
  $("#progress").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"' && quoted && text[index + 1] === '"') {
      value += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === "," && !quoted) {
      row.push(value.trim());
      value = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(value.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      value = "";
    } else {
      value += character;
    }
  }
  if (quoted) throw new Error("This CSV has an unclosed quoted field.");
  row.push(value.trim());
  if (row.some(Boolean)) rows.push(row);
  if (!rows.length) throw new Error("The selected CSV file is empty.");
  const header = rows[0].map((column) => column.toLowerCase());
  const nameIndex = header.indexOf("name");
  const emailIndex = header.indexOf("email");
  const dataRows = nameIndex >= 0 && emailIndex >= 0 ? rows.slice(1) : rows;
  const indices = nameIndex >= 0 && emailIndex >= 0 ? [nameIndex, emailIndex] : [0, 1];
  return dataRows.map((columns) => ({
    name: columns[indices[0]] || "",
    email: columns[indices[1]] || "",
  })).filter((recipient) => recipient.name || recipient.email);
}

async function importCsv(file) {
  try {
    const recipients = parseCsv(await file.text());
    if (!recipients.length) throw new Error("No recipient rows were found in this CSV.");
    if (recipients.length + elements.recipientList.children.length > MAX_RECIPIENTS) {
      throw new Error(`This import would exceed the ${MAX_RECIPIENTS}-recipient batch limit.`);
    }
    for (const recipient of recipients) addRecipient(recipient.name, recipient.email);
    showMessage(`${recipients.length} recipient${recipients.length === 1 ? "" : "s"} imported from ${file.name}.`, "success");
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "Unable to read this CSV file.", "error");
  } finally {
    $("#csv-file").value = "";
  }
}

$("#add-recipient").addEventListener("click", () => addRecipient());
elements.createButton.addEventListener("click", () => void createJob());
$("#csv-file").addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) void importCsv(file);
});
$("#restore-job").addEventListener("click", () => {
  void trackJob($("#job-id-input").value).catch((error) => {
    showMessage(error instanceof Error ? error.message : "Unable to track this batch.", "error");
  });
});
$("#job-id-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") $("#restore-job").click();
});
$("#copy-job-id").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("#job-id-value").textContent);
    $("#copy-job-id").textContent = "Copied";
    window.setTimeout(() => { $("#copy-job-id").textContent = "Copy ID"; }, 1200);
  } catch {
    showMessage("Could not copy the ID. Select it and copy manually.", "error");
  }
});
elements.eventName.addEventListener("input", () => {
  $("#preview-event").textContent = elements.eventName.value.trim() || "Your event name";
});
elements.eventDate.addEventListener("input", () => {
  const date = elements.eventDate.value;
  $("#preview-date").textContent = date
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`)).toUpperCase()
    : "EVENT DATE";
});
elements.borderColor.addEventListener("input", () => {
  $("#border-color-text").textContent = elements.borderColor.value.toUpperCase();
  $(".certificate-frame").style.borderColor = elements.borderColor.value;
});
elements.borderStyle.addEventListener("change", () => {
  const frame = $(".certificate-frame");
  frame.style.borderStyle = elements.borderStyle.value === "none"
    ? "hidden"
    : elements.borderStyle.value === "double" ? "double" : "solid";
  frame.style.borderWidth = elements.borderStyle.value === "thick" ? "5px" : "3px";
});
elements.borderWidth.addEventListener("input", () => {
  $("#border-width-value").textContent = `${elements.borderWidth.value} pt`;
  $(".certificate-frame").style.borderWidth = `${Math.max(1, Number(elements.borderWidth.value))}px`;
});
elements.logoFiles.addEventListener("change", () => {
  const logos = getLogoFiles();
  elements.logoSummary.textContent = logos.length
    ? `${logos.length} logo${logos.length === 1 ? "" : "s"} selected`
    : "PNG or JPG, up to 2 MB each · optional";
});

addRecipient();
$("#job-restore").hidden = false;
