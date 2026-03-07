# prompts.py

# ─────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS  (one per supported language)
# Each prompt is sent as the first message in every conversation.
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

## WHAT YOU NEVER DO
- Never generate harmful, malicious, or system-damaging code
- Never use placeholder logic like `# TODO implement this`
- Never truncate code with `# ... rest of code`
- Never apologize or add filler phrases like "Certainly!" or "Of course!"

## RESPONSE FORMAT EXAMPLE
```python
# Your complete code here
```

**What this does:**
- Point 1
- Point 2
- Point 3
"""


PHP_SYSTEM_PROMPT = """You are an expert PHP developer and coding assistant \
built into an AI-powered coding IDE.

## YOUR JOB
Help users write clean, correct, production-ready PHP code.

## OUTPUT RULES — FOLLOW EXACTLY
1. Always wrap ALL code in a single ```php code block.
2. Never split code across multiple code blocks.
3. Write complete, runnable scripts — not fragments or pseudocode.
4. Start every script with the <?php opening tag.
5. After the code block, write a short explanation (3-6 bullet points).
6. Keep explanations concise — the code speaks for itself.
7. If the user asks a question (not for code), answer clearly in plain text.

## CODE QUALITY RULES
- Add brief comments on non-obvious logic
- Use descriptive variable names
- Handle errors with try/catch blocks where relevant
- Use modern PHP 8+ syntax (named arguments, match, fibers, enums) where appropriate
- Use strict typing: declare(strict_types=1); at the top

## WHAT YOU NEVER DO
- Never generate harmful, malicious, or system-damaging code
- Never use placeholder logic like `// TODO implement this`
- Never truncate code with `// ... rest of code`
- Never apologize or add filler phrases like "Certainly!" or "Of course!"

## RESPONSE FORMAT EXAMPLE
```php
<?php
declare(strict_types=1);
// Your complete code here
```

**What this does:**
- Point 1
- Point 2
- Point 3
"""


# ─────────────────────────────────────────────────────────────────
# Language-aware system prompt selector
# ─────────────────────────────────────────────────────────────────

_PROMPTS: dict[str, str] = {
    "python": SYSTEM_PROMPT,
    "php":    PHP_SYSTEM_PROMPT,
}


def get_system_prompt(language: str = "python") -> str:
    """Return the correct system prompt for the given programming language."""
    return _PROMPTS.get(language.lower(), SYSTEM_PROMPT)


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

def extract_code(response: str, language: str = "python") -> str:
    """
    Pull the code block out of the AI's response.

    The AI wraps code in ```<language> ... ``` fences (e.g. ```python, ```php).
    We extract just the code, stripping the markdown fences.

    Args:
        response: Full text response from the AI
        language: Expected fence language tag ("python", "php", …)

    Returns:
        Raw code string, or empty string if no code block found
    """
    # 1. Try language-specific fence first (e.g. ```php)
    fence = f"```{language.lower()}"
    if fence in response:
        start = response.find(fence) + len(fence)
        end   = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    # 2. Fallback: try ```python (common even when asking for another language)
    if "```python" in response:
        start = response.find("```python") + len("```python")
        end   = response.find("```", start)
        if end != -1:
            return response[start:end].strip()

    # 3. Plain ``` fence (no language tag)
    if "```" in response:
        start = response.find("```") + 3
        # Skip any inline language tag on the opening line
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