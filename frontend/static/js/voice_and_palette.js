/**
 * voice_and_palette.js — Saral Command Palette (Ctrl+K) & Voice Typing (Web Speech API)
 * Pure frontend extension: operates without modifying backend routes or server APIs.
 */

(function () {
  // ── 1. COMMAND PALETTE (CTRL + K) ─────────────────────────────────────────
  const COMMANDS = [
    { id: "chat", title: "💬 Ask Saral (AI Tutor)", desc: "Interactive document Q&A and tutoring", path: "/chat" },
    { id: "simplify", title: "💡 Simplify Study Notes", desc: "Break down dense text into easy concepts", path: "/simplify" },
    { id: "summary", title: "📑 Instant Summarizer", desc: "Generate bulleted or paragraph summaries", path: "/summary" },
    { id: "quiz", title: "📝 Quiz Generator", desc: "Create practice tests from your study material", path: "/quiz" },
    { id: "explain", title: "📖 Deep Concept Explainer", desc: "Master academic terms with real-life analogies", path: "/explain" },
    { id: "revision", title: "🎯 Flashcards & Revision", desc: "Interactive flip cards and exam cheat sheets", path: "/revision" },
    { id: "upload", title: "📂 Upload New Document (+) ", desc: "Add a PDF or DOCX to your knowledge base", action: "upload" },
    { id: "settings", title: "⚙️ Settings & System Status", desc: "Manage AI parameters and learning level", path: "/settings" }
  ];

  let activeIndex = 0;
  let filteredCommands = [...COMMANDS];

  function openPalette() {
    const modal = document.getElementById("cmd-palette-modal");
    const input = document.getElementById("cmd-palette-input");
    if (!modal || !input) return;

    modal.style.display = "flex";
    input.value = "";
    activeIndex = 0;
    renderPaletteResults("");
    setTimeout(() => input.focus(), 50);
  }

  function closePalette() {
    const modal = document.getElementById("cmd-palette-modal");
    if (modal) modal.style.display = "none";
  }

  function renderPaletteResults(query) {
    const resultsContainer = document.getElementById("cmd-palette-results");
    if (!resultsContainer) return;

    const q = (query || "").toLowerCase().trim();
    filteredCommands = COMMANDS.filter(c => 
      c.title.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q)
    );

    // Also include dynamic active/indexed documents if searching docs
    const activeDoc = window.Saral?.ActiveDoc?.get();
    if (activeDoc && activeDoc.display_name.toLowerCase().includes(q) && !filteredCommands.some(c => c.id === "activedoc")) {
      filteredCommands.unshift({
        id: "activedoc",
        title: `📚 Active Document: ${activeDoc.display_name}`,
        desc: "Currently selected study material",
        action: "noop"
      });
    }

    if (filteredCommands.length === 0) {
      resultsContainer.innerHTML = `<div style="padding:24px;text-align:center;color:var(--color-text-muted);font-size:13px;">No commands or tools found matching "${query}"</div>`;
      return;
    }

    resultsContainer.innerHTML = filteredCommands.map((c, i) => `
      <div class="cmd-item ${i === activeIndex ? "active" : ""}" data-index="${i}">
        <div class="cmd-item__icon">${c.title.split(" ")[0] || "⚡"}</div>
        <div class="cmd-item__text">
          <div class="cmd-item__title">${c.title.substring(c.title.indexOf(" ") + 1)}</div>
          <div class="cmd-item__desc">${c.desc}</div>
        </div>
      </div>
    `).join("");

    resultsContainer.querySelectorAll(".cmd-item").forEach(el => {
      el.addEventListener("click", () => executeCommand(filteredCommands[parseInt(el.dataset.index, 10)]));
      el.addEventListener("mouseenter", () => {
        activeIndex = parseInt(el.dataset.index, 10);
        resultsContainer.querySelectorAll(".cmd-item").forEach((item, idx) => {
          item.classList.toggle("active", idx === activeIndex);
        });
      });
    });
  }

  function executeCommand(cmd) {
    if (!cmd) return;
    closePalette();
    if (cmd.action === "upload") {
      const inp = document.getElementById("global-upload-input") || document.getElementById("upload-input");
      if (inp) inp.click();
    } else if (cmd.path) {
      window.location.href = cmd.path;
    }
  }

  // ── 2. VOICE TYPING (WEB SPEECH API) ──────────────────────────────────────
  let recognition = null;
  let isListening = false;
  let activeVoiceBtn = null;

  function initSpeechEngine() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) return null;
    const rec = new SpeechRec();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";
    return rec;
  }

  function toggleVoiceTyping(targetInput, btnElement) {
    if (isListening && recognition) {
      recognition.stop();
      return;
    }

    if (!recognition) recognition = initSpeechEngine();
    if (!recognition) {
      window.Saral?.showToast("Voice typing is not supported in this browser. Please try Google Chrome or Edge.", "info");
      return;
    }

    activeVoiceBtn = btnElement;
    isListening = true;
    if (activeVoiceBtn) activeVoiceBtn.classList.add("listening");

    // Show floating pill
    let pill = document.getElementById("voice-status-pill");
    if (!pill) {
      pill = document.createElement("div");
      pill.id = "voice-status-pill";
      pill.className = "voice-status-pill";
      pill.innerHTML = `<span class="voice-dot-listening"></span><span>🎙️ Listening... speak clearly now!</span>`;
      document.body.appendChild(pill);
    }
    pill.style.display = "flex";

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }
      if (targetInput && transcript) {
        if (targetInput.tagName === "TEXTAREA" || targetInput.tagName === "INPUT") {
          targetInput.value = transcript;
          targetInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
    };

    recognition.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      stopVoiceUI();
      if (event.error === "not-allowed") {
        window.Saral?.showToast("Microphone permission denied. Please allow mic access in browser settings.", "error");
      }
    };

    recognition.onend = () => {
      stopVoiceUI();
    };

    try {
      recognition.start();
    } catch (err) {
      stopVoiceUI();
    }
  }

  function stopVoiceUI() {
    isListening = false;
    if (activeVoiceBtn) activeVoiceBtn.classList.remove("listening");
    const pill = document.getElementById("voice-status-pill");
    if (pill) pill.style.display = "none";
  }

  // Auto-inject voice mic buttons into main inputs across tool pages
  function injectVoiceButtons() {
    const targets = [
      { inputId: "chat-input", insertAfter: true },
      { inputId: "simplify-input", insertAfter: false },
      { inputId: "summary-text-input", insertAfter: false },
      { inputId: "explain-topic", insertAfter: true },
      { inputId: "cmd-palette-input", insertAfter: true, btnId: "cmd-voice-btn" }
    ];

    targets.forEach(cfg => {
      const inp = document.getElementById(cfg.inputId);
      if (!inp) return;

      let btn = cfg.btnId ? document.getElementById(cfg.btnId) : null;
      if (!btn && inp.parentElement) {
        btn = document.createElement("button");
        btn.type = "button";
        btn.className = "voice-type-btn";
        btn.title = "Voice Typing (Click and speak)";
        btn.innerHTML = `🎙️`;
        btn.style.marginLeft = "6px";
        if (cfg.insertAfter) {
          inp.parentElement.insertBefore(btn, inp.nextSibling);
        } else {
          inp.parentElement.appendChild(btn);
        }
      }

      if (btn && !btn.dataset.voiceAttached) {
        btn.dataset.voiceAttached = "true";
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          toggleVoiceTyping(inp, btn);
        });
      }
    });
  }

  // ── 3. GLOBAL EVENT LISTENERS & INITIALIZATION ────────────────────────────
  document.addEventListener("keydown", (e) => {
    // Check for Ctrl + K or Cmd + K
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const modal = document.getElementById("cmd-palette-modal");
      if (modal && modal.style.display === "flex") {
        closePalette();
      } else {
        openPalette();
      }
    }

    // Check inside command palette modal
    const modal = document.getElementById("cmd-palette-modal");
    if (modal && modal.style.display === "flex") {
      if (e.key === "Escape") {
        closePalette();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (filteredCommands.length) {
          activeIndex = (activeIndex + 1) % filteredCommands.length;
          renderPaletteResults(document.getElementById("cmd-palette-input")?.value || "");
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (filteredCommands.length) {
          activeIndex = (activeIndex - 1 + filteredCommands.length) % filteredCommands.length;
          renderPaletteResults(document.getElementById("cmd-palette-input")?.value || "");
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filteredCommands[activeIndex]) {
          executeCommand(filteredCommands[activeIndex]);
        }
      }
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    // Setup top trigger button
    const triggerBtn = document.getElementById("cmd-palette-trigger");
    if (triggerBtn) triggerBtn.addEventListener("click", openPalette);

    // Setup backdrop close
    const backdrop = document.getElementById("cmd-palette-backdrop");
    if (backdrop) backdrop.addEventListener("click", closePalette);
    const closeEsc = document.getElementById("cmd-palette-close");
    if (closeEsc) closeEsc.addEventListener("click", closePalette);

    // Setup live search typing
    const searchInp = document.getElementById("cmd-palette-input");
    if (searchInp) {
      searchInp.addEventListener("input", (e) => {
        activeIndex = 0;
        renderPaletteResults(e.target.value);
      });
    }

    // Auto inject voice buttons on load
    injectVoiceButtons();
  });

  // Re-check for injected voice buttons on page transitions or DOM updates
  setTimeout(injectVoiceButtons, 500);
})();
