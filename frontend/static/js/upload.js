/**
 * upload.js — Drag-and-drop + click-to-browse upload logic.
 *
 * Phase 2 made uploads async (202 Accepted).
 * This module polls GET /api/documents/<id>/status until indexing completes.
 */

(function () {
  const zone        = document.getElementById("upload-zone");
  const input       = document.getElementById("upload-input");
  const globalInput = document.getElementById("global-upload-input");
  const status      = document.getElementById("upload-status");

  if (zone && input) {
    zone.addEventListener("click", (e) => {
      if (e.target !== input) input.click();
    });
  }

  if (input) {
    input.addEventListener("change", () => {
      if (input.files.length) {
        handleFile(input.files[0], input);
      }
    });
  }

  if (globalInput) {
    globalInput.addEventListener("change", () => {
      if (globalInput.files.length) {
        handleFile(globalInput.files[0], globalInput);
      }
    });
  }

  if (zone) {
    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("drag-over");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file, input || globalInput);
    });
  }

  async function handleFile(file, sourceInput) {
    const allowedExt = [".pdf", ".docx", ".txt"];
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();

    if (!allowedExt.includes(ext)) {
      showStatus("error", "Unsupported file type. Please upload a PDF, DOCX, or TXT file.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      showStatus("error", "File exceeds the 25 MB upload limit.");
      return;
    }

    showStatus("loading", `Uploading ${file.name}...`);
    if (zone) zone.style.pointerEvents = "none";

    const { data, error } = await window.SaralAPI.Documents.upload(file);
    if (error) {
      if (zone) zone.style.pointerEvents = "";
      if (sourceInput) sourceInput.value = "";
      showStatus("error", error);
      return;
    }

    const doc = data.document;

    // 202 Accepted — poll until indexed or failed
    showStatus("loading", `Processing ${file.name}... (this may take a moment)`);
    await pollUntilIndexed(doc.id, file.name);
    if (zone) zone.style.pointerEvents = "";
    if (sourceInput) sourceInput.value = "";
  }

  async function pollUntilIndexed(docId, fileName) {
    const maxAttempts = 180;   // 180 × 2s = 6 minutes max for large PDFs and cloud container boots
    let attempts = 0;
    let consecutiveErrors = 0;

    while (attempts < maxAttempts) {
      await sleep(2000);
      attempts++;

      const { data, error } = await window.SaralAPI.Documents.status(docId);
      if (error) {
        consecutiveErrors++;
        if (consecutiveErrors > 30) {
          showStatus("error", `Could not check status after multiple retries: ${error}. Your document may still be processing in the background.`);
          return;
        }
        showStatus("loading", `⏳ Processing "${fileName}"... (waiting for server status, attempt ${consecutiveErrors})`);
        continue;
      }

      consecutiveErrors = 0;
      const s = data.status;
      const pct = data.progress_pct || 0;

      if (s === "indexed") {
        const { data: docData } = await window.SaralAPI.Documents.get(docId);
        const doc = docData?.document;
        if (doc) window.Saral.ActiveDoc.set(doc);
        showStatus("success",
          `"${fileName}" is ready — ${data.chunk_count} chunks indexed.`);
        window.Saral.showToast(`"${fileName}" indexed successfully.`, "success");
        if (typeof window.refreshDocumentList === "function") {
          window.refreshDocumentList();
        }
        return;
      }

      if (s === "failed") {
        showStatus("error", `Processing failed: ${data.error || "Unknown error."}`);
        return;
      }

      // Still processing — update progress
      showStatus("loading", `Processing "${fileName}"... ${pct}%`);
    }

    showStatus("error", "Processing timed out. The document may be too large or complex.");
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function showStatus(type, message) {
    if (!status) {
      if (type === "error" || type === "success" || message.startsWith("Uploading")) {
        window.Saral?.showToast(message, type === "loading" ? "info" : type);
      }
      return;
    }
    const cls = type === "loading" ? "info" : type;
    status.className = `alert alert-${cls}`;
    status.style.display = "flex";
    status.innerHTML = type === "loading"
      ? `<div class="spinner spinner-sm"></div><span style="margin-left:8px">${message}</span>`
      : message;
  }
})();
