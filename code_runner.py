# code_runner.py
import subprocess
import sys
import tempfile
import os
import re
from dataclasses import dataclass


@dataclass
class RunResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    installed_packages: list = None

    def __post_init__(self):
        if self.installed_packages is None:
            self.installed_packages = []


# ── Package name mapping ──────────────────────────────────────────
# Some import names differ from their pip install name.
# e.g. "import cv2" needs "pip install opencv-python"
IMPORT_TO_PIP = {
    "cv2":           "opencv-python",
    "PIL":           "Pillow",
    "sklearn":       "scikit-learn",
    "bs4":           "beautifulsoup4",
    "yaml":          "pyyaml",
    "dotenv":        "python-dotenv",
    "serial":        "pyserial",
    "wx":            "wxPython",
    "gi":            "PyGObject",
    "usb":           "pyusb",
    "OpenGL":        "PyOpenGL",
    "attr":          "attrs",
    "dateutil":      "python-dateutil",
    "google.cloud":  "google-cloud",
    "jwt":           "PyJWT",
    "Crypto":        "pycryptodome",
    "magic":         "python-magic",
    "Image":         "Pillow",
}

# Packages that are part of Python stdlib — never try to pip install these
STDLIB_MODULES = {
    "os", "sys", "re", "math", "time", "datetime", "random", "json",
    "pathlib", "shutil", "subprocess", "threading", "multiprocessing",
    "collections", "itertools", "functools", "typing", "dataclasses",
    "abc", "io", "csv", "sqlite3", "hashlib", "hmac", "base64",
    "urllib", "http", "email", "html", "xml", "logging", "unittest",
    "argparse", "configparser", "tempfile", "glob", "fnmatch",
    "struct", "array", "queue", "socket", "ssl", "uuid", "copy",
    "pprint", "string", "textwrap", "traceback", "warnings", "inspect",
    "ast", "dis", "gc", "weakref", "contextlib", "enum", "decimal",
    "fractions", "statistics", "heapq", "bisect", "operator",
}


def extract_imports(code: str) -> list[str]:
    """
    Parse all import statements from code and return
    a list of top-level module names.

    Handles:
        import numpy
        import numpy as np
        from pandas import DataFrame
        from sklearn.linear_model import ...
    """
    modules = []

    # Match: import X, import X as Y, import X, Y
    for match in re.finditer(r"^import\s+([\w\s,]+)", code, re.MULTILINE):
        for part in match.group(1).split(","):
            name = part.strip().split(" as ")[0].strip().split(".")[0]
            if name:
                modules.append(name)

    # Match: from X import ...
    for match in re.finditer(r"^from\s+([\w.]+)\s+import", code, re.MULTILINE):
        name = match.group(1).strip().split(".")[0]
        if name:
            modules.append(name)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for m in modules:
        if m not in seen:
            seen.add(m)
            unique.append(m)

    return unique


def resolve_pip_name(import_name: str) -> str:
    """
    Convert an import name to its pip package name.
    Falls back to the import name itself if no mapping exists.
    """
    return IMPORT_TO_PIP.get(import_name, import_name)


def is_package_installed(module_name: str) -> bool:
    """Check if a module can be imported (i.e. is already installed)."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        capture_output=True,
    )
    return result.returncode == 0


def install_package(pip_name: str) -> tuple[bool, str]:
    """
    Run pip install for a single package.

    Returns:
        (success: bool, output: str)
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def auto_install_missing(code: str) -> tuple[list[str], list[str], str]:
    """
    Scan the code for imports, detect missing packages,
    and install them automatically.

    Returns:
        installed:  list of packages successfully installed
        failed:     list of packages that failed to install
        install_log: human-readable log of what happened
    """
    imports = extract_imports(code)
    installed = []
    failed = []
    log_lines = []

    for module in imports:
        # Skip stdlib modules — they're always available
        if module in STDLIB_MODULES:
            continue

        # Skip if already installed
        if is_package_installed(module):
            continue

        # Resolve the correct pip name
        pip_name = resolve_pip_name(module)
        log_lines.append(f"📦 Installing {pip_name}...")

        success, output = install_package(pip_name)

        if success:
            installed.append(pip_name)
            log_lines.append(f"   ✓ {pip_name} installed successfully")
        else:
            failed.append(pip_name)
            log_lines.append(f"   ✗ Failed to install {pip_name}")

    return installed, failed, "\n".join(log_lines)


def run_python_code(code: str, timeout: int = 30) -> RunResult:
    """
    Execute Python code safely in a subprocess.
    Automatically installs any missing packages before running.

    Args:
        code:    Python source code to execute
        timeout: Max seconds before killing the process

    Returns:
        RunResult with output, status, and installed packages list
    """

    # ── Step 1: Auto-install missing packages ─────────────────────
    installed, failed, install_log = auto_install_missing(code)

    # ── Step 2: Write code to temp file ───────────────────────────
    tmp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    )

    try:
        tmp_file.write(code)
        tmp_file.flush()
        tmp_file.close()

        # ── Step 3: Run the code ───────────────────────────────────
        result = subprocess.run(
            [sys.executable, tmp_file.name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Prepend install log to output if packages were installed
        prefix = (install_log + "\n" + "─" * 30 + "\n") if install_log else ""

        return RunResult(
            success=result.returncode == 0,
            stdout=prefix + result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            installed_packages=installed,
        )

    except subprocess.TimeoutExpired:
        return RunResult(
            success=False,
            stdout=install_log,
            stderr=f"⏱️ Timed out after {timeout}s — check for infinite loops.",
            exit_code=-1,
            timed_out=True,
            installed_packages=installed,
        )

    except Exception as e:
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Failed to launch process: {str(e)}",
            exit_code=-1,
            installed_packages=installed,
        )

    finally:
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)


def format_output(result: RunResult) -> tuple[str, str]:
    """
    Format a RunResult into display text and a status string.

    Returns:
        (display_text, status)  where status = "success"|"error"|"timeout"
    """
    lines = []

    if result.timed_out:
        return result.stderr, "timeout"

    if result.stdout:
        lines.append(result.stdout.rstrip())

    if result.stderr:
        lines.append("── stderr ──────────────────")
        lines.append(result.stderr.rstrip())

    if not result.stdout and not result.stderr:
        lines.append("✓ Ran successfully with no output.")

    display = "\n".join(lines)
    status = "success" if result.success else "error"
    return display, status


# ── Self-test ─────────────────────────────────────────────────────
if __name__ == "__main__":

    print("Test 1: Basic print")
    r = run_python_code('print("Hello!")')
    assert r.success, "❌ Test 1 failed"
    print("  ✅ passed\n")

    print("Test 2: Syntax error")
    r = run_python_code("def bad(:\n    pass")
    assert not r.success, "❌ Test 2 failed"
    print("  ✅ passed\n")

    print("Test 3: Runtime error")
    r = run_python_code("print(1/0)")
    assert not r.success, "❌ Test 3 failed"
    print("  ✅ passed\n")

    print("Test 4: Timeout")
    r = run_python_code("while True: pass", timeout=3)
    assert r.timed_out, "❌ Test 4 failed"
    print("  ✅ passed\n")

    print("Test 5: Auto-install + use matplotlib")
    r = run_python_code("import matplotlib; print(matplotlib.__version__)")
    print(f"  installed={r.installed_packages}, output={r.stdout.strip()}")
    assert r.success, "❌ Test 5 failed"
    print("  ✅ passed\n")

    print("All tests passed ✅")