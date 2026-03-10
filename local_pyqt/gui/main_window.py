# gui/main_window.py
# Coder_AI — Inline-Hydraulik
#
# Layout:
#   LEFT   — Sidebar: logo, New Chat, session list, backend selector, model picker
#   RIGHT  — Main area: tab bar (Chat / Code / Output) + stacked pages
#
# Supports two backends:
#   • Local Model  — Qwen2.5-Coder-7B-Instruct loaded via local_model.py
#   • Groq API     — streamed via api_client.py (key from .env)
#
# Chat sessions are persisted to chat_sessions.json between runs.

from __future__ import annotations

import os

from dotenv import load_dotenv
from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QImage, QTextCharFormat,
    QTextCursor, QTextDocument, QTextImageFormat,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from gui.highlighter import PythonHighlighter

# ── Load .env ──────────────────────────────────────────────────────────
load_dotenv()

# ── Design tokens — European Atelier Light Theme ──────────────────────
SIDEBAR_BG   = "#EDEAE3"
MAIN_BG      = "#FAF9F6"
SURFACE      = "#FFFFFF"
BORDER       = "#D8D1C7"
ACCENT       = "#B45309"
TEXT_PRI     = "#1C1512"
TEXT_SEC     = "#6B6058"
TEXT_MUTED   = "#A09080"
GREEN        = "#166534"
RED          = "#9B2335"
WARN         = "#92400E"
SIDEBAR_HOV  = "#E3DDD4"
SIDEBAR_SEL  = "#D8D0C5"

# ── Groq fallback model list ───────────────────────────────────────────
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen-2.5-coder-32b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "deepseek-r1-distill-llama-70b",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

# ── Global stylesheet ──────────────────────────────────────────────────
APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {MAIN_BG};
    color: {TEXT_PRI};
    font-family: "Segoe UI", Inter, sans-serif;
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 8px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QTextEdit, QPlainTextEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT};
    selection-color: white;
    line-height: 1.5;
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}
QPushButton {{
    background-color: {SURFACE};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 13px;
    min-height: 32px;
}}
QPushButton:hover   {{ background-color: {SIDEBAR_HOV}; border-color: {TEXT_MUTED}; }}
QPushButton:pressed {{ background-color: {SIDEBAR_SEL}; }}
QPushButton:disabled {{
    background-color: {MAIN_BG};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton#generateBtn {{
    background-color: #1C1512;
    color: #B45309;
    border: 1px solid #1C1512;
    font-weight: 600;
    font-size: 13px;
    min-height: 40px;
    border-radius: 8px;
    padding: 0px 20px;
    letter-spacing: 0.3px;
}}
QPushButton#generateBtn:hover   {{ background-color: #2C2520; border-color: #2C2520; }}
QPushButton#generateBtn:pressed {{ background-color: #3D3530; border-color: #3D3530; }}
QPushButton#generateBtn:disabled {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
}}
QPushButton#runBtn {{
    background-color: {SURFACE};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 13px;
    min-height: 30px;
}}
QPushButton#runBtn:hover   {{ background-color: {SIDEBAR_HOV}; border-color: {TEXT_MUTED}; }}
QPushButton#runBtn:pressed {{ background-color: {SIDEBAR_SEL}; }}
QPushButton#runBtn:disabled {{
    background-color: {MAIN_BG};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}
QPushButton#tabBtn {{
    background: transparent;
    color: {TEXT_SEC};
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    min-height: 36px;
}}
QPushButton#tabBtn:hover {{ color: {TEXT_PRI}; }}
QPushButton#tabBtn[active="true"] {{
    color: {TEXT_PRI};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QPushButton#newChatBtn {{
    background-color: #1C1512;
    color: #B45309;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
    text-align: left;
}}
QPushButton#newChatBtn:hover   {{ background-color: #2C2520; }}
QPushButton#newChatBtn:pressed {{ background-color: #3D3530; }}
/* Mode toggle buttons */
QPushButton#modeBtn {{
    background-color: {SURFACE};
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 500;
    min-height: 26px;
}}
QPushButton#modeBtn:hover {{ background-color: {SIDEBAR_HOV}; color: {TEXT_PRI}; }}
QPushButton#modeBtn[active="true"] {{
    background-color: #1C1512;
    color: #B45309;
    border-color: #1C1512;
    font-weight: 600;
}}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background: transparent;
    color: {TEXT_SEC};
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    margin: 1px 4px;
}}
QListWidget::item:hover {{ background: {SIDEBAR_HOV}; color: {TEXT_PRI}; }}
QListWidget::item:selected {{
    background: {SIDEBAR_SEL};
    color: {TEXT_PRI};
}}
QComboBox {{
    background-color: {SURFACE};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}
QComboBox:hover {{ border-color: {TEXT_MUTED}; }}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: right center;
    width: 20px; border: none;
}}
QComboBox::down-arrow {{
    border-left:  4px solid transparent;
    border-right: 4px solid transparent;
    border-top:   5px solid {TEXT_SEC};
    width: 0; height: 0;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT_PRI};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    selection-color: white;
    padding: 4px;
    outline: none;
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {BORDER};
    height: 4px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}
QLabel {{ color: {TEXT_PRI}; background: transparent; }}
QSplitter::handle {{ background-color: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}
QWidget#sidebar  {{ background-color: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}
QWidget#mainArea {{ background-color: {MAIN_BG}; }}
QWidget#tabBar   {{ background-color: {MAIN_BG}; border-bottom: 1px solid {BORDER}; }}
QWidget#headerBar {{ background-color: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER}; }}
"""


# ─────────────────────────────────────────────────────────────────────
# Worker Threads
# ─────────────────────────────────────────────────────────────────────

class ModelLoaderWorker(QThread):
    """Loads the local Qwen model in a background thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def run(self) -> None:
        try:
            from local_model import get_model
            model = get_model()
            model.load(progress_cb=lambda msg: self.progress.emit(msg))
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class CodeGeneratorWorker(QThread):
    """Streams tokens from the local model in a background thread."""
    progress = pyqtSignal(int, str)
    token    = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, messages: list[dict], parent=None):
        super().__init__(parent)
        self.messages = messages

    def run(self) -> None:
        try:
            from local_model import get_model
            model = get_model()
            self.progress.emit(10, "Preparing local model…")
            full_response = ""
            token_count   = 0
            self.progress.emit(20, "Generating code…")
            for chunk in model.generate_stream(self.messages):
                full_response += chunk
                token_count   += 1
                self.token.emit(chunk)
                if token_count % 8 == 0:
                    pct = min(85, 20 + int(token_count / 500 * 65))
                    self.progress.emit(pct, "Generating…")
            self.progress.emit(100, "Generation complete.")
            self.finished.emit(full_response)
        except Exception as exc:
            self.error.emit(str(exc))


class ApiGeneratorWorker(QThread):
    """Streams code tokens from Groq in a background thread."""
    progress = pyqtSignal(int, str)
    token    = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, messages: list[dict], api_key: str, model: str, parent=None):
        super().__init__(parent)
        self.messages = messages
        self.api_key  = api_key
        self.model    = model

    def run(self) -> None:
        try:
            from api_client import ApiClient
            client = ApiClient("Groq", self.api_key, self.model)
            self.progress.emit(10, f"Connecting to Groq · {self.model}…")
            full_response = ""
            token_count   = 0
            self.progress.emit(20, "Generating code…")
            for chunk in client.generate_stream(self.messages):
                full_response += chunk
                token_count   += 1
                self.token.emit(chunk)
                if token_count % 8 == 0:
                    pct = min(85, 20 + int(token_count / 500 * 65))
                    self.progress.emit(pct, "Generating…")
            self.progress.emit(100, "Generation complete.")
            self.finished.emit(full_response)
        except Exception as exc:
            self.error.emit(str(exc))


class ModelFetchWorker(QThread):
    """Fetches live model list from Groq."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self) -> None:
        try:
            from api_client import ApiClient
            client = ApiClient("Groq", self.api_key)
            models = client.get_models()
            self.finished.emit(models)
        except Exception as exc:
            self.error.emit(str(exc))


class CodeRunnerWorker(QThread):
    """Runs generated Python code in a subprocess."""
    progress = pyqtSignal(int, str)
    log      = pyqtSignal(str)
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self.code = code

    def run(self) -> None:
        try:
            from code_runner import (
                extract_imports, resolve_pip_name,
                is_package_installed, STDLIB_MODULES, run_python_code,
            )
            imports = extract_imports(self.code)
            missing = [
                resolve_pip_name(m) for m in imports
                if m not in STDLIB_MODULES and not is_package_installed(m)
            ]
            self.progress.emit(10, "Checking dependencies…")
            if missing:
                self.progress.emit(15, f"Installing: {', '.join(missing)}")
                self.log.emit(f"[!] Missing: {', '.join(missing)}")
            else:
                self.log.emit("✓ All dependencies satisfied.")

            install_count = [0]
            install_total = len(missing)

            def _progress_cb(msg: str) -> None:
                msg_l = msg.lower()
                if "installing" in msg_l and "[pkg]" in msg_l:
                    install_count[0] += 1
                    pct = 15 + int(install_count[0] / max(install_total, 1) * 50)
                    self.progress.emit(pct, msg)
                elif "executing" in msg_l:
                    self.progress.emit(70, msg)
                elif "satisfied" in msg_l:
                    self.progress.emit(40, msg)
                self.log.emit(msg)

            result = run_python_code(self.code, timeout=60, progress_cb=_progress_cb)
            self.progress.emit(100, "✓ Done." if result.success else "✗ Failed.")
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────
# Sidebar Widget
# ─────────────────────────────────────────────────────────────────────

class SidebarWidget(QWidget):
    """Left navigation sidebar — sessions list, backend selector, model picker."""

    session_selected = pyqtSignal(int)
    new_chat_clicked = pyqtSignal()
    mode_changed     = pyqtSignal(str)   # "local" or "groq"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(230)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── App title ────────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(56)
        title_bar.setStyleSheet(f"background: {SIDEBAR_BG};")
        t_lay = QHBoxLayout(title_bar)
        t_lay.setContentsMargins(16, 0, 16, 0)
        icon_lbl = QLabel("⚡")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
        t_lay.addWidget(icon_lbl)
        name_lbl = QLabel("Coder AI")
        name_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {TEXT_PRI};"
            " background: transparent; margin-left: 4px;"
        )
        t_lay.addWidget(name_lbl)
        t_lay.addStretch()
        lay.addWidget(title_bar)

        lay.addWidget(self._divider())

        # ── New Chat button ──────────────────────────────────────────
        btn_area = QWidget()
        btn_area.setStyleSheet(f"background: {SIDEBAR_BG};")
        b_lay = QVBoxLayout(btn_area)
        b_lay.setContentsMargins(12, 10, 12, 10)
        self.new_chat_btn = QPushButton("＋  New Chat")
        self.new_chat_btn.setObjectName("newChatBtn")
        self.new_chat_btn.clicked.connect(self.new_chat_clicked.emit)
        b_lay.addWidget(self.new_chat_btn)
        lay.addWidget(btn_area)

        # ── Session list ─────────────────────────────────────────────
        sess_lbl = QLabel("RECENT CHATS")
        sess_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700;"
            f" letter-spacing: 1.2px; background: {SIDEBAR_BG};"
            " padding: 4px 16px;"
        )
        lay.addWidget(sess_lbl)

        self.session_list = QListWidget()
        self.session_list.setStyleSheet(
            f"QListWidget {{ background: {SIDEBAR_BG}; border: none; padding: 0 4px; }}"
            f"QListWidget::item {{ border-radius: 6px; padding: 8px 12px; font-size: 12px; color: {TEXT_SEC}; margin: 1px 4px; }}"
            f"QListWidget::item:hover {{ background: {SIDEBAR_HOV}; color: {TEXT_PRI}; }}"
            f"QListWidget::item:selected {{ background: {SIDEBAR_SEL}; color: {TEXT_PRI}; }}"
        )
        self.session_list.itemClicked.connect(
            lambda item: self.session_selected.emit(self.session_list.row(item))
        )
        lay.addWidget(self.session_list, 1)

        # ── Bottom section ───────────────────────────────────────────
        lay.addWidget(self._divider())

        bottom = QWidget()
        bottom.setStyleSheet(f"background: {SIDEBAR_BG};")
        bot_lay = QVBoxLayout(bottom)
        bot_lay.setContentsMargins(12, 10, 12, 14)
        bot_lay.setSpacing(8)

        # Backend label
        be_lbl = QLabel("BACKEND")
        be_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700;"
            " letter-spacing: 1.2px;"
        )
        bot_lay.addWidget(be_lbl)

        # Mode toggle: Local Model | Groq API
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)

        self.local_btn = QPushButton("Local Model")
        self.local_btn.setObjectName("modeBtn")
        self.local_btn.setProperty("active", "false")
        self.local_btn.clicked.connect(lambda: self._set_mode("local"))

        self.groq_btn = QPushButton("Groq API")
        self.groq_btn.setObjectName("modeBtn")
        self.groq_btn.setProperty("active", "true")
        self.groq_btn.clicked.connect(lambda: self._set_mode("groq"))

        mode_row.addWidget(self.local_btn)
        mode_row.addWidget(self.groq_btn)
        bot_lay.addLayout(mode_row)

        # ── Local model section (hidden by default) ──────────────────
        self._local_section = QWidget()
        local_lay = QVBoxLayout(self._local_section)
        local_lay.setContentsMargins(0, 0, 0, 0)
        local_lay.setSpacing(4)

        self.load_model_btn = QPushButton("⬇  Load Model")
        self.load_model_btn.setFixedHeight(28)
        self.load_model_btn.setStyleSheet(
            f"QPushButton {{ background: {SURFACE}; color: {TEXT_PRI};"
            f" border: 1px solid {BORDER}; border-radius: 6px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {SIDEBAR_HOV}; }}"
            f"QPushButton:disabled {{ color: {TEXT_MUTED}; }}"
        )
        local_lay.addWidget(self.load_model_btn)

        self.local_status_lbl = QLabel("● Model not loaded")
        self.local_status_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px;"
        )
        local_lay.addWidget(self.local_status_lbl)

        self._local_section.setVisible(False)
        bot_lay.addWidget(self._local_section)

        # ── Groq section ─────────────────────────────────────────────
        self._groq_section = QWidget()
        groq_lay = QVBoxLayout(self._groq_section)
        groq_lay.setContentsMargins(0, 0, 0, 0)
        groq_lay.setSpacing(6)

        # Model selector row
        model_row = QHBoxLayout()
        model_row.setSpacing(6)
        m_lbl = QLabel("Model")
        m_lbl.setStyleSheet(
            f"color: {TEXT_SEC}; font-size: 11px; font-weight: 600;"
        )
        model_row.addWidget(m_lbl)
        self.model_combo = QComboBox()
        self.model_combo.addItems(GROQ_MODELS)
        self.model_combo.setFixedHeight(28)
        model_row.addWidget(self.model_combo, 1)
        self.refresh_btn = QPushButton("↺")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip("Fetch live model list from Groq")
        self.refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {SURFACE}; color: {TEXT_SEC};"
            f" border: 1px solid {BORDER}; border-radius: 6px; font-size: 14px; }}"
            f"QPushButton:hover {{ color: {TEXT_PRI}; background: {SIDEBAR_HOV}; }}"
        )
        model_row.addWidget(self.refresh_btn)
        groq_lay.addLayout(model_row)

        # API key status
        self.key_status_lbl = QLabel("● Groq: key not found")
        self.key_status_lbl.setStyleSheet(
            f"color: {RED}; font-size: 11px;"
        )
        groq_lay.addWidget(self.key_status_lbl)

        bot_lay.addWidget(self._groq_section)
        lay.addWidget(bottom)

    def _set_mode(self, mode: str) -> None:
        is_local = mode == "local"
        self.local_btn.setProperty("active", "true" if is_local else "false")
        self.groq_btn.setProperty("active", "false" if is_local else "true")
        for btn in (self.local_btn, self.groq_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._local_section.setVisible(is_local)
        self._groq_section.setVisible(not is_local)
        self.mode_changed.emit(mode)

    @staticmethod
    def _divider() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet(f"color: {BORDER}; background: {BORDER}; max-height: 1px;")
        return f

    def add_session(self, name: str) -> None:
        item = QListWidgetItem(f"💬  {name}")
        self.session_list.insertItem(0, item)
        self.session_list.setCurrentRow(0)

    def rename_session(self, index: int, name: str) -> None:
        if 0 <= index < self.session_list.count():
            self.session_list.item(index).setText(f"💬  {name}")

    def set_key_status(self, ok: bool) -> None:
        if ok:
            self.key_status_lbl.setText("● Groq: connected")
            self.key_status_lbl.setStyleSheet(
                f"color: {GREEN}; font-size: 11px;"
            )
        else:
            self.key_status_lbl.setText("● Groq: key missing  →  set in .env")
            self.key_status_lbl.setStyleSheet(
                f"color: {RED}; font-size: 11px;"
            )

    def set_local_status(self, loaded: bool) -> None:
        if loaded:
            self.local_status_lbl.setText("● Model ready")
            self.local_status_lbl.setStyleSheet(f"color: {GREEN}; font-size: 11px;")
            self.load_model_btn.setEnabled(False)
        else:
            self.local_status_lbl.setText("● Model not loaded")
            self.local_status_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
            self.load_model_btn.setEnabled(True)


# ─────────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Coder_AI — Inline-Hydraulik")
        self.resize(1440, 880)
        self.setMinimumSize(960, 640)

        # ── API / model state ────────────────────────────────────────
        self._api_key   = os.getenv("GROQ_API_KEY", "").strip()
        self._api_model = os.getenv("GROQ_DEFAULT_MODEL", GROQ_MODELS[0]).strip()

        # ── Backend mode: "groq" | "local" ───────────────────────────
        self._mode              = "groq"
        self._local_model_loaded = False

        # ── App state ────────────────────────────────────────────────
        self._is_generating = False
        self._is_running    = False
        self._streamed_buf  = ""

        # ── Session management ───────────────────────────────────────
        self._sessions: list[dict] = []
        self._active_session_idx: int = -1

        # ── Build UI ─────────────────────────────────────────────────
        self._build_ui()
        self.setStyleSheet(APP_STYLE)

        # ── Post-init ────────────────────────────────────────────────
        key_ok = bool(self._api_key) and self._api_key != "your_groq_api_key_here"
        self._sidebar.set_key_status(key_ok)
        self._update_generate_btn_state()

        # Restore sessions or start fresh
        if not self._restore_sessions():
            self._new_session()

    # ─────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # Sidebar
        self._sidebar = SidebarWidget()
        self._sidebar.new_chat_clicked.connect(self._new_session)
        self._sidebar.session_selected.connect(self._load_session)
        self._sidebar.model_combo.currentTextChanged.connect(self._on_model_changed)
        self._sidebar.refresh_btn.clicked.connect(self._on_fetch_models)
        self._sidebar.mode_changed.connect(self._on_mode_changed)
        self._sidebar.load_model_btn.clicked.connect(self._on_load_local_model)
        root_lay.addWidget(self._sidebar)

        # Main area
        main_area = QWidget()
        main_area.setObjectName("mainArea")
        main_lay = QVBoxLayout(main_area)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(self._build_header_bar())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_chat_page())    # 0
        self._stack.addWidget(self._build_code_page())    # 1
        self._stack.addWidget(self._build_output_page())  # 2
        main_lay.addWidget(self._stack, 1)

        self._switch_tab(0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {BORDER}; border: none; border-radius: 0; }}"
            f"QProgressBar::chunk {{ background: {ACCENT}; border-radius: 0; }}"
        )
        main_lay.addWidget(self._progress_bar)
        root_lay.addWidget(main_area, 1)

    def _build_header_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("headerBar")
        bar.setFixedHeight(48)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 16, 0)
        lay.setSpacing(0)

        self._session_title_lbl = QLabel("New Chat")
        self._session_title_lbl.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {TEXT_PRI}; background: transparent;"
        )
        lay.addWidget(self._session_title_lbl)
        lay.addStretch()

        tab_bar = QWidget()
        tab_bar.setObjectName("tabBar")
        tab_bar.setStyleSheet("background: transparent; border: none;")
        tab_lay = QHBoxLayout(tab_bar)
        tab_lay.setContentsMargins(0, 0, 0, 0)
        tab_lay.setSpacing(0)

        self._tab_btns: list[QPushButton] = []
        for idx, label in enumerate(["Chat", "Code", "Output"]):
            btn = QPushButton(label)
            btn.setObjectName("tabBtn")
            btn.setCheckable(False)
            btn.setProperty("active", "false")
            btn.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            tab_lay.addWidget(btn)
            self._tab_btns.append(btn)
        lay.addWidget(tab_bar)

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent; margin-left: 16px;"
        )
        lay.addWidget(self._status_lbl)
        return bar

    # ── Chat page ─────────────────────────────────────────────────────

    def _build_chat_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("mainArea")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setPlaceholderText(
            "Your conversation will appear here…\n\nType a prompt below and click Generate."
        )
        self.history_display.setStyleSheet(
            f"background-color: {MAIN_BG}; border: none; padding: 20px 24px; border-radius: 0;"
        )
        self.history_display.setFont(QFont("Segoe UI", 13))
        lay.addWidget(self.history_display, 1)

        input_area = QWidget()
        input_area.setStyleSheet(f"background: {SIDEBAR_BG}; border-top: 1px solid {BORDER};")
        in_lay = QVBoxLayout(input_area)
        in_lay.setContentsMargins(20, 12, 20, 16)
        in_lay.setSpacing(10)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Ask me to write Python code… e.g. \"Build a REST API with FastAPI\""
        )
        self.prompt_input.setFixedHeight(88)
        self.prompt_input.setStyleSheet(
            f"background-color: {SURFACE}; border: 1px solid {BORDER};"
            " border-radius: 10px; padding: 12px 14px;"
            f" color: {TEXT_PRI}; font-size: 13px;"
        )
        self.prompt_input.installEventFilter(self)
        in_lay.addWidget(self.prompt_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        clear_chat_btn = QPushButton("🗑  Clear")
        clear_chat_btn.setFixedHeight(36)
        clear_chat_btn.setFixedWidth(90)
        clear_chat_btn.clicked.connect(self._clear_chat)
        btn_row.addWidget(clear_chat_btn)
        btn_row.addStretch()

        self._key_warn_lbl = QLabel("⚠ Set GROQ_API_KEY in your .env file")
        self._key_warn_lbl.setStyleSheet(
            f"color: {WARN}; font-size: 11px; background: transparent;"
        )
        self._key_warn_lbl.setVisible(False)
        btn_row.addWidget(self._key_warn_lbl)

        self.generate_btn = QPushButton("⚡  Generate Code")
        self.generate_btn.setObjectName("generateBtn")
        self.generate_btn.setFixedHeight(42)
        self.generate_btn.setMinimumWidth(160)
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self._on_generate)
        btn_row.addWidget(self.generate_btn)

        in_lay.addLayout(btn_row)
        lay.addWidget(input_area)
        return page

    # ── Code page ─────────────────────────────────────────────────────

    def _build_code_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("mainArea")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        toolbar_w = QWidget()
        toolbar_w.setFixedHeight(44)
        toolbar_w.setStyleSheet(f"background: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER};")
        tb_lay = QHBoxLayout(toolbar_w)
        tb_lay.setContentsMargins(16, 0, 16, 0)
        tb_lay.setSpacing(8)

        editor_lbl = QLabel("CODE EDITOR")
        editor_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;"
        )
        tb_lay.addWidget(editor_lbl)
        tb_lay.addStretch()

        copy_btn = QPushButton("⎘  Copy")
        copy_btn.setFixedHeight(30)
        copy_btn.clicked.connect(self._copy_code)
        tb_lay.addWidget(copy_btn)

        clear_editor_btn = QPushButton("✕  Clear")
        clear_editor_btn.setFixedHeight(30)
        clear_editor_btn.clicked.connect(self._clear_editor)
        tb_lay.addWidget(clear_editor_btn)

        self.run_btn = QPushButton("▶  Run Code")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setFixedHeight(30)
        self.run_btn.clicked.connect(self._on_run)
        tb_lay.addWidget(self.run_btn)

        lay.addWidget(toolbar_w)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setPlaceholderText(
            "# Generated Python code will appear here…\n"
            "# Switch to the Chat tab, type a prompt, and click Generate.\n"
            "# You can edit the code here before running."
        )
        mono = QFont("Consolas", 12)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.code_editor.setFont(mono)
        self.code_editor.setStyleSheet(
            f"background-color: {SIDEBAR_BG}; border: none; border-radius: 0; padding: 16px 20px;"
        )
        self._highlighter = PythonHighlighter(self.code_editor.document())
        lay.addWidget(self.code_editor, 1)
        return page

    # ── Output page ────────────────────────────────────────────────────

    def _build_output_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("mainArea")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        out_toolbar = QWidget()
        out_toolbar.setFixedHeight(44)
        out_toolbar.setStyleSheet(f"background: {SIDEBAR_BG}; border-bottom: 1px solid {BORDER};")
        ot_lay = QHBoxLayout(out_toolbar)
        ot_lay.setContentsMargins(16, 0, 16, 0)
        ot_lay.setSpacing(8)

        out_lbl = QLabel("OUTPUT / LOGS")
        out_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.2px;"
        )
        ot_lay.addWidget(out_lbl)
        ot_lay.addStretch()

        clear_out_btn = QPushButton("✕  Clear")
        clear_out_btn.setFixedHeight(30)
        clear_out_btn.clicked.connect(lambda: self.output_display.clear())
        ot_lay.addWidget(clear_out_btn)
        lay.addWidget(out_toolbar)

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText(
            "Code execution output and logs will appear here…\n\n"
            "Go to the Code tab, then click ▶ Run Code."
        )
        mono2 = QFont("Consolas", 12)
        mono2.setStyleHint(QFont.StyleHint.Monospace)
        self.output_display.setFont(mono2)
        self.output_display.setStyleSheet(
            f"background-color: {SIDEBAR_BG}; border: none; border-radius: 0; padding: 16px 20px;"
        )
        lay.addWidget(self.output_display, 1)

        self._progress_lbl = QLabel("Ready")
        self._progress_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_lbl.setStyleSheet(
            f"color: {TEXT_SEC}; font-size: 11px; padding: 6px;"
            f" background: {SIDEBAR_BG}; border-top: 1px solid {BORDER};"
        )
        lay.addWidget(self._progress_lbl)
        return page

    # ─────────────────────────────────────────────────────────────────
    # Tab switching
    # ─────────────────────────────────────────────────────────────────

    def _switch_tab(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ─────────────────────────────────────────────────────────────────
    # Session management
    # ─────────────────────────────────────────────────────────────────

    def _new_session(self) -> None:
        name = f"Chat {len(self._sessions) + 1}"
        self._sessions.insert(0, {"name": name, "history": []})
        if self._active_session_idx >= 0:
            self._active_session_idx += 1
        self._active_session_idx = 0
        self._sidebar.add_session(name)
        self.history_display.clear()
        self.code_editor.clear()
        self.output_display.clear()
        self.prompt_input.clear()
        self._streamed_buf = ""
        self._session_title_lbl.setText(name)
        self._switch_tab(0)
        self._save_sessions()

    def _load_session(self, index: int) -> None:
        if index < 0 or index >= len(self._sessions):
            return
        self._active_session_idx = index
        sess = self._sessions[index]
        self._session_title_lbl.setText(sess["name"])
        self.history_display.clear()
        for msg in sess["history"]:
            if msg["role"] == "user":
                self._append_history("You", msg["content"], is_user=True)
            elif msg["role"] == "assistant":
                from prompts import extract_explanation
                self._append_history(
                    "Coder AI",
                    extract_explanation(msg["content"]) or msg["content"],
                    is_user=False,
                )

    def _current_history(self) -> list[dict]:
        if self._active_session_idx < 0:
            return []
        return self._sessions[self._active_session_idx]["history"]

    # ─────────────────────────────────────────────────────────────────
    # JSON persistence
    # ─────────────────────────────────────────────────────────────────

    def _save_sessions(self) -> None:
        from sessions import save_sessions
        save_sessions(self._sessions, self._active_session_idx)

    def _restore_sessions(self) -> bool:
        from sessions import load_sessions
        sessions, last_idx = load_sessions()
        if not sessions:
            return False
        self._sessions = sessions
        for sess in sessions:
            self._sidebar.session_list.addItem(QListWidgetItem(f"💬  {sess['name']}"))
        safe_idx = min(last_idx, len(sessions) - 1)
        self._sidebar.session_list.setCurrentRow(safe_idx)
        self._load_session(safe_idx)
        return True

    def closeEvent(self, event) -> None:
        self._save_sessions()
        super().closeEvent(event)

    # ─────────────────────────────────────────────────────────────────
    # Backend mode
    # ─────────────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        self._mode = mode
        self._update_generate_btn_state()
        if mode == "local":
            self._key_warn_lbl.setVisible(False)
            self._set_status("Local model selected — click Load Model to initialise")
        else:
            key_ok = bool(self._api_key) and self._api_key != "your_groq_api_key_here"
            self._key_warn_lbl.setVisible(not key_ok)
            self._set_status("Groq API selected")

    def _on_load_local_model(self) -> None:
        """Load the local model in a background thread with progress shown in Output tab."""
        self._sidebar.load_model_btn.setEnabled(False)
        self._sidebar.local_status_lbl.setText("● Loading…")
        self._sidebar.local_status_lbl.setStyleSheet(
            f"color: {WARN}; font-size: 11px;"
        )
        self.output_display.clear()
        self._switch_tab(2)
        self._append_output("⚙ Loading local model — this may take a moment…\n" + "─" * 44)
        self._set_progress(5, "Loading model…")

        self._model_loader = ModelLoaderWorker()
        self._model_loader.progress.connect(self._on_model_load_progress)
        self._model_loader.finished.connect(self._on_model_load_done)
        self._model_loader.error.connect(self._on_model_load_error)
        self._model_loader.start()

    def _on_model_load_progress(self, msg: str) -> None:
        self._append_output(msg)
        self._set_status(msg.split("\n")[0][:80])

    def _on_model_load_done(self) -> None:
        self._local_model_loaded = True
        self._sidebar.set_local_status(True)
        self._append_output("\n✅ Model loaded and ready.")
        self._set_progress(100, "Model ready")
        self._set_status("✅ Local model ready")
        self._update_generate_btn_state()

    def _on_model_load_error(self, err: str) -> None:
        self._sidebar.load_model_btn.setEnabled(True)
        self._sidebar.local_status_lbl.setText("● Load failed")
        self._sidebar.local_status_lbl.setStyleSheet(f"color: {RED}; font-size: 11px;")
        self._append_output(f"\n❌ Load failed:\n{err}", is_error=True)
        self._set_status(f"Model load error: {err[:60]}")

    # ─────────────────────────────────────────────────────────────────
    # Groq helpers
    # ─────────────────────────────────────────────────────────────────

    def _on_model_changed(self, model: str) -> None:
        self._api_model = model

    def _on_fetch_models(self) -> None:
        key_ok = bool(self._api_key) and self._api_key != "your_groq_api_key_here"
        if not key_ok:
            self._set_status("⚠ Set GROQ_API_KEY in .env first")
            return
        self._sidebar.refresh_btn.setEnabled(False)
        self._sidebar.refresh_btn.setText("…")
        self._model_fetcher = ModelFetchWorker(self._api_key)
        self._model_fetcher.finished.connect(self._on_models_fetched)
        self._model_fetcher.error.connect(
            lambda e: (
                self._sidebar.refresh_btn.setEnabled(True),
                self._sidebar.refresh_btn.setText("↺"),
                self._set_status(f"Fetch error: {e}"),
            )
        )
        self._model_fetcher.start()

    def _on_models_fetched(self, models: list) -> None:
        self._sidebar.refresh_btn.setEnabled(True)
        self._sidebar.refresh_btn.setText("↺")
        current = self._sidebar.model_combo.currentText()
        self._sidebar.model_combo.blockSignals(True)
        self._sidebar.model_combo.clear()
        self._sidebar.model_combo.addItems(models)
        idx = self._sidebar.model_combo.findText(current)
        if idx >= 0:
            self._sidebar.model_combo.setCurrentIndex(idx)
        self._sidebar.model_combo.blockSignals(False)
        self._api_model = self._sidebar.model_combo.currentText()
        self._set_status(f"Fetched {len(models)} models from Groq")

    # ─────────────────────────────────────────────────────────────────
    # Generate button state
    # ─────────────────────────────────────────────────────────────────

    def _update_generate_btn_state(self) -> None:
        if self._mode == "local":
            ready = self._local_model_loaded and not self._is_generating
            self.generate_btn.setEnabled(ready)
            self._key_warn_lbl.setVisible(False)
        else:
            key_ok = bool(self._api_key) and self._api_key != "your_groq_api_key_here"
            self.generate_btn.setEnabled(key_ok and not self._is_generating)
            self._key_warn_lbl.setVisible(not key_ok)

    # ─────────────────────────────────────────────────────────────────
    # Code generation
    # ─────────────────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt or self._is_generating:
            return

        if self._mode == "groq":
            key_ok = bool(self._api_key) and self._api_key != "your_groq_api_key_here"
            if not key_ok:
                QMessageBox.warning(
                    self, "API Key Missing",
                    "GROQ_API_KEY not found.\n\n"
                    "1. Open the .env file in the project root\n"
                    "2. Replace 'your_groq_api_key_here' with your key\n"
                    "3. Restart Coder AI\n\n"
                    "Get a free key at: https://console.groq.com/keys"
                )
                return
        else:
            if not self._local_model_loaded:
                QMessageBox.warning(
                    self, "Model Not Loaded",
                    "The local model is not loaded yet.\n\n"
                    "Click ⬇ Load Model in the sidebar first."
                )
                return

        self._is_generating = True
        self.generate_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.code_editor.clear()
        self._streamed_buf = ""

        history = self._current_history()
        history.append({"role": "user", "content": prompt})
        self._append_history("You", prompt, is_user=True)

        from prompts import get_system_prompt
        messages = [{"role": "system", "content": get_system_prompt("python")}] + history

        self._set_progress(0, "Starting generation…")

        if self._mode == "local":
            self._generator = CodeGeneratorWorker(messages=messages)
        else:
            self._generator = ApiGeneratorWorker(
                messages=messages,
                api_key=self._api_key,
                model=self._api_model or self._sidebar.model_combo.currentText(),
            )

        self._generator.progress.connect(self._on_gen_progress)
        self._generator.token.connect(self._on_token)
        self._generator.finished.connect(self._on_generation_done)
        self._generator.error.connect(self._on_generation_error)
        self._generator.start()

    def _on_gen_progress(self, pct: int, msg: str) -> None:
        self._progress_bar.setValue(pct)
        self._set_status(msg)

    def _on_token(self, chunk: str) -> None:
        self._streamed_buf += chunk
        code = self._extract_code_partial(self._streamed_buf)
        if code:
            self.code_editor.setPlainText(code)
            cursor = self.code_editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.code_editor.setTextCursor(cursor)

    def _on_generation_done(self, response: str) -> None:
        from prompts import extract_code, extract_explanation
        code        = extract_code(response, "python")
        explanation = extract_explanation(response)
        if code:
            self.code_editor.setPlainText(code)

        history = self._current_history()
        history.append({"role": "assistant", "content": response})
        self._append_history("Coder AI", explanation or response, is_user=False)

        # Auto-name session from first prompt
        if self._active_session_idx >= 0:
            sess = self._sessions[self._active_session_idx]
            if sess["name"].startswith("Chat ") and len(history) == 2:
                first_prompt = history[0]["content"]
                short_name   = first_prompt[:32] + ("…" if len(first_prompt) > 32 else "")
                sess["name"] = short_name
                self._session_title_lbl.setText(short_name)
                self._sidebar.rename_session(self._active_session_idx, short_name)

        self._save_sessions()

        self._progress_bar.setValue(100)
        self._set_status("Code generated — review in Code tab, then click ▶ Run")
        self._is_generating = False
        self.generate_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.prompt_input.clear()
        self._switch_tab(1)

    def _on_generation_error(self, err: str) -> None:
        self._is_generating = False
        self.generate_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._set_status(f"Error: {err[:80]}")
        self._append_output(f"Generation error:\n{err}", is_error=True)
        self._switch_tab(2)

    # ─────────────────────────────────────────────────────────────────
    # Code execution
    # ─────────────────────────────────────────────────────────────────

    def _on_run(self) -> None:
        code = self.code_editor.toPlainText().strip()
        if not code or self._is_running:
            return
        self._is_running = True
        self.run_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.output_display.clear()
        self._progress_bar.setValue(0)
        self._switch_tab(2)

        self._runner = CodeRunnerWorker(code)
        self._runner.progress.connect(self._on_run_progress)
        self._runner.log.connect(lambda msg: self._append_output(msg))
        self._runner.finished.connect(self._on_run_done)
        self._runner.error.connect(self._on_run_error)
        self._runner.start()

    def _on_run_progress(self, pct: int, msg: str) -> None:
        self._progress_bar.setValue(pct)
        self._progress_lbl.setText(msg)
        self._set_status(msg)

    def _on_run_done(self, result) -> None:
        from code_runner import format_output
        output, status = format_output(result)
        if output:
            self._append_output(output, is_error=status != "success")
        if result.installed_packages:
            self._append_output(f"\n✅ Auto-installed: {', '.join(result.installed_packages)}")
        if result.plot_files:
            count = len(result.plot_files)
            self._append_output(f"\n{'─' * 28}\n[{count} plot{'s' if count > 1 else ''} generated]")
            for idx, path in enumerate(result.plot_files, 1):
                self._append_plot_image(path, idx)

        self._is_running = False
        self.run_btn.setEnabled(True)
        self._update_generate_btn_state()

        if status == "success":
            self._progress_bar.setValue(100)
            self._progress_lbl.setText("✓ Executed successfully")
            self._set_status("✓ Code ran successfully")
        elif status == "timeout":
            self._progress_lbl.setText("⏱ Timed out")
            self._set_status("Execution timed out")
        else:
            self._progress_lbl.setText("✗ Execution failed")
            self._set_status("Code failed — see Output tab")

    def _on_run_error(self, err: str) -> None:
        self._is_running = False
        self.run_btn.setEnabled(True)
        self._update_generate_btn_state()
        self._progress_bar.setValue(0)
        self._append_output(f"Runner error:\n{err}", is_error=True)

    # ─────────────────────────────────────────────────────────────────
    # Utility helpers
    # ─────────────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent
        if obj is self.prompt_input and event.type() == QEvent.Type.KeyPress:
            if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                self._on_generate()
                return True
        return super().eventFilter(obj, event)

    def _set_progress(self, pct: int, msg: str) -> None:
        self._progress_bar.setValue(pct)
        self._progress_lbl.setText(msg)

    def _set_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)
        self.statusBar().showMessage(msg)

    def _append_history(self, sender: str, text: str, is_user: bool) -> None:
        cursor = self.history_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt_label = QTextCharFormat()
        fmt_label.setFontWeight(700)
        fmt_label.setForeground(QColor(ACCENT if is_user else GREEN))
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
    def _extract_code_partial(text: str) -> str:
        if "```python" in text:
            start = text.find("```python") + len("```python")
            end   = text.find("```", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        if "```" in text:
            start = text.find("```") + 3
            end   = text.find("```", start)
            return text[start:end].strip() if end != -1 else text[start:].strip()
        return ""

    def _copy_code(self) -> None:
        text = self.code_editor.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._set_status("Code copied to clipboard")

    def _clear_editor(self) -> None:
        self.code_editor.clear()

    def _clear_chat(self) -> None:
        self.history_display.clear()
        if self._active_session_idx >= 0:
            self._sessions[self._active_session_idx]["history"].clear()
        self._save_sessions()
        self._set_status("Conversation cleared")

    def _append_plot_image(self, path: str, idx: int) -> None:
        image = QImage(path)
        if image.isNull():
            self._append_output(f"[Plot {idx}: could not load — {path}]", is_error=True)
            return
        available = max(400, self.output_display.viewport().width() - 40)
        if image.width() > available:
            image = image.scaledToWidth(available, Qt.TransformationMode.SmoothTransformation)
        resource_name = f"plot_{idx}_{os.path.basename(path)}"
        doc = self.output_display.document()
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(resource_name), image)
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        img_fmt = QTextImageFormat()
        img_fmt.setName(resource_name)
        img_fmt.setWidth(image.width())
        img_fmt.setHeight(image.height())
        cursor.insertImage(img_fmt)
        self.output_display.setTextCursor(cursor)
        self.output_display.ensureCursorVisible()
