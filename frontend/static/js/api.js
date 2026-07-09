/**
 * api.js — Centralised fetch wrapper for all Saral API calls.
 *
 * All communication with the Flask backend goes through this module.
 * No API keys or secrets ever pass through here.
 */

const API_BASE = "";   // Same origin; Flask serves both frontend and API.

/**
 * Core fetch helper.
 * Returns {data, error} — never throws.
 */
async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });

    // Handle 429 — IBM quota exhaustion
    if (res.status === 429) {
      return {
        data: null,
        error: "The AI service has temporarily reached its free usage limit. Please try again later.",
      };
    }

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      return { data: null, error: data.error || `Request failed (${res.status})` };
    }
    return { data, error: null };
  } catch (err) {
    return { data: null, error: "Network error. Is the server running?" };
  }
}

// ── Documents ──────────────────────────────────────────────────────────

const Documents = {
  async upload(file) {
    const form = new FormData();
    form.append("file", file);
    return apiFetch("/api/documents/upload", {
      method: "POST",
      headers: {},    // Let browser set multipart boundary
      body: form,
    });
  },

  async list() {
    return apiFetch("/api/documents/");
  },

  async get(docId) {
    return apiFetch(`/api/documents/${docId}`);
  },

  async delete(docId) {
    return apiFetch(`/api/documents/${docId}`, { method: "DELETE" });
  },

  async status(docId) {
    return apiFetch(`/api/documents/${docId}/status`);
  },
};

// ── Chat ───────────────────────────────────────────────────────────────

const Chat = {
  async ask(question, docIds = [], sessionId = "", learningLevel = "intermediate") {
    return apiFetch("/api/chat/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        doc_ids: docIds,
        session_id: sessionId,
        learning_level: learningLevel,
      }),
    });
  },

  async history(sessionId) {
    return apiFetch(`/api/chat/history/${sessionId}`);
  },

  async clearHistory(sessionId) {
    return apiFetch(`/api/chat/history/${sessionId}`, { method: "DELETE" });
  },
};

// ── Features ───────────────────────────────────────────────────────────

const Features = {
  async simplify(text, level = "intermediate", noCache = false) {
    return apiFetch("/api/simplify", {
      method: "POST",
      body: JSON.stringify({ text, level, no_cache: noCache }),
    });
  },

  async summary(docId, type = "short") {
    return apiFetch("/api/summary", {
      method: "POST",
      body: JSON.stringify({ doc_id: docId, type }),
    });
  },

  async quiz(docId, type = "mcq", count = 5, difficulty = "medium") {
    return apiFetch("/api/quiz/generate", {
      method: "POST",
      body: JSON.stringify({ doc_id: docId, type, count, difficulty }),
    });
  },

  async explain(term, docId = null) {
    return apiFetch("/api/explain", {
      method: "POST",
      body: JSON.stringify({ term, doc_id: docId }),
    });
  },

  async revision(docId, type = "quick_notes", count = 10) {
    return apiFetch("/api/revision/generate", {
      method: "POST",
      body: JSON.stringify({ doc_id: docId, type, count }),
    });
  },

  async importantPoints(docId) {
    return apiFetch("/api/revision/important-points", {
      method: "POST",
      body: JSON.stringify({ doc_id: docId }),
    });
  },
};

// ── Settings ───────────────────────────────────────────────────────────

const Settings = {
  async get() {
    return apiFetch("/api/settings");
  },

  async update(settings) {
    return apiFetch("/api/settings", {
      method: "POST",
      body: JSON.stringify(settings),
    });
  },

  async clearCache() {
    return apiFetch("/api/cache/clear", { method: "POST" });
  },
};

// ── Export ─────────────────────────────────────────────────────────────

window.SaralAPI = { Documents, Chat, Features, Settings };
