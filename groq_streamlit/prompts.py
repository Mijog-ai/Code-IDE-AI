# prompts.py

# ─────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# This is sent as the first message in every conversation.
# It sets the AI's identity, rules, and output format.
# ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Python software engineer and coding assistant \
built into an AI-powered coding IDE.

## YOUR JOB
Help users write clean, correct, production-ready Python code.

## OUTPUT RULES — FOLLOW EXACTLY
1. Always wrap ALL code in a single ```python code block.
2. Never split code across multiple code blocks.
3. Write complete, runnable scripts — not fragments or pseudocode.
4. After the code block, write a short explanation (3-6 bullet points).
5. Keep explanations concise — the code speaks for itself.
6. If the user asks a question (not for code), answer clearly in plain text.

## CODE QUALITY RULES
- Add brief comments on non-obvious logic
- Use descriptive variable names
- Handle common errors with try/except where relevant
- Include a main guard: if __name__ == "__main__": where appropriate
- Prefer standard library over third-party when possible
- Write self-contained scripts — use hardcoded example values or input() for any required user input

## WHAT YOU NEVER DO
- Never generate harmful, malicious, or system-damaging code
- Never use placeholder logic like `# TODO implement this`
- Never truncate code with `# ... rest of code`
- Never apologize or add filler phrases like "Certainly!" or "Of course!"
- Never use argparse, sys.argv, or any command-line argument parsing — code runs headlessly with no CLI arguments

## RESPONSE FORMAT EXAMPLE
```python
# Your complete code here
```

**What this does:**
- Point 1
- Point 2
- Point 3
"""


# ─────────────────────────────────────────────────────────────────
# HELPER: Build the full message list sent to the API
# ─────────────────────────────────────────────────────────────────

def build_messages(chat_history: list[dict]) -> list[dict]:
    """
    Prepend the system prompt to the conversation history.
    The Groq API expects this exact format.

    Args:
        chat_history: List of {"role": ..., "content": ...} dicts

    Returns:
        Full message list with system prompt at index 0
    """
    system_message = {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
    return [system_message] + chat_history


# ─────────────────────────────────────────────────────────────────
# HELPER: Extract code block from AI response
# ─────────────────────────────────────────────────────────────────

def extract_code(response: str) -> str:
    """
    Pull the Python code block out of the AI's response.

    The AI wraps code in ```python ... ``` fences.
    We extract just the code, stripping the markdown fences.

    Args:
        response: Full text response from the AI

    Returns:
        Raw Python code string, or empty string if no code found
    """
    # Look for ```python ... ``` block
    if "```python" in response:
        start = response.find("```python") + len("```python")
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    # Fallback: look for plain ``` ... ``` block
    if "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    # No code block found — return empty
    return ""


def extract_explanation(response: str) -> str:
    """
    Extract the explanation text that comes AFTER the code block.

    Args:
        response: Full AI response text

    Returns:
        The explanation portion, or the full response if no code block
    """
    if "```" in response:
        # Find the closing fence of the last code block
        last_fence = response.rfind("```")
        explanation = response[last_fence + 3:].strip()
        return explanation if explanation else ""

    # No code block — the whole response is explanation
    return response.strip()