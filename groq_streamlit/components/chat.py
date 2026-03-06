# components/chat.py
import streamlit as st
from groq_client import stream_response
from prompts import extract_code, extract_explanation
from utils.session import add_user_message, add_assistant_message


def render_message(role: str, content: str):
    if role == "user":
        st.markdown(
            f"""
            <div class="chat-message-user">
                <div class="chat-label" style="color:#d97706;">You</div>
                <div style="color:#1c1917; font-size:0.9rem; line-height:1.6;">{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        explanation = extract_explanation(content)
        display_text = explanation if explanation else content

        st.markdown(
            f"""
            <div class="chat-message-ai">
                <div class="chat-label" style="color:#78716c;">AI Coder</div>
                <div style="color:#1c1917; font-size:0.9rem; line-height:1.6;">{display_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_panel():
    """
    Render the full left-side chat panel.
    Includes: header, message history, input box, submit logic.
    """

    # ── Panel header ──────────────────────────────────────────────
    st.markdown(
        '<div class="panel-header">💬 &nbsp; CHAT ASSISTANT</div>',
        unsafe_allow_html=True
    )

    # ── Chat history display ──────────────────────────────────────
    # Scrollable container for all past messages
    chat_container = st.container(height=480)

    with chat_container:
        if not st.session_state.messages:
            # Empty state — show a welcome prompt
            # Empty state
            st.markdown(
                """
                <div style="
                    text-align: center;
                    padding: 60px 20px;
                    color: #c4b89a;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.875rem;
                ">
                    <div style="font-size: 2.5rem; margin-bottom: 14px;">✦</div>
                    <div style="font-weight: 500; color: #78716c;">Ask me to build anything in Python.</div>
                    <div style="margin-top: 8px; font-size: 0.78rem; color: #a8a29e;">
                        Try: "build a snake game" or "create a REST API"
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            # Render each message in order
            for msg in st.session_state.messages:
                render_message(msg["role"], msg["content"])

    # ── Message stats ─────────────────────────────────────────────
    msg_count = len(st.session_state.messages)
    if msg_count > 0:
        turns = msg_count // 2
        st.caption(f"🗨️ {turns} exchange{'s' if turns != 1 else ''} · {msg_count} messages")

    # ── Chat input area ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    # Check if a sidebar example button set a pending prompt
    default_value = st.session_state.get("pending_prompt", "")

    user_input = st.text_area(
        label="Your request",
        value=default_value,
        placeholder='e.g. "build a snake game in Python" or "create a FastAPI server"',
        height=100,
        key="chat_input",
        label_visibility="collapsed",
    )

    # Clear the pending prompt after it's been loaded into the input
    if default_value:
        st.session_state.pending_prompt = ""

    # ── Action buttons ────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns([3, 1])

    with btn_col1:
        send_clicked = st.button(
            "⚡ Generate Code",
            use_container_width=True,
            disabled=st.session_state.is_generating,
        )

    with btn_col2:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.messages = []
            st.session_state.generated_code = ""
            st.session_state.run_output = ""
            st.session_state.run_status = ""
            st.rerun()

    # ── Handle submission ─────────────────────────────────────────
    if send_clicked and user_input.strip():
        handle_submission(user_input.strip())


def handle_submission(user_input: str):
    """
    Process a user message:
    1. Add user message to history
    2. Stream AI response token by token
    3. Extract and store code from the response
    4. Add full AI response to history
    """

    # Prevent double-clicks during generation
    st.session_state.is_generating = True

    # Save the user message into chat history
    add_user_message(user_input)

    # Stream the AI response with a live typing effect
    with st.spinner("⚡ AI is generating code..."):
        try:
            full_response = ""

            # stream_response is a generator — we collect all chunks
            for chunk in stream_response(
                chat_history=st.session_state.messages,
                model=st.session_state.selected_model,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens,
            ):
                full_response += chunk

            # Save the complete AI response to chat history
            add_assistant_message(full_response)

            # Extract code block and store it for the editor panel
            code = extract_code(full_response)
            if code:
                st.session_state.generated_code = code
                # Clear previous run output when new code arrives
                st.session_state.run_output = ""
                st.session_state.run_status = ""

        except ValueError as e:
            # API key not configured
            st.error(f"⚙️ Configuration error: {e}")

        except Exception as e:
            # Any other API error
            st.error(f"❌ Error: {str(e)}")

    # Allow submissions again
    st.session_state.is_generating = False

    # Rerun to refresh the chat display with new messages
    st.rerun()