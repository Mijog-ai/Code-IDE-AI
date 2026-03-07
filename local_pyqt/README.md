# ⚡ AI Coder IDE — Local PyQt6 Version

A desktop AI coding assistant that runs **fully offline** using a local
Qwen2.5-Coder-7B-Instruct model on your GPU.
Alternatively switch to **Groq or OpenRouter** cloud API with one click — no
GPU required in that mode.

---

## Features

- **Offline inference** — Qwen2.5-Coder-7B loaded with 4-bit NF4 quantisation (~3.5 GB VRAM)
- **Live token streaming** — code editor updates as tokens arrive
- **Multi-turn conversation** — AI remembers context across messages
- **Python syntax highlighting** in the built-in editor
- **Auto-install missing packages** before each run (pip auto-install)
- **Matplotlib plot capture** — figures are rendered inline in the output panel
- **Groq / OpenRouter API fallback** — no GPU needed in API mode
- **Python & PHP** language support

---

## Requirements

### Minimum (GPU mode)

| Requirement | Version / Notes |
|-------------|-----------------|
| Python | 3.11.x |
| OS | Windows 10/11 (tested), Linux should work |
| GPU | NVIDIA with ≥ 6 GB VRAM (8 GB recommended) |
| CUDA driver | 12.x or later |
| RAM | ≥ 16 GB system RAM |
| Disk | ~15 GB free (model download) |

### Minimum (API mode only — no GPU)

| Requirement | Notes |
|-------------|-------|
| Python | 3.11.x |
| Groq key | Free at [console.groq.com](https://console.groq.com) |
| OR OpenRouter key | [openrouter.ai/keys](https://openrouter.ai/keys) |

---

## Setup (fresh system)

### 1 — Clone / copy the project

```
Code-IDE-AI/
└── local_pyqt/          ← you are here
    ├── main.py
    ├── local_model.py
    ├── api_client.py
    ├── prompts.py
    ├── code_runner.py
    ├── gui/
    │   ├── main_window.py
    │   └── highlighter.py
    └── requirements.txt
```

### 2 — Create and activate a virtual environment

```bash
# From inside local_pyqt/
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3 — Install PyQt6 and base dependencies

```bash
pip install PyQt6>=6.6.0 transformers>=4.40.0 accelerate>=0.27.0
```

### 4 — Install PyTorch with CUDA support

Choose the command that matches your CUDA driver version.
Check your driver version with: `nvidia-smi`

| CUDA Driver | PyTorch index URL |
|-------------|-------------------|
| 12.8 / 12.9 (RTX 50xx) | `https://download.pytorch.org/whl/cu128` |
| 12.1 (RTX 40xx / 30xx) | `https://download.pytorch.org/whl/cu121` |
| CPU only | standard `pip install torch` |

```bash
# Example: RTX 50xx series (CUDA 12.8/12.9)
pip install torch --index-url https://download.pytorch.org/whl/cu128

# Example: RTX 40xx / 30xx (CUDA 12.1)
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

Verify CUDA is detected:
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Expected: True   NVIDIA GeForce RTX ...
```

### 5 — Install bitsandbytes (required for 4-bit NF4 quantisation)

```bash
pip install bitsandbytes
```

> Without `bitsandbytes` the model falls back to `bfloat16` which uses
> ~14 GB VRAM instead of ~3.5 GB. The app still works but you need a
> high-VRAM GPU or the model will run on CPU (very slow).

### 6 — Download the model

Download **Qwen2.5-Coder-7B-Instruct** from Hugging Face.

**Option A — huggingface-hub (recommended)**

```bash
pip install huggingface_hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='Qwen/Qwen2.5-Coder-7B-Instruct',
    local_dir=r'D:\LLMs\models--Qwen--Qwen2.5-Coder-7B-Instruct',
)
"
```

**Option B — git lfs**

```bash
git lfs install
git clone https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct \
    "D:\LLMs\models--Qwen--Qwen2.5-Coder-7B-Instruct"
```

> Model size: ~15 GB download, ~4 GB in VRAM after 4-bit quantisation.

### 7 — Set the model path in `local_model.py`

Open `local_pyqt/local_model.py` and update line 16:

```python
MODEL_CACHE_PATH = r"D:\LLMs\models--Qwen--Qwen2.5-Coder-7B-Instruct"
```

Change this to wherever you saved the model on **your** system, for example:

```python
MODEL_CACHE_PATH = r"C:\Users\YourName\models\Qwen2.5-Coder-7B-Instruct"
# or on Linux:
MODEL_CACHE_PATH = "/home/yourname/models/Qwen2.5-Coder-7B-Instruct"
```

The path can point to either:
- The HuggingFace cache folder (contains a `snapshots/` subfolder) — auto-detected
- The model directory directly (contains `config.json`, `*.safetensors`, etc.)

### 8 — Run the app

```bash
# Make sure the venv is active
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS

python main.py
```

---

## API Mode (no GPU needed)

If you don't have a compatible GPU, use Groq or OpenRouter instead:

1. Launch the app: `python main.py`
2. Click **☁ Groq / OpenRouter** in the header — the model is **not** loaded
3. Select your provider, paste your API key, pick a model
4. Type a prompt and generate code normally

The **Run Code** button (auto-install + execution) works identically in both modes.

---

## Project Structure

```
local_pyqt/
├── main.py                Entry point — interpreter guard, DLL fix, QApplication
├── local_model.py         Load Qwen2.5-Coder-7B (4-bit NF4 + SDPA + torch.compile)
├── api_client.py          Groq / OpenRouter streaming client (API mode)
├── prompts.py             System prompts for Python & PHP, extract_code()
├── code_runner.py         Import detection, pip auto-install, subprocess execution,
│                          matplotlib plot capture
├── gui/
│   ├── main_window.py     Full PyQt6 UI — layout, workers, signals/slots
│   └── highlighter.py     Python & PHP syntax highlighter (QSyntaxHighlighter)
└── requirements.txt
```

---

## How It Works

### Model loading (local mode)

```
Click "🖥 Local Model"
      ↓
ModelLoaderWorker (QThread)
  1. TF32 enabled (free ~10-30% speedup on Ampere/Ada/Blackwell)
  2. Tokenizer loaded from model path
  3. Model loaded with 4-bit NF4 (bitsandbytes) → ~3.5 GB VRAM
     (fallback: bfloat16 with device_map="auto" if bitsandbytes missing)
  4. torch.compile(mode="reduce-overhead") — CUDA graph caching
      ↓
  Generate button enabled — model ready
```

### Code generation

```
User types prompt → clicks ⚡ Generate Code
      ↓
CodeGeneratorWorker / ApiGeneratorWorker (QThread)
  - Local: model.generate_stream() via TextIteratorStreamer (daemon thread)
  - API:   ApiClient.generate_stream() via SSE / JSON-lines streaming
      ↓
_on_token() → extracts code block → updates editor live
_on_generation_done() → final extract_code() → clean code in editor
```

### Code execution (both modes)

```
User clicks ▶ Run Code
      ↓
CodeRunnerWorker (QThread) → run_python_code()
  1. Scan imports with regex (line-safe [^\n]+ pattern)
  2. pip install any missing packages
  3. Inject matplotlib Agg backend preamble if matplotlib is used
  4. Write code to temp .py file
  5. subprocess.run([sys.executable, tmp.py], timeout=60)
  6. Parse stdout for __PLOT__: markers → load PNGs inline in output panel
  7. Display stdout / stderr with colour coding
```

---

## Configuration

All settings are controlled from the GUI — no config files needed:

| Setting | Where | Notes |
|---------|-------|-------|
| Model path | `local_model.py` line 16 | Change once at setup |
| Mode (Local / API) | Header buttons | Switch anytime |
| API provider | API bar dropdown | Groq or OpenRouter |
| API key | API bar text field | Stored in memory only |
| Language | Code editor toolbar | Python or PHP |
| Temperature / max tokens | (local model) | Hardcoded in `generate_stream()` defaults |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| *"Wrong Python interpreter"* on start | Run via `.venv\Scripts\python.exe main.py` or activate venv first |
| `FileNotFoundError: Model not found` | Update `MODEL_CACHE_PATH` in `local_model.py` |
| `CUDA out of memory` | Install `bitsandbytes` for 4-bit quantisation; or use API mode |
| `torch.cuda.is_available()` returns `False` | Reinstall torch with the correct `--index-url` for your CUDA version |
| `WinError 1114` (DLL init failed) | Already handled by `main.py`'s `_register_torch_dll_dir()` — ensure you start via `python main.py`, not a shortcut that bypasses the entry point |
| First generation is very slow | Normal — `torch.compile` warms up on the first call; subsequent generations are fast |
| `bitsandbytes` install fails on Windows | Try: `pip install bitsandbytes --prefer-binary` |
| App crashes importing PyQt6 | Ensure you installed `PyQt6` (not `PyQt5`) into the correct venv |
