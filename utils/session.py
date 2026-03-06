# utils/session.py
import streamlit as st


def init_session_state():
    """
    Initialize all session state variables with safe defaults.
    Called once at app startup — safe to call multiple times
    because we check before setting (avoids overwriting live state).
    """

    # ── Chat history ──────────────────────────────────────────────
    # List of dicts: [{"role": "user"|"assistant", "content": "..."}]
    # This is the raw history sent to the Groq API each request.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Generated code ────────────────────────────────────────────
    # The most recently extracted Python code block from AI response.
    # This gets loaded into the code editor in Phase 3.
    if "generated_code" not in st.session_state:
        st.session_state.generated_code = ""

    # ── Code execution output ─────────────────────────────────────
    # stdout/stderr from running the code — shown below the editor.
    if "run_output" not in st.session_state:
        st.session_state.run_output = ""

    # ── Run status ────────────────────────────────────────────────
    # "success" | "error" | "" — controls output box color
    if "run_status" not in st.session_state:
        st.session_state.run_status = ""

    # ── Model settings (sidebar will write these) ─────────────────
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "llama-3.3-70b-versatile"

    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.3

    if "max_tokens" not in st.session_state:
        st.session_state.max_tokens = 4096

    # ── Editor settings ───────────────────────────────────────────
    if "editor_theme" not in st.session_state:
        st.session_state.editor_theme = "monokai"

    if "font_size" not in st.session_state:
        st.session_state.font_size = 14

    # ── Pending prompt ────────────────────────────────────────────
    # Set by sidebar example buttons to pre-fill the chat input.
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = ""

    # ── AI thinking flag ─────────────────────────────────────────
    # Prevents double submissions while AI is generating.
    if "is_generating" not in st.session_state:
        st.session_state.is_generating = False


def clear_chat():
    """Reset chat history and all code state."""
    st.session_state.messages = []
    st.session_state.generated_code = ""
    st.session_state.run_output = ""
    st.session_state.run_status = ""


def add_user_message(content: str):
    """Append a user message to chat history."""
    st.session_state.messages.append({
        "role": "user",
        "content": content
    })


def add_assistant_message(content: str):
    """Append an assistant message to chat history."""
    st.session_state.messages.append({
        "role": "assistant",
        "content": content
    })


def get_message_count() -> int:
    """Return total number of messages in chat history."""
    return len(st.session_state.messages)