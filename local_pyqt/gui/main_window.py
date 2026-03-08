# gui/main_window.py
# Main PyQt6 window for the local-model AI Coder IDE.
#
# Layout (horizontal splitter):
#   LEFT  — prompt input, Generate button, conversation history
#   RIGHT — code editor (syntax-highlighted), Run button, output/log panel
#   BOTTOM — step-by-step progress bar + status label

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.highlighter import PythonHighlighter

# ── Design tokens ────────────────────────────────────────────────
ACCENT      = "#d97706"
BG_APP      = "#f5f4ef"
BG_PANEL    = "#ffffff"
BG_CODE     = "#fafaf8"
BORDER      = "#e5e3dc"
TEXT_PRI    = "#1c1917"
TEXT_SEC    = "#57534e"
TEXT_MUTED  = "#a8a29e"
GREEN       = "#16a34a"
RED         = "#dc2626"

# ── Language display name → internal key ─────────────────────────
# Internal key must match LANGUAGE_CONFIG in code_runner.py and
# the _PROMPTS dict in prompts.py.
_LANG_DISPLAY_MAP: dict[str, str] = {
    "python":           "python",
    "php":              "php",
    "c# / asp.net":     "csharp",
    "kotlin":           "kotlin",
    "flutter / dart":   "dart",
    "visual foxpro":    "foxpro",
}

# Internal key → file extension (for editor placeholder)
_LANG_EXT: dict[str, str] = {
    "python":  ".py",
    "php":     ".php",
    "csharp":  ".csx",
    "kotlin":  ".kts",
    "dart":    ".dart",
    "foxpro":  ".prg",
}

# Internal key → comment prefix (for editor placeholder text)
_LANG_COMMENT: dict[str, str] = {
    "python":  "#",
    "php":     "//",
    "csharp":  "//",
    "kotlin":  "//",
    "dart":    "//",
    "foxpro":  "*",
}

APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {BG_APP};
    font-family: "Segoe UI", Inter, sans-serif;
    color: {TEXT_PRI};
    font-size: 13px;
}}

QTextEdit, QPlainTextEdit {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    color: {TEXT_PRI};
    selection-background-color: #fde68a;
    selection-color: {TEXT_PRI};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}

QPushButton {{
    background-color: #f0efe9;
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 13px;
    min-height: 30px;
}}
QPushButton:hover  {{ background-color: {BORDER}; }}
QPushButton:pressed {{ background-color: #d1cdc6; }}
QPushButton:disabled {{
    background-color: #e9e7e0;
    color: {TEXT_MUTED};
}}

QPushButton#generateBtn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-weight: 700;
    font-size: 14px;
    min-height: 40px;
    border-radius: 10px;
}}
QPushButton#generateBtn:hover   {{ background-color: #b45309; }}
QPushButton#generateBtn:pressed {{ background-color: #92400e; }}
QPushButton#generateBtn:disabled {{
    background-color: #fde68a;
    color: #92400e;
}}

QPushButton#runBtn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    min-height: 36px;
    border-radius: 9px;
}}
QPushButton#runBtn:hover   {{ background-color: #b45309; }}
QPushButton#runBtn:pressed {{ background-color: #92400e; }}
QPushButton#runBtn:disabled {{
    background-color: #fde68a;
    color: #92400e;
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 7px;
    background-color: #ece9e1;
    height: 22px;
    text-align: center;
    color: {TEXT_SEC};
    font-size: 12px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 6px;
}}

QLabel {{ color: {TEXT_PRI}; background: transparent; }}
QLabel#sectionLabel {{
    font-size: 10px;
    font-weight: 700;
    color: {TEXT_MUTED};
    letter-spacing: 1.5px;
    padding-bottom: 2px;
}}
QLabel#statusLabel {{
    font-size: 11px;
    color: {TEXT_SEC};
}}

QSplitter::handle {{
    background-color: {BORDER};
    width: 6px;
    height: 6px;
}}
QSplitter::handle:hover {{
    background-color: {ACCENT};
}}
QFrame#sep {{
    background-color: {BORDER};
    max-height: 1px;
    min-height: 1px;
}}
"""


# ─────────────────────────────────────────────────────────────────
# Background worker threads
# ─────────────────────────────────────────────────────────────────

class ModelLoaderWorker(QThread):
    """Loads the LocalModel in a background thread."""
    progress = pyqtSignal(str)   # status text
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def run(self) -> None:
        try:
            from local_model import get_model
            model = get_model()
            if not model.is_loaded:
                model.load(progress_cb=lambda msg: self.progress.emit(msg))
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class CodeGeneratorWorker(QThread):
    """
    Runs model.generate_stream() in a background thread.

    Streaming tokens are emitted one at a time so the GUI can
    update the code editor in real time without blocking.
    Progress advances from 10 % → 60 % while tokens arrive,
    then jumps to 60 % when generation is complete.
    """
    progress = pyqtSignal(int, str)   # (percent, message)
    token    = pyqtSignal(str)         # one streaming chunk
    finished = pyqtSignal(str)         # full response text
    error    = pyqtSignal(str)

    def __init__(self, messages: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.messages = messages

    def run(self) -> None:
        try:
            from local_model import get_model
            model = get_model()

            self.progress.emit(10, "Preparing prompt…")

            full_response = ""
            token_count   = 0

            self.progress.emit(20, "Generating code…")

            for chunk in model.generate_stream(self.messages):
                full_response += chunk
                token_count   += 1
                self.token.emit(chunk)

                # Smoothly advance progress bar 20 % → 58 %
                # (assumes ~500 tokens average response)
                if token_count % 8 == 0:
                    pct = min(58, 20 + int(token_count / 500 * 38))
                    self.progress.emit(pct, "Generating code…")

            self.progress.emit(60, "Code generation complete.")
            self.finished.emit(full_response)

        except Exception as exc:
            self.error.emit(str(exc))


class ApiGeneratorWorker(QThread):
    """
    Streams tokens from Groq or OpenRouter in a background thread.
    Drop-in replacement for CodeGeneratorWorker when API mode is active.
    """
    progress = pyqtSignal(int, str)
    token    = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(
        self,
        messages:  list[dict],
        provider:  str,
        api_key:   str,
        model:     str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.messages  = messages
        self.provider  = provider
        self.api_key   = api_key
        self.model     = model

    def run(self) -> None:
        try:
            from api_client import ApiClient
            client = ApiClient(self.provider, self.api_key, self.model)

            self.progress.emit(10, f"Connecting to {self.provider}…")
            full_response = ""
            token_count   = 0
            self.progress.emit(20, f"Generating via {self.provider} · {self.model}…")

            for chunk in client.generate_stream(self.messages):
                full_response += chunk
                token_count   += 1
                self.token.emit(chunk)
                if token_count % 8 == 0:
                    pct = min(58, 20 + int(token_count / 500 * 38))
                    self.progress.emit(pct, f"Generating via {self.provider}…")

            self.progress.emit(60, "Generation complete.")
            self.finished.emit(full_response)

        except Exception as exc:
            self.error.emit(str(exc))


class ModelFetchWorker(QThread):
    """
    Fetches the live list of models from the selected provider API.
    Emits `finished` with the list on success, `error` with a message on failure.
    """
    finished = pyqtSignal(list)   # list[str] of model IDs
    error    = pyqtSignal(str)

    def __init__(self, provider: str, api_key: str, parent=None) -> None:
        super().__init__(parent)
        self.provider = provider
        self.api_key  = api_key

    def run(self) -> None:
        try:
            from api_client import ApiClient
            client = ApiClient(self.provider, self.api_key)
            models = client.get_models()
            self.finished.emit(models)
        except Exception as exc:
            self.error.emit(str(exc))


class CodeRunnerWorker(QThread):
    """
    Step-by-step pipeline delegated entirely to run_python_code():
      10 %           — Checking dependencies
      10 % → 65 %   — Installing missing packages (progress via callback)
      70 %           — Executing code
     100 %           — Done / Failed
    """
    progress = pyqtSignal(int, str)   # (percent, message)
    log      = pyqtSignal(str)        # incremental log line
    finished = pyqtSignal(object)     # RunResult dataclass
    error    = pyqtSignal(str)

    def __init__(self, code: str, language: str = "python", parent=None) -> None:
        super().__init__(parent)
        self.code     = code
        self.language = language
        self._install_count  = 0
        self._install_total  = 0

    def run(self) -> None:
        try:
            from code_runner import (
                extract_imports, resolve_pip_name,
                is_package_installed, STDLIB_MODULES,
                run_python_code,
            )

            if self.language == "python":
                # Pre-scan so we know how many packages to install for progress calc
                imports = extract_imports(self.code)
                missing = [
                    resolve_pip_name(m) for m in imports
                    if m not in STDLIB_MODULES and not is_package_installed(m)
                ]
                self._install_total = len(missing)
                self._install_count = 0

                self.progress.emit(10, "Checking dependencies…")
                if missing:
                    self.progress.emit(15, f"Found {len(missing)} missing package(s): {', '.join(missing)}")
                    self.log.emit(f"[!] Missing packages: {', '.join(missing)}")
                else:
                    self.log.emit("✓ All dependencies already satisfied.")
            else:
                # Non-Python: skip dependency check
                self._install_total = 0
                self.progress.emit(10, f"Preparing {self.language.upper()} code…")
                self.log.emit(f"Running {self.language.upper()} code…")

            # ── Hand off the full pipeline to run_python_code ────
            def _progress_cb(msg: str) -> None:
                msg_l = msg.lower()
                if "installing" in msg_l and "[pkg]" in msg_l:
                    self._install_count += 1
                    n = max(self._install_total, 1)
                    pct = 15 + int(self._install_count / n * 50)
                    self.progress.emit(pct, msg)
                elif "✓" in msg or "✗" in msg:
                    self.progress.emit(self.progress_bar_value(), msg)
                elif "executing" in msg_l:
                    self.progress.emit(70, msg)
                elif "satisfied" in msg_l or "all dep" in msg_l:
                    self.progress.emit(40, msg)
                self.log.emit(msg)

            result = run_python_code(
                self.code, timeout=60,
                progress_cb=_progress_cb, language=self.language,
            )

            done_msg = "✓ Execution complete." if result.success else "✗ Execution failed."
            self.progress.emit(100, done_msg)
            self.finished.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))

    def progress_bar_value(self) -> int:
        """Return current progress bar value safely from this thread."""
        n = max(self._install_total, 1)
        return 15 + int(self._install_count / n * 50)


class RuntimeInstallerWorker(QThread):
    """
    Installs a language runtime (e.g. Dart SDK, Kotlin, dotnet-script)
    using winget in a background thread.

    Signals:
        progress(str)         — incremental log line
        finished(bool, str)   — (success, full_log)
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)   # success, log

    def __init__(self, language: str, parent=None) -> None:
        super().__init__(parent)
        self.language = language

    def run(self) -> None:
        try:
            from code_runner import install_runtime
            success, log = install_runtime(
                self.language,
                progress_cb=lambda msg: self.progress.emit(msg),
            )
            self.finished.emit(success, log)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ─────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("⚡ AI Coder IDE — Local Model")
        self.resize(1440, 880)
        self.setMinimumSize(960, 640)

        # State
        self._chat_history: list[dict] = []
        self._is_generating  = False
        self._is_running     = False
        self._model_loaded   = False
        self._streamed_buf   = ""

        # API mode state  (set BEFORE _build_ui so widgets can read them)
        self._mode         = ""        # "" | "local" | "api"  — none selected at start
        self._model_loading = False    # True while ModelLoaderWorker is running
        self._api_provider = "Groq"
        self._api_key      = ""
        self._api_model    = ""

        # Language selector state
        self._language     = "python"  # "python" | "php"

        self._build_ui()
        self.setStyleSheet(APP_STYLE)

    # ─────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(12, 10, 12, 8)
        root_lay.setSpacing(8)

        # Header
        root_lay.addWidget(self._make_header())
        root_lay.addWidget(self._sep())

        # API config bar (hidden until API mode is selected)
        self._api_bar = self._build_api_bar()
        root_lay.addWidget(self._api_bar)

        # Left / right panels in a splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([440, 960])
        root_lay.addWidget(splitter, 1)

        # Progress section
        root_lay.addWidget(self._sep())
        root_lay.addWidget(self._build_progress_section())

        self.statusBar().showMessage("Select a mode to begin.")

    def _make_header(self) -> QWidget:
        w   = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(8)

        title = QLabel("⚡  AI Coder IDE")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {TEXT_PRI};"
        )
        lay.addWidget(title)

        # Subtitle changes when mode switches
        self.header_sub_lbl = QLabel(
            "Select a mode to begin"
        )
        self.header_sub_lbl.setStyleSheet(
            f"font-size: 11px; color: {TEXT_MUTED}; margin-left: 8px;"
        )
        lay.addWidget(self.header_sub_lbl)

        lay.addStretch()

        # ── Mode toggle buttons ──────────────────────────────────────
        self.btn_mode_local = QPushButton("🖥  Local Model")
        self.btn_mode_local.setFixedHeight(30)
        self.btn_mode_local.clicked.connect(lambda: self._switch_mode("local"))
        lay.addWidget(self.btn_mode_local)

        self.btn_mode_api = QPushButton("☁  Groq / OpenRouter")
        self.btn_mode_api.setFixedHeight(30)
        self.btn_mode_api.clicked.connect(lambda: self._switch_mode("api"))
        lay.addWidget(self.btn_mode_api)

        # Apply initial button styles
        self._refresh_mode_buttons()

        self.model_status_lbl = QLabel("● No mode selected")
        self.model_status_lbl.setStyleSheet(
            f"font-size: 12px; color: {TEXT_MUTED}; margin-left: 12px;"
        )
        lay.addWidget(self.model_status_lbl)

        return w

    def _build_api_bar(self) -> QWidget:
        """
        Collapsible configuration bar shown only when API mode is active.

        ┌─ Provider ──┬─ API Key ──────────────────────┬─ Model ──────────────────────┬─────────┐
        │  [Groq ▼]  │  [●●●●●●●●●●●●●●●●●●●●●●●]   │  [qwen-2.5-coder-32b ▼]     │ Fetch ↺ │
        └─────────────┴────────────────────────────────┴──────────────────────────────┴─────────┘
        """
        bar = QWidget()
        bar.setStyleSheet(
            f"QWidget {{ background-color: {BG_PANEL}; "
            f"border: 1px solid {BORDER}; border-radius: 8px; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(10)

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet(
                f"color: {TEXT_SEC}; font-size: 12px; font-weight: 600;"
                " background: transparent; border: none;"
            )
            return l

        # ── Provider ─────────────────────────────────────────────
        lay.addWidget(_lbl("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.setFixedWidth(130)
        self.provider_combo.setFixedHeight(28)
        lay.addWidget(self.provider_combo)

        # ── API Key ──────────────────────────────────────────────
        lay.addWidget(_lbl("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Paste Groq / OpenRouter key here…")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setFixedHeight(28)
        self.api_key_input.setMinimumWidth(200)
        lay.addWidget(self.api_key_input, 1)

        # ── Model combo (editable for custom model names) ─────────
        lay.addWidget(_lbl("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)      # user can type a custom ID
        self.model_combo.setFixedHeight(28)
        self.model_combo.setMinimumWidth(280)
        lay.addWidget(self.model_combo, 2)

        # ── Fetch Models button ───────────────────────────────────
        self.fetch_models_btn = QPushButton("↺  Fetch Models")
        self.fetch_models_btn.setFixedHeight(28)
        self.fetch_models_btn.setToolTip(
            "Load the live model list from the selected provider API"
        )
        self.fetch_models_btn.clicked.connect(self._on_fetch_models)
        lay.addWidget(self.fetch_models_btn)

        # Populate provider list and default model list now that
        # model_combo exists (important: connect signals AFTER initial fill)
        from api_client import PROVIDERS
        self.provider_combo.addItems(list(PROVIDERS.keys()))
        self._populate_models(self.provider_combo.currentText())

        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.api_key_input.textChanged.connect(self._on_api_key_changed)

        bar.setVisible(False)   # hidden until API mode is selected
        return bar

    # ── Left panel ───────────────────────────────────────────────

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        lay   = QVBoxLayout(panel)
        lay.setContentsMargins(0, 4, 4, 0)
        lay.setSpacing(6)

        # ── Vertical splitter: prompt area (top) / history (bottom) ─
        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.setChildrenCollapsible(False)
        vsplit.setHandleWidth(8)

        # ─── Top pane: prompt input + Generate button ─────────────
        top_pane = QWidget()
        top_lay  = QVBoxLayout(top_pane)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)

        top_lay.addWidget(self._section_label("PROMPT"))

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            'e.g. "build a snake game" or "create a FastAPI REST server"'
        )
        top_lay.addWidget(self.prompt_input, 1)

        self.generate_btn = QPushButton("⚡  Generate Code")
        self.generate_btn.setObjectName("generateBtn")
        self.generate_btn.setEnabled(False)   # enabled once model loads
        self.generate_btn.clicked.connect(self._on_generate)
        top_lay.addWidget(self.generate_btn)

        vsplit.addWidget(top_pane)

        # ─── Bottom pane: conversation history + Clear button ─────
        bot_pane = QWidget()
        bot_lay  = QVBoxLayout(bot_pane)
        bot_lay.setContentsMargins(0, 4, 0, 0)
        bot_lay.setSpacing(4)

        bot_lay.addWidget(self._sep())
        bot_lay.addWidget(self._section_label("CONVERSATION"))

        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setPlaceholderText(
            "Your conversation history will appear here…"
        )
        bot_lay.addWidget(self.history_display, 1)

        clear_btn = QPushButton("🗑  Clear Conversation")
        clear_btn.clicked.connect(self._clear_chat)
        bot_lay.addWidget(clear_btn)

        vsplit.addWidget(bot_pane)

        # Default split: ~30 % prompt, ~70 % history
        vsplit.setSizes([220, 520])

        lay.addWidget(vsplit, 1)

        return panel

    # ── Right panel ──────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        lay   = QVBoxLayout(panel)
        lay.setContentsMargins(4, 4, 0, 0)
        lay.setSpacing(6)

        # ── Top toolbar (always visible, outside the splitter) ────
        toolbar    = QHBoxLayout()
        toolbar.addWidget(self._section_label("CODE EDITOR"))
        toolbar.addStretch()

        # Language selector — replaces the old static "Python 3" badge
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "Python", "PHP", "C# / ASP.NET", "Kotlin", "Flutter / Dart",
            "Visual FoxPro",
        ])
        self.lang_combo.setFixedHeight(26)
        self.lang_combo.setFixedWidth(150)
        self.lang_combo.setStyleSheet(
            f"QComboBox {{"
            f"  background-color: #fef3c7; color: {ACCENT};"
            f"  border: 1px solid #fde68a; border-radius: 6px;"
            "  padding: 2px 4px 2px 10px; font-size: 11px; font-weight: 600;"
            "}"
            f"QComboBox:hover {{ background-color: #fde68a; }}"
            "QComboBox::drop-down {"
            "  subcontrol-origin: padding; subcontrol-position: top right;"
            "  width: 20px; border: none;"
            "  border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
            "}"
            f"QComboBox::down-arrow {{"
            f"  border-left:  4px solid transparent;"
            f"  border-right: 4px solid transparent;"
            f"  border-top:   5px solid {ACCENT};"
            f"  width: 0; height: 0;"
            f"}}"
            f"QComboBox QAbstractItemView {{"
            f"  background-color: {BG_PANEL}; color: {TEXT_PRI};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            "  selection-background-color: #fde68a;"
            f"  selection-color: {TEXT_PRI}; padding: 2px;"
            f"}}"
        )
        self.lang_combo.currentTextChanged.connect(self._on_language_changed)
        toolbar.addWidget(self.lang_combo)

        copy_btn = QPushButton("⎘ Copy")
        copy_btn.clicked.connect(self._copy_code)
        toolbar.addWidget(copy_btn)

        clear_editor_btn = QPushButton("✕ Clear")
        clear_editor_btn.clicked.connect(self._clear_editor)
        toolbar.addWidget(clear_editor_btn)

        toolbar_w = QWidget()
        toolbar_w.setLayout(toolbar)
        lay.addWidget(toolbar_w)

        # ── Vertical splitter: code editor (top) / output (bottom) ─
        # Both panes are freely resizable by dragging the handle.
        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.setChildrenCollapsible(False)
        vsplit.setHandleWidth(8)

        # ─── Top pane: code editor + Run button ───────────────────
        top_pane = QWidget()
        top_lay  = QVBoxLayout(top_pane)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setPlaceholderText(
            "# Generated code will appear here…\n"
            "# You can edit it before running."
        )
        mono = QFont("Consolas", 12)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(mono)
        self.code_editor.setStyleSheet(
            f"background-color: {BG_CODE}; border: 1px solid {BORDER};"
            "border-radius: 8px; padding: 8px;"
        )
        self._highlighter = PythonHighlighter(self.code_editor.document())
        top_lay.addWidget(self.code_editor, 1)

        self.run_btn = QPushButton("▶  Run Code")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self._on_run)
        top_lay.addWidget(self.run_btn)

        # Warning shown when the selected language runtime is not on PATH
        self.runtime_warn_lbl = QLabel("")
        self.runtime_warn_lbl.setStyleSheet(
            f"color: {RED}; font-size: 11px; padding: 1px 0;"
        )
        self.runtime_warn_lbl.setWordWrap(True)
        self.runtime_warn_lbl.setVisible(False)
        top_lay.addWidget(self.runtime_warn_lbl)

        vsplit.addWidget(top_pane)

        # ─── Bottom pane: output / logs ───────────────────────────
        bot_pane = QWidget()
        bot_lay  = QVBoxLayout(bot_pane)
        bot_lay.setContentsMargins(0, 4, 0, 0)
        bot_lay.setSpacing(4)

        bot_lay.addWidget(self._sep())
        bot_lay.addWidget(self._section_label("OUTPUT / LOGS"))

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText(
            "Execution output and logs will appear here…"
        )
        mono2 = QFont("Consolas", 11)
        mono2.setStyleHint(QFont.StyleHint.Monospace)
        self.output_display.setFont(mono2)
        bot_lay.addWidget(self.output_display, 1)

        vsplit.addWidget(bot_pane)

        # Default split: ~65 % editor, ~35 % output
        vsplit.setSizes([480, 260])

        lay.addWidget(vsplit, 1)

        return panel

    # ── Progress section ─────────────────────────────────────────

    def _build_progress_section(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        lay.addWidget(self.progress_bar)

        self.progress_lbl = QLabel("Ready")
        self.progress_lbl.setObjectName("statusLabel")
        self.progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.progress_lbl)

        return w

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionLabel")
        return lbl

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setObjectName("sep")
        f.setFrameShape(QFrame.Shape.HLine)
        return f

    def _set_progress(self, pct: int, msg: str) -> None:
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{msg}  ({pct} %)")
        self.progress_lbl.setText(msg)

    def _append_history(self, sender: str, text: str, is_user: bool) -> None:
        cursor = self.history_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt_label = QTextCharFormat()
        fmt_label.setFontWeight(700)
        fmt_label.setForeground(QColor(ACCENT if is_user else TEXT_SEC))

        fmt_text = QTextCharFormat()
        fmt_text.setForeground(QColor(TEXT_PRI))
        fmt_text.setFontWeight(400)

        if self.history_display.toPlainText():
            cursor.insertText("\n\n")

        cursor.insertText(f"{sender}\n", fmt_label)
        cursor.insertText(text, fmt_text)

        self.history_display.setTextCursor(cursor)
        self.history_display.ensureCursorVisible()

    def _append_output(self, text: str, *, is_error: bool = False) -> None:
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(RED if is_error else TEXT_PRI))

        if self.output_display.toPlainText():
            cursor.insertText("\n")
        cursor.insertText(text, fmt)

        self.output_display.setTextCursor(cursor)
        self.output_display.ensureCursorVisible()

    @staticmethod
    def _extract_code_partial(text: str, language: str = "python") -> str:
        """
        Extract code from a partial (still-streaming) response.
        Tries the language-specific fence first, then falls back to plain ```.
        """
        fence = f"```{language}"
        if fence in text:
            start = text.find(fence) + len(fence)
            end   = text.find("```", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        if "```python" in text:   # common fallback regardless of language
            start = text.find("```python") + len("```python")
            end   = text.find("```", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        if "```" in text:
            start = text.find("```") + 3
            end   = text.find("```", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        return ""

    # ─────────────────────────────────────────────────────────────
    # Mode toggle  (Local Model  ↔  API)
    # ─────────────────────────────────────────────────────────────

    _BTN_ACTIVE_SS = (
        f"QPushButton {{"
        f"  background-color: {ACCENT}; color: white; border: none;"
        f"  border-radius: 7px; padding: 4px 16px;"
        f"  font-weight: 700; font-size: 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: #b45309; }}"
    )
    _BTN_INACTIVE_SS = (
        f"QPushButton {{"
        f"  background-color: #e9e7e0; color: {TEXT_SEC};"
        f"  border: 1px solid {BORDER}; border-radius: 7px; padding: 4px 16px;"
        f"  font-weight: 500; font-size: 12px;"
        f"}}"
        f"QPushButton:hover {{ background-color: {BORDER}; }}"
    )

    def _refresh_mode_buttons(self) -> None:
        if self._mode == "local":
            self.btn_mode_local.setStyleSheet(self._BTN_ACTIVE_SS)
            self.btn_mode_api.setStyleSheet(self._BTN_INACTIVE_SS)
        elif self._mode == "api":
            self.btn_mode_local.setStyleSheet(self._BTN_INACTIVE_SS)
            self.btn_mode_api.setStyleSheet(self._BTN_ACTIVE_SS)
        else:  # no mode selected yet
            self.btn_mode_local.setStyleSheet(self._BTN_INACTIVE_SS)
            self.btn_mode_api.setStyleSheet(self._BTN_INACTIVE_SS)

    def _switch_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._refresh_mode_buttons()

        if mode == "local":
            self.header_sub_lbl.setText(
                "Local Model · Qwen2.5-Coder-7B-Instruct · 4-bit NF4 · CUDA"
            )
            self._api_bar.setVisible(False)
            if self._model_loaded:
                self.model_status_lbl.setText("● Model ready")
                self.model_status_lbl.setStyleSheet(
                    f"font-size: 12px; color: {GREEN}; margin-left: 12px;"
                )
            elif self._model_loading:
                self.model_status_lbl.setText("● Loading model…")
                self.model_status_lbl.setStyleSheet(
                    f"font-size: 12px; color: {ACCENT}; margin-left: 12px;"
                )
            else:
                # First time selecting local mode — start loading now
                self.model_status_lbl.setText("● Loading model…")
                self.model_status_lbl.setStyleSheet(
                    f"font-size: 12px; color: {ACCENT}; margin-left: 12px;"
                )
                self._start_model_load()
        else:
            self.header_sub_lbl.setText(
                f"API Mode · {self._api_provider}"
            )
            self._api_bar.setVisible(True)
            self.model_status_lbl.setText("● API mode")
            self.model_status_lbl.setStyleSheet(
                "font-size: 12px; color: #0ea5e9; margin-left: 12px;"
            )

        self._update_generate_btn_state()

    def _update_generate_btn_state(self) -> None:
        """Enable the Generate button based on current-mode readiness."""
        if self._mode == "local":
            self.generate_btn.setEnabled(self._model_loaded)
        elif self._mode == "api":
            self.generate_btn.setEnabled(bool(self._api_key.strip()))
        else:
            self.generate_btn.setEnabled(False)

    # ── API bar helpers ────────────────────────────────────────────

    def _populate_models(self, provider: str) -> None:
        """Fill model_combo with the fallback list for the given provider."""
        from api_client import PROVIDERS
        models = PROVIDERS.get(provider, {}).get("fallback_models", [])
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.blockSignals(False)
        self._api_model = models[0] if models else ""

    def _on_provider_changed(self, provider: str) -> None:
        self._api_provider = provider
        self._populate_models(provider)
        if self._mode == "api":
            self.header_sub_lbl.setText(f"API Mode · {provider}")

    def _on_api_key_changed(self, text: str) -> None:
        self._api_key = text
        self._update_generate_btn_state()

    def _on_model_changed(self, model: str) -> None:
        self._api_model = model

    def _on_fetch_models(self) -> None:
        """Fetch the live model list from the provider in a background thread."""
        if not self._api_key.strip():
            self._append_output(
                "[API] Enter an API key first, then click Fetch Models.", is_error=True
            )
            return

        self.fetch_models_btn.setEnabled(False)
        self.fetch_models_btn.setText("⏳ Fetching…")

        self._model_fetcher = ModelFetchWorker(self._api_provider, self._api_key)
        self._model_fetcher.finished.connect(self._on_models_fetched)
        self._model_fetcher.error.connect(self._on_models_fetch_error)
        self._model_fetcher.start()

    def _on_models_fetched(self, models: list) -> None:
        self.fetch_models_btn.setEnabled(True)
        self.fetch_models_btn.setText("↺  Fetch Models")

        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        # Restore selection if the previously chosen model is still available
        idx = self.model_combo.findText(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)
        self._api_model = self.model_combo.currentText()

        count = len(models)
        self.statusBar().showMessage(
            f"Fetched {count} models from {self._api_provider}."
        )

    def _on_models_fetch_error(self, err: str) -> None:
        self.fetch_models_btn.setEnabled(True)
        self.fetch_models_btn.setText("↺  Fetch Models")
        self._append_output(
            f"[API] Failed to fetch models: {err}", is_error=True
        )

    # ─────────────────────────────────────────────────────────────
    # Language selector
    # ─────────────────────────────────────────────────────────────

    def _on_language_changed(self, lang_display: str) -> None:
        """Switch the active language and update the syntax highlighter."""
        self._language = _LANG_DISPLAY_MAP.get(
            lang_display.lower(), lang_display.lower()
        )

        # Detach the old highlighter and attach the new one
        from gui.highlighter import make_highlighter
        if hasattr(self, "_highlighter") and self._highlighter:
            self._highlighter.setDocument(None)
        self._highlighter = make_highlighter(
            self._language, self.code_editor.document()
        )

        # Update placeholder text to match language
        ext     = _LANG_EXT.get(self._language, "")
        comment = _LANG_COMMENT.get(self._language, "//")
        self.code_editor.setPlaceholderText(
            f"{comment} Generated {lang_display} code will appear here ({ext})…\n"
            f"{comment} You can edit it before running."
        )

        # Show / hide the runtime-missing warning label
        from code_runner import is_runtime_available, RUNTIME_INFO
        if not is_runtime_available(self._language):
            info = RUNTIME_INFO.get(self._language, {})
            check = info.get("check", self._language)
            if info.get("cannot_install"):
                warn = (
                    f"⚠ '{check}' not found — {lang_display} cannot be auto-installed. "
                    "Click ▶ Run for manual instructions."
                )
            else:
                warn = (
                    f"⚠ '{check}' not found on PATH — "
                    "click ▶ Run Code and choose to install automatically."
                )
            self.runtime_warn_lbl.setText(warn)
            self.runtime_warn_lbl.setVisible(True)
        else:
            self.runtime_warn_lbl.setVisible(False)

        self.statusBar().showMessage(f"Language: {lang_display}")

    # ─────────────────────────────────────────────────────────────
    # Model loading
    # ─────────────────────────────────────────────────────────────

    def _start_model_load(self) -> None:
        self._model_loading = True
        self._loader = ModelLoaderWorker()
        self._loader.progress.connect(self._on_model_progress)
        self._loader.finished.connect(self._on_model_loaded)
        self._loader.error.connect(self._on_model_error)
        self._loader.start()

    def _on_model_progress(self, msg: str) -> None:
        # Map loading steps to progress percentages
        msg_lower = msg.lower()
        if "tokenizer" in msg_lower:
            pct = 10
        elif "4-bit" in msg_lower or "quantis" in msg_lower or "bfloat16" in msg_lower:
            pct = 25
        elif "compil" in msg_lower:
            pct = 85
        elif "ready" in msg_lower or "vram" in msg_lower:
            pct = 98
        else:
            pct = self.progress_bar.value()   # hold current value

        # Show only the first line in the progress bar (keep it short)
        short = msg.splitlines()[0]
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{short}  ({pct} %)")
        self.progress_lbl.setText(msg)
        self.statusBar().showMessage(short)

    def _on_model_loaded(self) -> None:
        self._model_loaded = True
        self._model_loading = False
        # Only update the UI if we are still in local mode
        if self._mode == "local":
            self.generate_btn.setEnabled(True)
            self.model_status_lbl.setText("● Model ready")
            self.model_status_lbl.setStyleSheet(
                f"font-size: 12px; color: {GREEN}; margin-left: 12px;"
            )
            self.statusBar().showMessage(
                "Model loaded. Enter a prompt and click Generate."
            )
            self._set_progress(100, "Model loaded and ready.")

    def _on_model_error(self, err: str) -> None:
        self._model_loading = False
        self.model_status_lbl.setText("● Load failed")
        self.model_status_lbl.setStyleSheet(f"font-size: 12px; color: {RED};")
        self.statusBar().showMessage(f"Model error: {err}")
        self._append_output(f"ERROR loading model:\n{err}", is_error=True)
        QMessageBox.critical(self, "Model Load Error", f"Failed to load model:\n\n{err}")

    # ─────────────────────────────────────────────────────────────
    # Code generation
    # ─────────────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt or self._is_generating:
            return

        self._is_generating = True
        self.generate_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.output_display.clear()
        self.code_editor.clear()
        self._streamed_buf = ""

        # Add to conversation history
        self._chat_history.append({"role": "user", "content": prompt})
        self._append_history("You", prompt, is_user=True)

        # Build message list: language-specific system prompt + full history
        from prompts import get_system_prompt
        messages = [
            {"role": "system", "content": get_system_prompt(self._language)}
        ] + self._chat_history

        self._set_progress(0, "Starting generation…")

        if self._mode == "api":
            # ── API mode: use Groq or OpenRouter ──────────────────
            model = self._api_model or self.model_combo.currentText()
            self._generator = ApiGeneratorWorker(
                messages=messages,
                provider=self._api_provider,
                api_key=self._api_key,
                model=model,
            )
        else:
            # ── Local mode: use the on-device model ───────────────
            self._generator = CodeGeneratorWorker(messages)

        self._generator.progress.connect(self._set_progress)
        self._generator.token.connect(self._on_token)
        self._generator.finished.connect(self._on_generation_done)
        self._generator.error.connect(self._on_generation_error)
        self._generator.start()

    def _on_token(self, chunk: str) -> None:
        """Live-update the code editor as tokens stream in."""
        self._streamed_buf += chunk
        code = self._extract_code_partial(self._streamed_buf, self._language)
        if code:
            self.code_editor.setPlainText(code)
            cursor = self.code_editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.code_editor.setTextCursor(cursor)

    def _on_generation_done(self, response: str) -> None:
        from prompts import extract_code, extract_explanation

        code        = extract_code(response, self._language)
        explanation = extract_explanation(response)

        if code:
            self.code_editor.setPlainText(code)

        self._chat_history.append({"role": "assistant", "content": response})
        self._append_history("AI Coder", explanation or response, is_user=False)

        self._set_progress(100, "Code generated — review and click ▶ Run Code.")
        self._is_generating = False
        self.generate_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.prompt_input.clear()
        self.statusBar().showMessage("Code generated. Click ▶ Run Code to execute.")

    def _on_generation_error(self, err: str) -> None:
        self._is_generating = False
        self.generate_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self._set_progress(0, f"Generation error.")
        self._append_output(f"Generation error:\n{err}", is_error=True)
        self.statusBar().showMessage(f"Generation failed: {err}")

    # ─────────────────────────────────────────────────────────────
    # Code execution
    # ─────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        """
        Entry point for the Run button.

        1. If the runtime for the selected language is missing:
             a. VFP / cannot-install  → show manual instructions dialog, stop.
             b. Otherwise             → ask user if they want to auto-install,
                                        start RuntimeInstallerWorker on Yes.
        2. Runtime is present → call _run_code() directly.
        """
        code = self.code_editor.toPlainText().strip()
        if not code or self._is_running:
            return

        from code_runner import is_runtime_available, RUNTIME_INFO

        if not is_runtime_available(self._language):
            info  = RUNTIME_INFO.get(self._language, {})
            name  = info.get("name", self._language.upper())
            check = info.get("check", self._language)

            if info.get("cannot_install"):
                # Show manual instructions — no install possible
                QMessageBox.information(
                    self,
                    f"{name} — Manual Install Required",
                    info.get(
                        "manual_note",
                        f"'{check}' is not on PATH.\n"
                        f"Please install {name} manually.\n\n"
                        f"Download: {info.get('url', '')}",
                    ),
                )
                return

            # Ask the user whether to auto-install
            url  = info.get("url", "")
            reply = QMessageBox.question(
                self,
                f"Install {name}?",
                f"'{check}' was not found on PATH.\n\n"
                f"Would you like to install {name} automatically?\n\n"
                f"This uses winget (Windows Package Manager) and may take\n"
                f"a few minutes depending on your internet connection.\n\n"
                f"Manual install: {url}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._start_runtime_install()
            return

        # Runtime is available — run immediately
        self._run_code()

    def _run_code(self) -> None:
        """Start CodeRunnerWorker for the current code and language."""
        code = self.code_editor.toPlainText().strip()
        if not code or self._is_running:
            return

        self._is_running = True
        self.run_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.output_display.clear()
        self._set_progress(0, "Starting execution…")

        self._runner = CodeRunnerWorker(code, language=self._language)
        self._runner.progress.connect(self._set_progress)
        self._runner.log.connect(lambda msg: self._append_output(msg))
        self._runner.finished.connect(self._on_run_done)
        self._runner.error.connect(self._on_run_error)
        self._runner.start()

    # ─────────────────────────────────────────────────────────────
    # Runtime installer agent
    # ─────────────────────────────────────────────────────────────

    def _start_runtime_install(self) -> None:
        """Launch RuntimeInstallerWorker and show progress in the output panel."""
        from code_runner import RUNTIME_INFO
        info = RUNTIME_INFO.get(self._language, {})
        name = info.get("name", self._language.upper())

        self.run_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.output_display.clear()
        self._set_progress(0, f"Installing {name}…")
        self._append_output(
            f"⚙ Installing {name} via winget — please wait…\n"
            f"{'─' * 44}"
        )

        self._runtime_installer = RuntimeInstallerWorker(self._language)
        self._runtime_installer.progress.connect(self._on_runtime_install_progress)
        self._runtime_installer.finished.connect(self._on_runtime_install_done)
        self._runtime_installer.start()

    def _on_runtime_install_progress(self, msg: str) -> None:
        self._append_output(msg)
        short = msg[:70].strip()
        self._set_progress(50, short or "Installing…")

    def _on_runtime_install_done(self, success: bool, log: str) -> None:
        from code_runner import RUNTIME_INFO
        info = RUNTIME_INFO.get(self._language, {})
        name = info.get("name", self._language.upper())
        url  = info.get("url", "")

        self.run_btn.setEnabled(True)
        self._update_generate_btn_state()

        if success:
            self._set_progress(100, f"{name} installed.")
            self._append_output(f"\n{'─' * 44}")
            self._append_output(f"✅ {name} installed successfully!")
            self.runtime_warn_lbl.setVisible(False)

            reply = QMessageBox.question(
                self,
                "Runtime Installed",
                f"{name} was installed successfully.\n\n"
                "Note: If the runtime is still not found, you may need to\n"
                "restart this application or open a new terminal session.\n\n"
                "Run your code now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._run_code()
        else:
            self._set_progress(0, "Installation failed.")
            self._append_output(f"\n{'─' * 44}")
            self._append_output(
                f"❌ Installation failed — see log above.", is_error=True
            )
            if url:
                self._append_output(
                    f"\n📥 Install manually: {url}"
                )

    def _on_run_done(self, result) -> None:
        from code_runner import format_output
        output, status = format_output(result)

        is_error = status != "success"
        if output:
            self._append_output(output, is_error=is_error)

        if result.installed_packages:
            self._append_output(
                f"\n✅ Auto-installed: {', '.join(result.installed_packages)}"
            )

        # Embed any matplotlib figures that were captured during execution
        if result.plot_files:
            count = len(result.plot_files)
            self._append_output(
                f"\n{'─' * 28}\n"
                f"[{count} plot{'s' if count > 1 else ''} generated]"
            )
            for idx, path in enumerate(result.plot_files, 1):
                self._append_plot_image(path, idx)

        self._is_running = False
        self.run_btn.setEnabled(True)
        self._update_generate_btn_state()

        if status == "success":
            self._set_progress(100, "✓ Code ran successfully.")
            self.statusBar().showMessage("✓ Code ran successfully.")
        elif status == "timeout":
            self._set_progress(100, "⏱ Timed out — check for infinite loops.")
            self.statusBar().showMessage("Execution timed out.")
        else:
            self._set_progress(100, "✗ Code failed — see output panel.")
            self.statusBar().showMessage("Code execution failed.")

    def _on_run_error(self, err: str) -> None:
        self._is_running = False
        self.run_btn.setEnabled(True)
        self._update_generate_btn_state()
        self._set_progress(0, "Execution error.")
        self._append_output(f"Runner error:\n{err}", is_error=True)

    def _append_plot_image(self, path: str, idx: int) -> None:
        """
        Load a PNG figure from *path* and embed it inline in the output
        QTextEdit using Qt's document-resource mechanism.

        The image is scaled down to fit the panel width if necessary,
        preserving the aspect ratio.
        """
        image = QImage(path)
        if image.isNull():
            self._append_output(
                f"[Plot {idx}: could not load image — {path}]", is_error=True
            )
            return

        # Leave a 40-px margin so the image never overflows the panel.
        available = max(400, self.output_display.viewport().width() - 40)
        if image.width() > available:
            image = image.scaledToWidth(
                available, Qt.TransformationMode.SmoothTransformation
            )

        # Register the image as a named resource in the document so the
        # cursor can reference it by name rather than file path.
        resource_name = f"plot_{idx}_{os.path.basename(path)}"
        doc = self.output_display.document()
        doc.addResource(
            QTextDocument.ResourceType.ImageResource,
            QUrl(resource_name),
            image,
        )

        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextImageFormat()
        fmt.setName(resource_name)
        fmt.setWidth(image.width())
        fmt.setHeight(image.height())
        cursor.insertImage(fmt)

        self.output_display.setTextCursor(cursor)
        self.output_display.ensureCursorVisible()

    # ─────────────────────────────────────────────────────────────
    # Toolbar actions
    # ─────────────────────────────────────────────────────────────

    def _copy_code(self) -> None:
        code = self.code_editor.toPlainText()
        if code:
            QApplication.clipboard().setText(code)
            self.statusBar().showMessage("Code copied to clipboard.")

    def _clear_editor(self) -> None:
        self.code_editor.clear()
        self.output_display.clear()
        self._set_progress(0, "Editor cleared.")

    def _clear_chat(self) -> None:
        self._chat_history.clear()
        self.history_display.clear()
        self.statusBar().showMessage("Conversation cleared.")

    # ─────────────────────────────────────────────────────────────
    # Window lifecycle
    # ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
