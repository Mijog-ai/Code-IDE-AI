# prompts.py

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


def get_system_prompt(language: str = "python") -> str:
    """Return the system prompt (always Python)."""
    return SYSTEM_PROMPT


def build_messages(chat_history: list[dict]) -> list[dict]:
    """
    Prepend the system prompt to the conversation history.

    Args:
        chat_history: List of {"role": ..., "content": ...} dicts

    Returns:
        Full message list with system prompt at index 0
    """
    return [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history


def extract_code(response: str, language: str = "python") -> str:
    """
    Pull the code block out of the AI's response.

    Args:
        response: Full text response from the AI
        language: Expected fence language tag (always "python")

    Returns:
        Raw code string, or empty string if no code block found
    """
    if "```python" in response:
        start = response.find("```python") + len("```python")
        end   = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    if "```" in response:
        start = response.find("```") + 3
        newline = response.find("\n", start)
        if newline != -1 and response[start:newline].strip().isalpha():
            start = newline + 1
        end = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    return ""


def extract_explanation(response: str) -> str:
    """
    Extract the explanation text that comes AFTER the code block.

    Returns:
        The explanation portion, or the full response if no code block
    """
    if "```" in response:
        last_fence = response.rfind("```")
        explanation = response[last_fence + 3:].strip()
        return explanation if explanation else ""

    return response.strip()
