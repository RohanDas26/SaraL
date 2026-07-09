/**
 * utils.js — Shared helpers used across all pages.
 *
 * Includes:
 *  - Session ID management
 *  - Simple Markdown renderer (no KaTeX, no external deps)
 *  - Copy-to-clipboard helper
 *  - Toast notification system
 */

// ── Session ID ─────────────────────────────────────────────────────────

function getSessionId() {
  let id = localStorage.getItem("saral_session_id");
  if (!id) {
    id = "session_" + Math.random().toString(36).slice(2, 11);
    localStorage.setItem("saral_session_id", id);
  }
  return id;
}

// ── Active document store ──────────────────────────────────────────────

const ActiveDoc = {
  get() {
    const raw = localStorage.getItem("saral_active_doc");
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  },
  set(doc) {
    localStorage.setItem("saral_active_doc", JSON.stringify(doc));
  },
  clear() {
    localStorage.removeItem("saral_active_doc");
  },
};

// ── Learning level store ───────────────────────────────────────────────

const LearningLevel = {
  get()    { return localStorage.getItem("saral_level") || "intermediate"; },
  set(lvl) { localStorage.setItem("saral_level", lvl); },
};

// ── Simple Markdown renderer ───────────────────────────────────────────
// Handles: headings, bold, italic, code, pre, ul, ol, blockquote, hr, links.
// Deliberately minimal — no external lib, no security risk.

function renderMarkdown(text) {
  if (!text) return "";

  let html = escapeHtml(text);

  // Fenced code blocks  ```lang\ncode\n```
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g, (_, code) =>
    `<pre><code>${code.trim()}</code></pre>`
  );

  // Inline code
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");

  // Headings
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm,  "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm,   "<h1>$1</h1>");

  // Bold / Italic
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g,      "<em>$1</em>");

  // Unordered list
  html = html.replace(/((?:^[-•] .+\n?)+)/gm, (block) => {
    const items = block.trim().split("\n").map(l => `<li>${l.replace(/^[-•] /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });

  // Ordered list
  html = html.replace(/((?:^\d+\. .+\n?)+)/gm, (block) => {
    const items = block.trim().split("\n").map(l => `<li>${l.replace(/^\d+\. /, "")}</li>`).join("");
    return `<ol>${items}</ol>`;
  });

  // Blockquote
  html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");

  // Horizontal rule
  html = html.replace(/^---+$/gm, "<hr>");

  // Paragraphs — convert double newlines
  html = html.replace(/\n{2,}/g, "</p><p>");
  html = `<p>${html}</p>`;

  // Single newlines → <br> inside paragraphs (but not inside block elements)
  html = html.replace(/(?<!>)\n(?!<)/g, "<br>");

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, "");
  html = html.replace(/<p>(<(?:h[1-6]|ul|ol|pre|blockquote|hr)[^>]*>)/g, "$1");
  html = html.replace(/(<\/(?:h[1-6]|ul|ol|pre|blockquote)>)<\/p>/g, "$1");

  return html;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ── Copy to clipboard ──────────────────────────────────────────────────

async function copyToClipboard(text, btn = null) {
  try {
    await navigator.clipboard.writeText(text);
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = "Copied";
      btn.disabled = true;
      setTimeout(() => { btn.textContent = orig; btn.disabled = false; }, 1800);
    }
    return true;
  } catch {
    return false;
  }
}

// ── Toast notifications ────────────────────────────────────────────────

function showToast(message, type = "info", duration = 3500) {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.style.cssText =
      "position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  const colors = {
    info:    "#0969da",
    success: "#1a7f37",
    error:   "#cf222e",
    warn:    "#9a6700",
  };
  toast.style.cssText = `
    background:#1f2328;
    color:#fff;
    padding:10px 16px;
    border-radius:8px;
    font-size:13px;
    border-left:3px solid ${colors[type] || colors.info};
    max-width:320px;
    box-shadow:0 4px 12px rgba(0,0,0,0.15);
    opacity:0;
    transition:opacity 0.2s;
  `;
  toast.textContent = message;
  container.appendChild(toast);

  requestAnimationFrame(() => { toast.style.opacity = "1"; });
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// ── Loading overlay ────────────────────────────────────────────────────

function showLoading(message = "Thinking...") {
  const overlay = document.getElementById("loading-overlay");
  if (!overlay) return;
  const label = overlay.querySelector("p");
  if (label) label.textContent = message;
  overlay.classList.add("active");
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.remove("active");
}

// ── Exports ────────────────────────────────────────────────────────────

window.Saral = {
  getSessionId,
  ActiveDoc,
  LearningLevel,
  renderMarkdown,
  copyToClipboard,
  showToast,
  showLoading,
  hideLoading,
};
