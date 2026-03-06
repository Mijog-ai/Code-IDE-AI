# app.py
import streamlit as st
from dotenv import load_dotenv
from utils.session import init_session_state
from components.chat import render_chat_panel
from components.editor import render_editor_panel

load_dotenv()

# ── Page config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Coder IDE",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-app:        #f5f4ef;
    --bg-sidebar:    #eeece6;
    --bg-panel:      #ffffff;
    --bg-input:      #ffffff;
    --bg-hover:      #f0efe9;
    --accent:        #d97706;
    --accent-light:  #fef3c7;
    --accent-soft:   #fffbeb;
    --text-primary:  #1c1917;
    --text-secondary:#57534e;
    --text-muted:    #a8a29e;
    --border:        #e5e3dc;
    --shadow-sm:     0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md:     0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04);
    --radius:        10px;
}

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.stApp {
    background: var(--bg-app);
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
}

.block-container { padding-top: 1.5rem !important; max-width: 100% !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: var(--text-secondary) !important;
    font-size: 0.85rem !important;
}

/* Panel header */
.panel-header {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--text-muted);
    padding: 0 0 10px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}

/* Chat messages */
.chat-message-user {
    background: var(--accent-light);
    border: 1px solid #fde68a;
    border-radius: var(--radius);
    padding: 12px 16px;
    margin: 10px 0;
    box-shadow: var(--shadow-sm);
}
.chat-message-ai {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 12px 16px;
    margin: 10px 0;
    box-shadow: var(--shadow-sm);
}
.chat-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-family: 'Inter', sans-serif;
}

/* All buttons default */
.stButton > button {
    background: var(--bg-hover) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
    box-shadow: var(--shadow-sm) !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: var(--border) !important;
    transform: none !important;
}

/* Primary send button */
button[kind="primary"],
div[data-testid="column"]:first-child .stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
}
div[data-testid="column"]:first-child .stButton > button:hover {
    background: #b45309 !important;
    box-shadow: var(--shadow-md) !important;
}

/* Run button — full width standalone */
div[data-testid="stVerticalBlock"] > div > div > .stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
}

/* Sidebar example buttons */
[data-testid="stSidebar"] .stButton > button {
    background: var(--bg-panel) !important;
    color: var(--text-secondary) !important;
    border: 1px solid var(--border) !important;
    text-align: left !important;
    font-size: 0.8rem !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--accent-light) !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* Text area */
.stTextArea textarea {
    background: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    box-shadow: var(--shadow-sm) !important;
    transition: border-color 0.15s ease !important;
}
.stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(217,119,6,0.12) !important;
}
.stTextArea textarea::placeholder { color: var(--text-muted) !important; }

/* Select boxes */
.stSelectbox [data-baseweb="select"] > div {
    background: var(--bg-input) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
}

/* Code blocks */
pre, code {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
    background: #fafaf8 !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

.stCaption, small { color: var(--text-muted) !important; font-size: 0.78rem !important; }
hr { border-color: var(--border) !important; opacity: 1 !important; }
</style>
""", unsafe_allow_html=True)

# ── Init session ──────────────────────────────────────────────────
init_session_state(),

# app.py — add this right after init_session_state()
import os

# ── Guard: show setup screen if API key is missing ────────────────
if not os.getenv("GROQ_API_KEY"):
    st.markdown("""
    <div style="
        max-width: 520px;
        margin: 80px auto;
        background: #ffffff;
        border: 1px solid #e5e3dc;
        border-radius: 14px;
        padding: 40px;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.07);
        font-family: 'Inter', sans-serif;
    ">
        <div style="font-size: 2.8rem; margin-bottom: 16px;">⚡</div>
        <h2 style="color:#1c1917; font-size:1.4rem; margin-bottom:8px;">
            API Key Required
        </h2>
        <p style="color:#78716c; font-size:0.9rem; line-height:1.6; margin-bottom:24px;">
            AI Coder IDE needs a <strong>Groq API key</strong> to generate code.
            It's free and takes 30 seconds to set up.
        </p>
        <div style="
            background:#fef3c7;
            border:1px solid #fde68a;
            border-radius:8px;
            padding:16px;
            text-align:left;
            font-family:'JetBrains Mono', monospace;
            font-size:0.8rem;
            color:#92400e;
            line-height:2;
        ">
            1. Visit <strong>console.groq.com</strong><br>
            2. Create a free account &amp; copy your API key<br>
            3. Create a <strong>.env</strong> file in the project root<br>
            4. Add: <strong>GROQ_API_KEY=your_key_here</strong><br>
            5. Restart the app: <strong>streamlit run app.py</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()  # Halt — don't render anything else

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ AI Coder IDE")
    st.markdown("---")
    st.markdown("### 🤖 Model")

    st.session_state.selected_model = st.selectbox(
        "Groq Model",
        ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768"],
        index=0,
    )
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    st.session_state.max_tokens = st.select_slider(
        "Max Tokens", [512, 1024, 2048, 4096, 8192], value=4096
    )

    st.markdown("---")
    st.markdown("### ⌨️ Editor")

    st.session_state.editor_theme = st.selectbox(
        "Theme",
        ["tomorrow", "github", "xcode", "kuroir", "solarized_light"],
        index=0,
    )
    st.session_state.font_size = st.slider("Font Size", 12, 20, 14)

    st.markdown("---")
    st.markdown("### 💡 Examples")

    examples = [
        "Build a snake game in Python",
        "Create a FastAPI REST server",
        "Write a web scraper with requests",
        "Build a CSV analysis script with pandas",
        "Create a CLI todo app with argparse",
        "Write merge sort with explanation",
    ]

    for prompt in examples:
        if st.button(f"▸ {prompt}", key=f"ex_{prompt[:12]}", use_container_width=True):
            st.session_state.pending_prompt = prompt
            st.rerun()

    st.markdown("---")
    st.caption(f"Messages: {len(st.session_state.messages)}")
    st.caption(f"Model: {st.session_state.selected_model}")

# ── Two-column IDE layout ─────────────────────────────────────────
col_chat, col_editor = st.columns([1, 1], gap="large")

with col_chat:
    render_chat_panel()

with col_editor:
    render_editor_panel()