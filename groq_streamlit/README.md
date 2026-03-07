# ⚡ AI Coder IDE — Groq / Streamlit Version

A browser-based AI coding assistant powered by the **Groq cloud API**.
Type a prompt, get complete runnable code, edit it in the built-in editor,
and execute it — all in one page.

---

## Features

- **Streaming code generation** via Groq (tokens appear live as they arrive)
- **Multi-turn conversation** — the AI remembers context across messages
- **ACE code editor** with syntax highlighting and multiple themes
- **Auto-install missing packages** before each run (pip auto-install)
- **Subprocess execution** with stdout / stderr capture
- Sidebar model selector, temperature, max-tokens, and editor-theme controls

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.11.x (recommended) |
| OS | Windows / macOS / Linux |
| Groq API key | Free at [console.groq.com](https://console.groq.com) |

> No GPU needed — all inference runs on Groq's servers.

---

## Setup (fresh system)

### 1 — Clone / copy the project

```
Code-IDE-AI/
└── groq_streamlit/      ← you are here
    ├── app.py
    ├── groq_client.py
    ├── prompts.py
    ├── code_runner.py
    ├── components/
    │   ├── chat.py
    │   └── editor.py
    ├── utils/
    │   └── session.py
    └── requirements.txt
```

### 2 — Create and activate a virtual environment

```bash
# From inside groq_streamlit/
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` installs:

```
streamlit==1.35.0
groq==0.9.0
streamlit-ace==0.1.1
python-dotenv==1.0.1
```

### 4 — Create the `.env` file

Create a file named `.env` **inside the `groq_streamlit/` folder**:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get your free key at → **https://console.groq.com/keys**

> If the key is missing the app will show a setup screen instead of the IDE.

### 5 — Run the app

```bash
streamlit run app.py
```

The browser opens automatically at **http://localhost:8501**

---

## Available Models (sidebar)

| Model | Notes |
|-------|-------|
| `llama-3.3-70b-versatile` | Best quality, default |
| `llama3-70b-8192` | Fast, large context |
| `llama3-8b-8192` | Fastest, smaller |
| `mixtral-8x7b-32768` | Very long context |

---

## Project Structure

```
groq_streamlit/
├── app.py                 Main entry point — Streamlit page layout + sidebar
├── groq_client.py         Groq API wrapper — streaming + non-streaming calls
├── prompts.py             System prompt, extract_code(), extract_explanation()
├── code_runner.py         Import detection, auto-install, subprocess execution
├── components/
│   ├── chat.py            Chat panel UI — message list, input form, streaming
│   └── editor.py          ACE code editor UI — run button, output box
├── utils/
│   └── session.py         Streamlit session-state initialisation helpers
├── requirements.txt
└── .env                   ← you create this (not committed to git)
```

---

## How It Works

```
User types prompt
      ↓
chat.py  →  groq_client.stream_response()  →  Groq API (streaming)
      ↓
Accumulate tokens → extract ```python...``` block → show in ACE editor
      ↓
User clicks ▶ Run Code
      ↓
code_runner.run_python_code()
  1. Scan imports with regex
  2. pip install any missing packages
  3. Write code to temp .py file
  4. subprocess.run([sys.executable, tmp.py])
  5. Capture stdout / stderr → display in coloured box
```

---

## Configuration

All settings are in the **sidebar** at runtime — no config files needed:

| Setting | Default | Description |
|---------|---------|-------------|
| Model | `llama-3.3-70b-versatile` | Groq model to use |
| Temperature | 0.3 | Creativity (0 = deterministic) |
| Max Tokens | 4096 | Maximum response length |
| Editor Theme | `tomorrow` | ACE editor colour scheme |
| Font Size | 14 | Editor font size (px) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| *"API Key Required"* screen | Create `groq_streamlit/.env` with `GROQ_API_KEY=...` |
| `ModuleNotFoundError: streamlit` | Activate the venv: `.venv\Scripts\activate` |
| Packages not auto-installed | The venv must be active when running the app |
| Browser doesn't open | Navigate manually to http://localhost:8501 |
| `RateLimitError` from Groq | Free tier has rate limits — wait a few seconds |
