/**
 * quiz.js — Interactive quiz interface.
 */

(function () {
  const docSel       = document.getElementById("quiz-doc-select");
  const typeSelect   = document.getElementById("quiz-type-select");
  const diffSelect   = document.getElementById("quiz-difficulty-select");
  const countInput   = document.getElementById("quiz-count");
  const countMinus   = document.getElementById("quiz-count-minus");
  const countPlus    = document.getElementById("quiz-count-plus");
  const generateBtn  = document.getElementById("quiz-generate-btn");
  const quizArea     = document.getElementById("quiz-area");
  const quizConfig   = document.getElementById("quiz-config");
  const questionText = document.getElementById("quiz-question-text");
  const optionsEl    = document.getElementById("quiz-options");
  const answerInput  = document.getElementById("quiz-answer-input");
  const explanation  = document.getElementById("quiz-explanation");
  const progressText = document.getElementById("quiz-progress-text");
  const progressBar  = document.getElementById("quiz-progress-bar");
  const scoreEl      = document.getElementById("quiz-score");
  const attemptedEl  = document.getElementById("quiz-attempted");
  const showAnsBtn   = document.getElementById("quiz-show-answer-btn");
  const nextBtn      = document.getElementById("quiz-next-btn");
  const restartBtn   = document.getElementById("quiz-restart-btn");

  if (!generateBtn) return;

  if (countMinus && countInput) {
    countMinus.addEventListener("click", () => {
      let val = parseInt(countInput.value) || 5;
      if (val > 1) countInput.value = val - 1;
    });
  }
  if (countPlus && countInput) {
    countPlus.addEventListener("click", () => {
      let val = parseInt(countInput.value) || 5;
      if (val < 20) countInput.value = val + 1;
    });
  }

  let questions   = [];
  let currentIdx  = 0;
  let score       = 0;
  let answered    = false;

  // ── Load documents into select ─────────────────────────────────────
  async function loadDocs() {
    const { data } = await window.SaralAPI.Documents.list();
    if (!data?.documents?.length) return;
    data.documents.filter(d => d.status === "indexed").forEach((d) => {
      docSel.appendChild(new Option(d.display_name, d.id));
    });
    const active = window.Saral.ActiveDoc.get();
    if (active) docSel.value = active.id;
  }

  // ── Generate quiz ─────────────────────────────────────────────────
  generateBtn.addEventListener("click", async () => {
    const docId = docSel.value;
    const type  = typeSelect.value;
    const diff  = diffSelect.value;
    const count = Math.min(Math.max(parseInt(countInput.value) || 5, 1), 20);

    if (!docId) { window.Saral.showToast("Please select a document.", "warn"); return; }

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<div class="spinner spinner-sm"></div>';
    window.Saral.showLoading("Generating quiz...");

    const { data, error } = await window.SaralAPI.Features.quiz(docId, type, count, diff);
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Quiz";
    window.Saral.hideLoading();

    if (error) { window.Saral.showToast(error, "error"); return; }
    if (!data.questions?.length) { window.Saral.showToast("No questions generated. Try again.", "warn"); return; }

    questions  = data.questions;
    currentIdx = 0;
    score      = 0;
    answered   = false;

    quizConfig.style.display = "none";
    quizArea.style.display   = "";
    renderQuestion();

    if (data.cached) window.Saral.showToast("Quiz loaded from cache.", "info", 2000);
  });

  // ── Render current question ───────────────────────────────────────
  function renderQuestion() {
    const q       = questions[currentIdx];
    const total   = questions.length;
    const isMCQ   = q.options?.length > 0;
    const isTF    = typeof q.answer === "string" && ["True","False"].includes(q.answer);
    const isShort = !isMCQ && !isTF;

    progressText.textContent = `Question ${currentIdx + 1} of ${total}`;
    progressBar.style.width  = ((currentIdx + 1) / total * 100) + "%";
    questionText.textContent = q.question;
    explanation.style.display = "none";
    answered = false;
    nextBtn.textContent = currentIdx === total - 1 ? "Finish" : "Next";

    optionsEl.innerHTML = "";
    answerInput.style.display = "none";

    if (isMCQ || isTF) {
      const opts = isMCQ ? q.options : ["True", "False"];
      opts.forEach((opt) => {
        const el = document.createElement("div");
        el.className    = "quiz-option";
        el.textContent  = opt;
        el.addEventListener("click", () => handleOptionSelect(el, opt, q.answer));
        optionsEl.appendChild(el);
      });
    } else {
      answerInput.value = "";
      answerInput.style.display = "";
    }
  }

  function handleOptionSelect(el, chosen, correct) {
    if (answered) return;
    answered = true;

    const isCorrect = chosen === correct;
    if (isCorrect) {
      el.classList.add("correct");
      score++;
      scoreEl.textContent = score;
    } else {
      el.classList.add("incorrect");
      // Highlight correct answer
      optionsEl.querySelectorAll(".quiz-option").forEach((opt) => {
        if (opt.textContent === correct) opt.classList.add("correct");
      });
    }

    attemptedEl.textContent = currentIdx + 1;

    if (questions[currentIdx].explanation) {
      explanation.textContent = "Explanation: " + questions[currentIdx].explanation;
      explanation.style.display = "flex";
    }
  }

  showAnsBtn.addEventListener("click", () => {
    const q = questions[currentIdx];
    if (!answered) {
      answered = true;
      attemptedEl.textContent = currentIdx + 1;
      optionsEl.querySelectorAll(".quiz-option").forEach((opt) => {
        if (opt.textContent === q.answer) opt.classList.add("correct");
      });
    }
    if (q.explanation) {
      explanation.textContent = "Answer: " + q.answer + (q.explanation ? " — " + q.explanation : "");
      explanation.style.display = "flex";
    } else {
      explanation.textContent = "Correct answer: " + q.answer;
      explanation.style.display = "flex";
    }
  });

  nextBtn.addEventListener("click", () => {
    if (currentIdx < questions.length - 1) {
      currentIdx++;
      renderQuestion();
    } else {
      // Finished
      const total   = questions.length;
      const pct     = Math.round(score / total * 100);
      window.Saral.showToast(`Quiz complete! Score: ${score}/${total} (${pct}%)`, pct >= 70 ? "success" : "warn", 5000);
      quizArea.style.display   = "none";
      quizConfig.style.display = "";
    }
  });

  restartBtn.addEventListener("click", () => {
    quizArea.style.display   = "none";
    quizConfig.style.display = "";
  });

  // Guard: DOMContentLoaded may have already fired by the time this script runs.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadDocs);
  } else {
    loadDocs();
  }
})();
