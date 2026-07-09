/**
 * chat.js — Ask Saral chat interface logic.
 *
 * Handles: message sending, response rendering, copy/regenerate
 * buttons, chat history loading, document selection.
 */

(function () {
  const form    = document.getElementById("chat-form");
  const input   = document.getElementById("chat-input");
  const area    = document.getElementById("chat-area");
  const clearBtn = document.getElementById("clear-history-btn");

  if (!form) return;

  const sessionId = window.Saral.getSessionId();
  let lastQuestion = "";

  // ── Load chat history on page init ────────────────────────────────────
  loadHistory();

  // ── Auto-resize input ─────────────────────────────────────────────────
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });

  // ── Send on Enter (Shift+Enter for newline) ───────────────────────────
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event("submit"));
    }
  });

  // ── Form submit ───────────────────────────────────────────────────────
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    lastQuestion = question;
    input.value = "";
    input.style.height = "auto";

    // Append user bubble
    appendMessage("user", question);
    const thinkingEl = appendThinking();

    const activeDoc = window.Saral.ActiveDoc.get();
    const docIds    = activeDoc ? [activeDoc.id] : [];
    const level     = window.Saral.LearningLevel.get();

    const { data, error } = await window.SaralAPI.Chat.ask(question, docIds, sessionId, level);

    thinkingEl.remove();

    if (error) {
      appendMessage("error", error);
      return;
    }

    appendMessage("assistant", data.answer, data.sources || []);
    scrollBottom();
  });

  // ── Clear history ─────────────────────────────────────────────────────
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      if (!confirm("Clear chat history?")) return;
      await window.SaralAPI.Chat.clearHistory(sessionId);
      area.innerHTML = "";
      window.Saral.showToast("Chat history cleared.", "info");
    });
  }

  // ── Load history ──────────────────────────────────────────────────────
  async function loadHistory() {
    const { data, error } = await window.SaralAPI.Chat.history(sessionId);
    if (error || !data?.messages?.length) return;
    data.messages.forEach((m) => {
      if (m.role === "user") {
        appendMessage("user", m.content);
      } else {
        appendMessage("assistant", m.content, m.sources || []);
      }
    });
    scrollBottom();
  }

  // ── Append message bubble ─────────────────────────────────────────────
  function appendMessage(role, content, sources = []) {
    const wrapper = document.createElement("div");
    wrapper.className = `chat-message chat-message--${role === "user" ? "user" : "assistant"}`;

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-bubble--${role === "user" ? "user" : "assistant"}`;

    if (role === "error") {
      wrapper.className = "chat-message chat-message--assistant";
      bubble.className  = "chat-bubble chat-bubble--assistant";
      bubble.innerHTML  = `<span style="color:var(--color-error)">${escapeHtml(content)}</span>`;
    } else if (role === "user") {
      bubble.textContent = content;
    } else {
      bubble.innerHTML = window.Saral.renderMarkdown(content);
    }

    wrapper.appendChild(bubble);

    // Sources row
    if (sources.length) {
      const metaRow = document.createElement("div");
      metaRow.className = "chat-meta";
      sources.forEach((s) => {
        const tag = document.createElement("span");
        tag.className   = "chat-source";
        tag.textContent = `${s.doc_name} — p.${s.page_num}`;
        metaRow.appendChild(tag);
      });
      wrapper.appendChild(metaRow);
    }

    // Action buttons for assistant messages
    if (role === "assistant") {
      const actions = document.createElement("div");
      actions.className = "chat-meta";
      actions.innerHTML = `
        <button class="chat-action-btn copy-btn">Copy</button>
        <button class="chat-action-btn regen-btn">Regenerate</button>
      `;
      actions.querySelector(".copy-btn").addEventListener("click", function () {
        window.Saral.copyToClipboard(content, this);
      });
      actions.querySelector(".regen-btn").addEventListener("click", async function () {
        if (!lastQuestion) return;
        wrapper.remove();
        const thinkingEl = appendThinking();
        const activeDoc = window.Saral.ActiveDoc.get();
        const docIds    = activeDoc ? [activeDoc.id] : [];
        const level     = window.Saral.LearningLevel.get();
        const { data, error } = await window.SaralAPI.Chat.ask(lastQuestion, docIds, sessionId, level);
        thinkingEl.remove();
        if (error) { appendMessage("error", error); return; }
        appendMessage("assistant", data.answer, data.sources || []);
        scrollBottom();
      });
      wrapper.appendChild(actions);
    }

    area.appendChild(wrapper);
    return wrapper;
  }

  function appendThinking() {
    const el = document.createElement("div");
    el.className = "chat-message chat-message--assistant";
    el.innerHTML = `<div class="chat-bubble chat-bubble--assistant" style="display:flex;align-items:center;gap:8px;">
      <div class="spinner spinner-sm"></div> <span style="color:var(--color-text-muted)">Thinking...</span>
    </div>`;
    area.appendChild(el);
    scrollBottom();
    return el;
  }

  function scrollBottom() {
    const container = area.closest(".main-content") || area.parentElement;
    if (container) container.scrollTop = container.scrollHeight;
  }

  function escapeHtml(t) {
    return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }
})();
