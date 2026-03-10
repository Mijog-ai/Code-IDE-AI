# prompts.py
# System prompts and response-parsing helpers for Quick Coder.

from __future__ import annotations

# ── Per-language system prompts ───────────────────────────────────

_BASE_RULES = """
## OUTPUT RULES — FOLLOW EXACTLY
1. Always wrap ALL code in a single ```{lang} code block.
2. Never split code across multiple code blocks.
3. Write complete, runnable scripts — not fragments or pseudocode.
4. After the code block, write a short explanation (3-6 bullet points).
5. Keep explanations concise — the code speaks for itself.
6. If the user asks a question (not for code), answer clearly in plain text.

## CODE QUALITY RULES
- Add brief comments on non-obvious logic
- Use descriptive variable names
- Handle common errors where relevant
- Write self-contained scripts

## WHAT YOU NEVER DO
- Never generate harmful, malicious, or system-damaging code
- Never use placeholder logic like `# TODO implement this`
- Never truncate code with `# ... rest of code`
- Never apologize or add filler phrases like "Certainly!" or "Of course!"
"""

_CONTINUATION_REMINDER = """## CONTINUATION MODE — THIS IS A FOLLOW-UP REQUEST
The conversation already contains code that was written earlier in this session.
You MUST follow these rules:
- DO NOT rewrite the entire code from scratch.
- ONLY apply the changes the user is asking for.
- Keep all existing logic, structure, and variable names that are not being changed.
- Output the FULL updated file (with your targeted edits applied), not just the changed lines.
- If the user's request is unclear, ask for clarification instead of guessing.
"""

_PYTHON_PROMPT = f"""You are an expert Python software engineer and coding assistant \
built into an AI-powered coding IDE.

## YOUR JOB
Help users write clean, correct, production-ready Python code.
{_BASE_RULES.format(lang="python")}
- Prefer standard library over third-party when possible
- Include a main guard: if __name__ == "__main__": where appropriate
- Never use argparse, sys.argv, or CLI argument parsing — code runs headlessly

## RESPONSE FORMAT EXAMPLE
```python
# Your complete code here
```

**What this does:**
- Point 1
- Point 2
- Point 3
"""



_LANG_PROMPTS: dict[str, str] = {
    "python":     _PYTHON_PROMPT,
}

# Keep a plain reference for legacy callers
SYSTEM_PROMPT = _PYTHON_PROMPT


# ── Public API ────────────────────────────────────────────────────

def get_system_prompt(language: str = "python") -> str:
    """Return the system prompt for the given language key."""
    return _LANG_PROMPTS.get(language.lower(), _PYTHON_PROMPT)


def build_messages(chat_history: list[dict], language: str = "python") -> list[dict]:
    """Prepend the appropriate system prompt to *chat_history*.

    When the conversation already has prior messages (continuation), an extra
    system reminder is injected right before the latest user turn so that
    local/smaller models clearly understand they must edit existing code
    rather than rewrite everything from scratch.
    """
    system_msg = {"role": "system", "content": get_system_prompt(language)}
    is_continuation = len(chat_history) > 1  # more than just the first user message

    if is_continuation:
        # Inject the continuation reminder as a second system message
        # placed just before the last user turn so it stays in recent context.
        reminder_msg = {"role": "system", "content": _CONTINUATION_REMINDER}
        # Insert before the final user message for maximum recency effect
        *earlier, last = chat_history
        return [system_msg] + earlier + [reminder_msg, last]

    return [system_msg] + chat_history


def extract_code(response: str, language: str = "python") -> str:
    """
    Pull the first code block out of the AI's response.
    Tries the exact language fence first, then generic ```.
    """
    fence = f"```{language}"
    if fence in response:
        start = response.find(fence) + len(fence)
        end   = response.find("```", start)
        if end != -1:
            return response[start:end].strip()
        return response[start:].strip()

    if "```python" in response:
        start = response.find("```python") + len("```python")
        end   = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    if "```" in response:
        start   = response.find("```") + 3
        newline = response.find("\n", start)
        if newline != -1 and response[start:newline].strip().isalpha():
            start = newline + 1
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    return ""


def extract_explanation(response: str) -> str:
    """
    Extract the explanation text that comes AFTER the last code block.
    Returns the full response if no code block is present.
    """
    if "```" in response:
        last_fence  = response.rfind("```")
        explanation = response[last_fence + 3:].strip()
        return explanation if explanation else ""
    return response.strip()
