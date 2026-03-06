# groq_client.py
import os
from groq import Groq
from dotenv import load_dotenv
from prompts import build_messages

load_dotenv()


def get_client() -> Groq:
    """
    Create and return a Groq client.
    Raises a clear ValueError if the API key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found!\n"
            "1. Copy .env.example → .env\n"
            "2. Add your key from https://console.groq.com"
        )

    return Groq(api_key=api_key)


def generate_response(
    chat_history: list[dict],
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    Send full conversation history to Groq and get a complete response.

    Args:
        chat_history: List of user/assistant messages so far
        model: Which Groq model to use
        temperature: 0.0 = focused/deterministic, 1.0 = creative
        max_tokens: Max length of the response

    Returns:
        The assistant's full response as a string
    """
    client = get_client()

    # Prepend system prompt to chat history
    messages = build_messages(chat_history)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


def stream_response(
    chat_history: list[dict],
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.3,
    max_tokens: int = 4096,
):
    """
    Stream a response from Groq token by token.
    Used for the live-typing effect in the chat UI.

    Yields:
        Text chunks (strings) as they arrive from the API
    """
    client = get_client()
    messages = build_messages(chat_history)

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,   # ← enables streaming mode
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


# ── Quick connection test (run this file directly) ───────────────
if __name__ == "__main__":
    print("Testing Groq API connection...")
    try:
        result = generate_response(
            chat_history=[{"role": "user", "content": "Reply with: CONNECTION OK"}],
            model="openai/gpt-oss-120b",
            max_tokens=20,
        )
        print(f"✅ Groq API working! Response: {result}")
    except ValueError as e:
        print(f"❌ Config error: {e}")
    except Exception as e:
        print(f"❌ API error: {e}")