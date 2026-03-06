# code_runner.py
# Detects imports, auto-installs missing packages, then executes code.
#
# Bug fix: original regex used [\w\s,]+ which greedily ate newlines,
# causing every import after the first to be silently skipped.
# Fixed to [^\n]+ so each import line is matched independently.

import importlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field


# ── Result dataclass ─────────────────────────────────────────────

@dataclass
class RunResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    installed_packages: list = field(default_factory=list)
    plot_files: list = field(default_factory=list)


# ── Import-name → pip-name mapping ───────────────────────────────
# Add entries here whenever an import name differs from the pip package name.

IMPORT_TO_PIP: dict[str, str] = {
    "cv2":          "opencv-python",
    "PIL":          "Pillow",
    "Image":        "Pillow",
    "sklearn":      "scikit-learn",
    "bs4":          "beautifulsoup4",
    "yaml":         "pyyaml",
    "dotenv":       "python-dotenv",
    "serial":       "pyserial",
    "usb":          "pyusb",
    "OpenGL":       "PyOpenGL",
    "attr":         "attrs",
    "dateutil":     "python-dateutil",
    "jwt":          "PyJWT",
    "Crypto":       "pycryptodome",
    "magic":        "python-magic",
    "wx":           "wxPython",
    "gi":           "PyGObject",
    "google.cloud": "google-cloud",
    "skimage":      "scikit-image",
    "mpl_toolkits": "matplotlib",
    "mpl":          "matplotlib",
}

# Standard-library modules — never attempt to pip-install these.
STDLIB_MODULES: frozenset[str] = frozenset({
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
    "platform", "signal", "pickle", "shelve", "zipfile", "tarfile",
    "gzip", "bz2", "lzma", "zlib", "binascii", "codecs", "locale",
    "gettext", "getopt", "cmd", "shlex", "readline", "rlcompleter",
    "curses", "tkinter", "turtle", "cmath", "numbers", "types",
    "importlib", "pkgutil", "unittest", "doctest", "pdb", "profile",
    "timeit", "trace", "sys", "builtins", "future", "__future__",
    "concurrent", "asyncio", "contextvars",
})


# ── Matplotlib plot-capture ───────────────────────────────────────
# Unique marker printed to stdout for each saved figure path.
_PLOT_MARKER = "__PLOT__:"


def _make_plot_preamble(plot_dir: str) -> str:
    """
    Return Python source that must be prepended before user code when
    matplotlib is detected.

    What it does
    ─────────────
    1. Forces the non-interactive Agg backend (no GUI window needed).
    2. Monkey-patches matplotlib.pyplot.show() so every call saves all
       open figures as PNG files into *plot_dir* and prints their paths
       to stdout prefixed with _PLOT_MARKER.
    3. Registers the same hook with atexit so figures are saved even if
       the user forgets to call plt.show() (e.g. the script just creates
       figures and exits).

    All injected names use a _cap suffix to avoid colliding with user
    variables.
    """
    pd = repr(plot_dir)
    mk = repr(_PLOT_MARKER)
    return (
        f"import matplotlib as _mpl_cap; _mpl_cap.use('Agg')\n"
        f"import matplotlib.pyplot as _plt_cap\n"
        f"import os as _os_cap, atexit as _atexit_cap\n"
        f"_PLOT_DIR_CAP = {pd}\n"
        f"_PLOT_MK_CAP  = {mk}\n"
        f"_plot_idx_cap = [0]\n"
        f"\n"
        f"def _show_cap(*_a, **_kw):\n"
        f"    for _fn in _plt_cap.get_fignums():\n"
        f"        _plot_idx_cap[0] += 1\n"
        f"        _p = _os_cap.path.join(_PLOT_DIR_CAP,\n"
        f"                 'plot_%03d_f%d.png' % (_plot_idx_cap[0], _fn))\n"
        f"        _plt_cap.figure(_fn).savefig(_p, bbox_inches='tight', dpi=150)\n"
        f"        print(_PLOT_MK_CAP + _p)\n"
        f"    _plt_cap.close('all')\n"
        f"\n"
        f"_plt_cap.show = _show_cap\n"
        f"_atexit_cap.register(_show_cap)\n"
        f"\n"
    )


# ── Import extraction ─────────────────────────────────────────────

def extract_imports(code: str) -> list[str]:
    """
    Parse all import statements and return a deduplicated list of
    top-level module names.

    KEY FIX: uses [^\\n]+ (not [\\w\\s,]+) so the regex never
    crosses newlines and swallows subsequent import lines.

    Handles:
        import numpy
        import numpy as np
        import os, sys, re
        from pandas import DataFrame
        from sklearn.linear_model import LinearRegression
        import matplotlib.pyplot as plt
    """
    modules: list[str] = []

    # ── "import X" / "import X as Y" / "import X, Y" ─────────────
    # [^\n]+ matches the rest of the line only — no newline crossing
    for match in re.finditer(r"^import\s+([^\n]+)", code, re.MULTILINE):
        raw = match.group(1).split("#")[0]   # strip inline comments
        for part in raw.split(","):
            name = part.strip().split(" as ")[0].strip().split(".")[0]
            if name:
                modules.append(name)

    # ── "from X import ..." ───────────────────────────────────────
    for match in re.finditer(r"^from\s+([\w.]+)\s+import", code, re.MULTILINE):
        name = match.group(1).strip().split(".")[0]
        if name:
            modules.append(name)

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for m in modules:
        if m and m not in seen:
            seen.add(m)
            unique.append(m)

    return unique


# ── Package detection ─────────────────────────────────────────────

def resolve_pip_name(import_name: str) -> str:
    """Map an import name to its pip install name (falls back to itself)."""
    return IMPORT_TO_PIP.get(import_name, import_name)


def is_package_installed(module_name: str) -> bool:
    """
    Check whether a module is importable in the *current* Python environment.

    Uses importlib.util.find_spec() — same environment as the running process,
    no subprocess overhead, and consistent with what the code execution subprocess
    will see (both use the same site-packages directory).
    """
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


# ── Package installation ─────────────────────────────────────────

def install_package(pip_name: str) -> tuple[bool, str]:
    """
    pip-install a single package into the current Python environment.
    Invalidates the import cache afterwards so the package is immediately
    findable by is_package_installed() and importlib in the same process.

    Returns:
        (success: bool, combined_output: str)
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_name, "--quiet"],
        capture_output=True,
        text=True,
    )
    importlib.invalidate_caches()   # make the new package findable right away
    return result.returncode == 0, result.stdout + result.stderr


# ── All-in-one: detect + install ─────────────────────────────────

def auto_install_missing(
    code: str,
    progress_cb=None,
) -> tuple[list[str], list[str], str]:
    """
    Scan *code* for import statements, find which packages are missing,
    and pip-install them one by one.

    Args:
        code:        Python source to scan
        progress_cb: optional callable(message) for progress updates

    Returns:
        (installed, failed, install_log)
    """
    imports    = extract_imports(code)
    installed  = []
    failed     = []
    log_lines  = []

    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    for module in imports:
        if module in STDLIB_MODULES:
            continue
        if is_package_installed(module):
            continue

        pip_name = resolve_pip_name(module)
        _cb(f"[PKG] Installing {pip_name}...")
        log_lines.append(f"[PKG] Installing {pip_name}...")

        success, output = install_package(pip_name)

        if success:
            installed.append(pip_name)
            msg = f"      [OK] {pip_name} installed successfully"
        else:
            failed.append(pip_name)
            msg = f"      [FAIL] {pip_name} could not be installed"

        _cb(msg)
        log_lines.append(msg)

    return installed, failed, "\n".join(log_lines)


# ── Code execution ────────────────────────────────────────────────

def run_python_code(
    code: str,
    timeout: int = 60,
    progress_cb=None,
) -> RunResult:
    """
    Full pipeline: detect missing packages → install → execute.

    Args:
        code:        Python source to run
        timeout:     max seconds before killing the process
        progress_cb: optional callable(message) for step updates

    Returns:
        RunResult with stdout, stderr, exit code, and installed package list
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    # ── 1. Detect & install missing packages ─────────────────────
    _cb("Checking dependencies...")
    imports = extract_imports(code)
    missing_modules = [
        m for m in imports
        if m not in STDLIB_MODULES and not is_package_installed(m)
    ]

    installed: list[str] = []
    failed:    list[str] = []
    log_lines: list[str] = []

    if missing_modules:
        pip_names = [resolve_pip_name(m) for m in missing_modules]
        _cb(f"Installing {len(pip_names)} missing package(s): {', '.join(pip_names)}")

        for pip_name in pip_names:
            _cb(f"[PKG] Installing {pip_name}...")
            log_lines.append(f"[PKG] Installing {pip_name}...")
            success, _ = install_package(pip_name)
            if success:
                installed.append(pip_name)
                msg = f"      [OK] {pip_name} installed"
            else:
                failed.append(pip_name)
                msg = f"      [FAIL] {pip_name} could not be installed"
            _cb(msg)
            log_lines.append(msg)
    else:
        _cb("✓ All dependencies satisfied.")

    # ── 2. Prepare code: inject plot-capture preamble if needed ──
    #    matplotlib.pyplot.show() in a subprocess has no display
    #    context, so we replace it with a save-to-PNG hook that
    #    writes figure files into a temp directory and prints each
    #    path to stdout prefixed with _PLOT_MARKER.
    _cb("Executing code...")
    imports_found  = extract_imports(code)
    uses_mpl       = any(
        m in ("matplotlib", "mpl", "mpl_toolkits", "mpl_finance")
        for m in imports_found
    )
    plot_dir: str | None = None
    if uses_mpl:
        plot_dir = tempfile.mkdtemp(prefix="ide_plots_")
        run_code = _make_plot_preamble(plot_dir) + code
    else:
        run_code = code

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(run_code)
        tmp.flush()
        tmp.close()

        # ── 3. Run in a subprocess with the same Python executable ─
        result = subprocess.run(
            [sys.executable, tmp.name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # ── 4. Parse stdout for plot-file markers ─────────────────
        plot_files: list[str] = []
        if plot_dir:
            clean_lines: list[str] = []
            for line in result.stdout.splitlines(keepends=True):
                stripped = line.rstrip("\r\n")
                if stripped.startswith(_PLOT_MARKER):
                    path = stripped[len(_PLOT_MARKER):]
                    if os.path.exists(path):
                        plot_files.append(path)
                else:
                    clean_lines.append(line)
            raw_stdout = "".join(clean_lines)
        else:
            raw_stdout = result.stdout

        prefix = ("\n".join(log_lines) + "\n" + "─" * 32 + "\n") if log_lines else ""

        return RunResult(
            success=result.returncode == 0,
            stdout=prefix + raw_stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            installed_packages=installed,
            plot_files=plot_files,
        )

    except subprocess.TimeoutExpired:
        return RunResult(
            success=False,
            stdout="\n".join(log_lines),
            stderr=f"⏱ Timed out after {timeout}s — check for infinite loops.",
            exit_code=-1,
            timed_out=True,
            installed_packages=installed,
        )

    except Exception as exc:
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Failed to launch process: {exc}",
            exit_code=-1,
            installed_packages=installed,
        )

    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


# ── Output formatting ─────────────────────────────────────────────

def format_output(result: RunResult) -> tuple[str, str]:
    """
    Format a RunResult into (display_text, status).
    status is one of: "success" | "error" | "timeout"
    """
    if result.timed_out:
        return result.stderr, "timeout"

    lines: list[str] = []
    if result.stdout:
        lines.append(result.stdout.rstrip())
    if result.stderr:
        lines.append("── stderr ──────────────────")
        lines.append(result.stderr.rstrip())
    if not result.stdout and not result.stderr:
        if result.plot_files:
            n = len(result.plot_files)
            lines.append(f"✓ Ran successfully — {n} plot{'s' if n > 1 else ''} generated.")
        else:
            lines.append("✓ Ran successfully with no output.")

    return "\n".join(lines), "success" if result.success else "error"
