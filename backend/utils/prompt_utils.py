"""
utils/prompt_utils.py — All prompt templates for Saral.

Centralising prompts here means prompt engineering changes never require
touching service logic.  Every template uses str.format() substitution.
"""


from typing import Optional


# ── System persona (shared prefix) ────────────────────────────────────
SYSTEM_PERSONA = (
    "You are Saral, a dedicated educational AI assistant. "
    "You help students understand complex topics clearly and accurately. "
    "You are patient, encouraging, and always base your answers on the provided study material."
)


# ── RAG / Ask Saral ───────────────────────────────────────────────────
RAG_PROMPT = """\
{system}

{history_section}STUDY MATERIAL FROM UPLOADED DOCUMENTS:
\"\"\"
{context}
\"\"\"

STUDENT LEARNING LEVEL: {learning_level}

INSTRUCTIONS FOR SARAL:
1. Answer clearly, accurately, and at the {learning_level} level.
2. Use the provided STUDY MATERIAL above as your primary reference and context.
3. If the student asks a follow-up question or asks for more detail/marks (e.g., "in detail for 8 marks", "why?", "explain further", "give an example"), use the RECENT CONVERSATION HISTORY above to understand what topic they are asking about, and elaborate thoroughly using both the uploaded study material and your expert educational knowledge of that subject.
4. If the study material mentions a topic as a brief bullet point or outline (like lecture slides), clearly explain the full concept so the student can study for their exams, while noting which slide/document mentions it.
5. Only if the student asks about a topic completely unrelated to their study material or conversation history, reply EXACTLY:
   "I couldn't find this information in your uploaded study material. Please upload a relevant document and try again."
6. Cite parts of the study material (e.g. [Source X, page Y]) when applicable.

CURRENT QUESTION: {question}

ANSWER:"""


# ── Simplify ──────────────────────────────────────────────────────────
SIMPLIFY_PROMPT = """\
{system}

Rewrite the following concept for a {level} learner.

LEVEL GUIDELINES:
- beginner: Use everyday language and simple analogies. Avoid technical jargon entirely.
- intermediate: College-level explanation. Introduce key terminology with brief definitions.
- advanced: Technical and precise. Assume the reader has domain knowledge.

CONCEPT TO SIMPLIFY:
\"\"\"
{text}
\"\"\"

SIMPLIFIED EXPLANATION ({level} level):"""


# ── Summary ───────────────────────────────────────────────────────────
SUMMARY_PROMPTS = {
    "short": """\
{system}

Write a SHORT summary (3–5 sentences) of the following study material.
Focus on the most important idea only.

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

SHORT SUMMARY:""",

    "detailed": """\
{system}

Write a DETAILED summary of the following study material.
Cover all key concepts, definitions, and relationships between ideas.
Use clear paragraphs.

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

DETAILED SUMMARY:""",

    "bullet": """\
{system}

Summarise the following study material as a BULLET POINT LIST.
Each bullet should capture one distinct key point.
Use plain, clear language.

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

KEY POINTS:
•""",

    "one_minute": """\
{system}

Write a ONE-MINUTE REVISION summary of the following study material.
Imagine a student reading this 5 minutes before an exam.
It must be concise, high-impact, and cover only what matters most.

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

ONE-MINUTE REVISION:""",

    "exam_notes": """\
{system}

Create structured EXAM REVISION NOTES from the following study material.
Format them as:

TOPIC: <topic name>
KEY DEFINITIONS:
- <term>: <definition>
...
IMPORTANT CONCEPTS:
- <concept and brief explanation>
...
COMMON EXAM POINTS:
- <likely exam question or tested idea>
...

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

EXAM REVISION NOTES:""",
}


# ── Quiz ──────────────────────────────────────────────────────────────
QUIZ_PROMPTS = {
    "mcq": """\
{system}

Generate exactly {count} multiple-choice questions from the study material below.
Difficulty: {difficulty}.

CRITICAL INSTRUCTION: You MUST generate EXACTLY {count} distinct questions. Do not generate fewer than {count}. Your JSON array must contain exactly {count} items.

Return ONLY a valid JSON array. No extra text before or after. Use this exact schema:
[
  {{
    "question": "question text",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "answer": "A) ...",
    "explanation": "brief explanation of why this is correct"
  }}
]

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

JSON:""",

    "true_false": """\
{system}

Generate exactly {count} true/false questions from the study material below.
Difficulty: {difficulty}.

CRITICAL INSTRUCTION: You MUST generate EXACTLY {count} distinct questions. Do not generate fewer than {count}. Your JSON array must contain exactly {count} items.

Return ONLY a valid JSON array:
[
  {{
    "question": "statement text",
    "answer": "True" or "False",
    "explanation": "brief explanation"
  }}
]

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

JSON:""",

    "short": """\
{system}

Generate exactly {count} short-answer questions from the study material below.
Difficulty: {difficulty}. Each answer should be 1–3 sentences.

CRITICAL INSTRUCTION: You MUST generate EXACTLY {count} distinct questions. Do not generate fewer than {count}. Your JSON array must contain exactly {count} items.

Return ONLY a valid JSON array:
[
  {{
    "question": "question text",
    "answer": "model answer (1–3 sentences)"
  }}
]

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

JSON:""",

    "long": """\
{system}

Generate exactly {count} long-answer / essay questions from the study material below.
Difficulty: {difficulty}. Each answer should be a full paragraph.

CRITICAL INSTRUCTION: You MUST generate EXACTLY {count} distinct questions. Do not generate fewer than {count}. Your JSON array must contain exactly {count} items.

Return ONLY a valid JSON array:
[
  {{
    "question": "question text",
    "answer": "detailed model answer"
  }}
]

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

JSON:""",
}



# ── Explain Term ──────────────────────────────────────────────────────
EXPLAIN_PROMPT = """\
{system}

Explain the following term clearly.

{context_section}

Provide your explanation in this exact format:

DEFINITION: <one-sentence definition>

MEANING: <2–3 sentence deeper explanation>

EXAMPLE: <a concrete example>

REAL-WORLD ANALOGY: <a simple everyday analogy that makes this easy to remember>

TERM TO EXPLAIN: {term}

EXPLANATION:"""


# ── Revision ──────────────────────────────────────────────────────────
REVISION_PROMPTS = {
    "flashcards": """\
{system}

Create {count} flashcards from the following study material.
Each flashcard should have a clear FRONT (term or question) and BACK (answer or definition).

Return ONLY a valid JSON array:
[
  {{
    "front": "term or question",
    "back": "definition or answer"
  }}
]

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

JSON:""",

    "quick_notes": """\
{system}

Create QUICK NOTES from the following study material.
Format:
- Section headings where appropriate
- Short, punchy bullet points under each section
- Highlight key terms in UPPERCASE

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

QUICK NOTES:""",

    "exam_sheet": """\
{system}

Create a one-page EXAM CHEAT SHEET from the following study material.
Include: key formulas, definitions, important dates/numbers, and must-know concepts.
Be as dense and information-rich as possible.

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

EXAM CHEAT SHEET:""",
}


# ── Important Points ──────────────────────────────────────────────────
IMPORTANT_POINTS_PROMPT = """\
{system}

From the following study material, extract:

1. IMPORTANT FORMULAS (if any)
2. KEY DEFINITIONS (5–10 terms)
3. EXAM TIPS (common mistakes, frequently tested ideas)
4. FREQUENTLY ASKED CONCEPTS

STUDY MATERIAL:
\"\"\"
{context}
\"\"\"

IMPORTANT POINTS:"""


def build_rag_prompt(
    context: str,
    question: str,
    learning_level: str,
    history: Optional[list[dict]] = None,
) -> str:
    history_section = ""
    if history:
        history_lines = []
        for msg in history:
            role = "STUDENT" if msg.get("role") == "user" else "SARAL"
            history_lines.append(f"{role}: {msg.get('content', '')}")
        history_section = "RECENT CONVERSATION HISTORY:\n\"\"\"\n" + "\n\n".join(history_lines) + "\n\"\"\"\n\n"

    return RAG_PROMPT.format(
        system=SYSTEM_PERSONA,
        history_section=history_section,
        context=context,
        learning_level=learning_level,
        question=question,
    )


def build_simplify_prompt(text: str, level: str) -> str:
    return SIMPLIFY_PROMPT.format(system=SYSTEM_PERSONA, level=level, text=text)


def build_summary_prompt(context: str, summary_type: str) -> str:
    template = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["short"])
    return template.format(system=SYSTEM_PERSONA, context=context)


def build_quiz_prompt(context: str, quiz_type: str, count: int, difficulty: str) -> str:
    template = QUIZ_PROMPTS.get(quiz_type, QUIZ_PROMPTS["mcq"])
    return template.format(
        system=SYSTEM_PERSONA,
        context=context,
        count=count,
        difficulty=difficulty,
    )


def build_explain_prompt(term: str, context: str = "") -> str:
    context_section = (
        f"Use the following study material as context if relevant:\n\"\"\"\n{context}\n\"\"\"\n"
        if context else ""
    )
    return EXPLAIN_PROMPT.format(
        system=SYSTEM_PERSONA,
        context_section=context_section,
        term=term,
    )


def build_revision_prompt(context: str, revision_type: str, count: int = 10) -> str:
    template = REVISION_PROMPTS.get(revision_type, REVISION_PROMPTS["quick_notes"])
    return template.format(system=SYSTEM_PERSONA, context=context, count=count)


def build_important_points_prompt(context: str) -> str:
    return IMPORTANT_POINTS_PROMPT.format(system=SYSTEM_PERSONA, context=context)
