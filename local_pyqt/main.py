# main.py — entry point for the local PyQt6 AI Coder IDE
import sys
import os

# ── Interpreter guard ─────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_EXPECTED_PYTHON = os.path.join(_THIS_DIR, ".venv", "Scripts", "python.exe")
_RUNNING_PYTHON  = os.path.normcase(os.path.abspath(sys.executable))

if os.path.exists(_EXPECTED_PYTHON) and \
        _RUNNING_PYTHON != os.path.normcase(os.path.abspath(_EXPECTED_PYTHON)):
    print("=" * 60)
    print("ERROR: Wrong Python interpreter!")
    print(f"  Running : {sys.executable}")
    print(f"  Expected: {_EXPECTED_PYTHON}")
    print()
    print("Use run.bat, or set your IDE interpreter to:")
    print(f"  {_EXPECTED_PYTHON}")
    print("=" * 60)
    sys.exit(1)

# ── DLL search path fix (MUST happen before importing PyQt6) ──────
# PyQt6 modifies Windows' DLL search context on startup. If torch is
# imported later inside a QThread, Windows can't find the CUDA DLLs
# anymore (WinError 1114 / DLL_INIT_FAILED). Registering the torch
# lib directory with os.add_dll_directory() makes it permanently
# visible to all threads regardless of PyQt6's changes.
def _register_torch_dll_dir() -> None:
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(torch_lib):
            os.add_dll_directory(torch_lib)          # Python 3.8+ Windows only
            # Also prepend to PATH as a belt-and-suspenders fallback
            os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass   # if torch isn't installed yet, skip silently

_register_torch_dll_dir()

# ── Ensure local_pyqt/ is on Python path ─────────────────────────
sys.path.insert(0, _THIS_DIR)

# ── Now it is safe to import PyQt6 ───────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Coder IDE — Local")
    app.setOrganizationName("AICoderIDE")

    default_font = QFont("Segoe UI", 10)
    app.setFont(default_font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
