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
import shutil
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


# ── Supported languages ───────────────────────────────────────────
# Maps language key → (command factory, file extension).
# cmd is a zero-arg callable so sys.executable is resolved at call time.

LANGUAGE_CONFIG: dict[str, dict] = {
    "python": {
        "cmd": lambda: [sys.executable],
        "ext": ".py",
    },
    # JavaScript — requires: Node.js on PATH (https://nodejs.org/)
    "javascript": {
        "cmd": lambda: ["node"],
        "ext": ".js",
    },
    # TypeScript — requires: Node.js on PATH; tsx is downloaded on-demand via npx
    "typescript": {
        "cmd": lambda: ["npx", "--yes", "tsx"],
        "ext": ".ts",
    },
    # Go — requires: Go toolchain on PATH (https://go.dev/)
    "go": {
        "cmd": lambda: ["go", "run"],
        "ext": ".go",
    },
    "php": {
        "cmd": lambda: ["php"],
        "ext": ".php",
    },
    # C# / ASP.NET — requires: dotnet tool install -g dotnet-script
    "csharp": {
        "cmd": lambda: ["dotnet-script"],
        "ext": ".csx",
    },
    # Kotlin — requires: kotlinc on PATH (https://kotlinlang.org/docs/command-line.html)
    "kotlin": {
        "cmd": lambda: ["kotlinc", "-script"],
        "ext": ".kts",
    },
    # Flutter / Dart — requires: dart on PATH (https://dart.dev/get-dart)
    # Standalone Dart scripts run directly; Flutter app code needs `flutter run`
    "dart": {
        "cmd": lambda: ["dart"],
        "ext": ".dart",
    },
    # Visual FoxPro — requires VFP9 runtime on PATH.
    # vfp9.exe does not support clean headless script execution;
    # code generation works fully but Run Code will show an error if
    # vfp9 is not on PATH — open the .prg in the VFP IDE instead.
    "foxpro": {
        "cmd": lambda: ["vfp9", "-t"],
        "ext": ".prg",
    },
}


# ── Runtime availability & auto-install ──────────────────────────
#
# Each RUNTIME_INFO entry has:
#   "name"            — human-readable runtime name
#   "check"           — executable to look for on PATH
#   "strategies"      — ordered list of install strategies to try
#     Each strategy:  {"label": str, "steps": [[cmd, arg, ...], ...]}
#   "cannot_install"  — True for runtimes that can only be installed manually
#   "url"             — manual download URL shown on failure
#   "post_install_note" (optional) — extra guidance shown after success
#   "manual_note"     — message shown when cannot_install is True

RUNTIME_INFO: dict[str, dict] = {
    "javascript": {
        "name":    "Node.js",
        "check":   "node",
        "strategies": [
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "OpenJS.NodeJS.LTS",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
            {
                "label": "Chocolatey",
                "steps": [["choco", "install", "nodejs-lts", "-y"]],
            },
        ],
        "cannot_install": False,
        "url": "https://nodejs.org/en/download/",
    },
    "typescript": {
        "name":    "Node.js (required for TypeScript / tsx)",
        "check":   "node",    # tsx runs via npx — only node needs to be installed
        "strategies": [
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "OpenJS.NodeJS.LTS",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
            {
                "label": "Chocolatey",
                "steps": [["choco", "install", "nodejs-lts", "-y"]],
            },
        ],
        "cannot_install": False,
        "url": "https://nodejs.org/en/download/",
        "post_install_note": (
            "TypeScript files are executed via 'npx tsx' — tsx is downloaded\n"
            "automatically by npx on first use. No separate TypeScript install needed."
        ),
    },
    "go": {
        "name":    "Go",
        "check":   "go",
        "strategies": [
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "GoLang.Go",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
            {
                "label": "Chocolatey",
                "steps": [["choco", "install", "golang", "-y"]],
            },
        ],
        "cannot_install": False,
        "url": "https://go.dev/dl/",
    },
    "php": {
        "name":    "PHP 8",
        "check":   "php",
        "strategies": [
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "PHP.PHP",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
            {
                "label": "Chocolatey",
                "steps": [["choco", "install", "php", "-y"]],
            },
        ],
        "cannot_install": False,
        "url": "https://www.php.net/downloads",
    },
    "csharp": {
        "name":    "dotnet-script (C# scripting)",
        "check":   "dotnet-script",
        "strategies": [
            {
                "label": "winget + dotnet tool",
                "steps": [
                    # Step 1 — install .NET SDK via winget
                    ["winget", "install", "Microsoft.DotNet.SDK.8",
                     "--accept-source-agreements", "--accept-package-agreements"],
                    # Step 2 — install dotnet-script as a global .NET tool
                    ["dotnet", "tool", "install", "-g", "dotnet-script"],
                ],
            },
        ],
        "cannot_install": False,
        "url": "https://github.com/dotnet-script/dotnet-script",
        "post_install_note": (
            "dotnet-script is installed as a global .NET tool.\n"
            "If 'dotnet-script' is still not found after install, restart the app —\n"
            "the .NET tools folder (~/.dotnet/tools) must be on PATH."
        ),
    },
    "kotlin": {
        "name":    "Kotlin (kotlinc)",
        "check":   "kotlinc",
        "strategies": [
            {
                "label": "Chocolatey",        # choco has a reliable kotlinc package
                "steps": [["choco", "install", "kotlinc", "-y"]],
            },
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "JetBrains.Kotlin.Compiler",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
        ],
        "cannot_install": False,
        "url": "https://kotlinlang.org/docs/command-line.html",
        "post_install_note": (
            "Kotlin requires a JDK 17+ on PATH.\n"
            "Install it with:  winget install Microsoft.OpenJDK.21"
        ),
    },
    "dart": {
        "name":    "Dart SDK",
        "check":   "dart",
        "strategies": [
            {
                "label": "winget",
                "steps": [
                    ["winget", "install", "Dart.Dart",
                     "--accept-source-agreements", "--accept-package-agreements"],
                ],
            },
            {
                "label": "Chocolatey",
                "steps": [["choco", "install", "dart-sdk", "-y"]],
            },
        ],
        "cannot_install": False,
        "url": "https://dart.dev/get-dart",
    },
    "foxpro": {
        "name":    "Visual FoxPro 9",
        "check":   "vfp9",
        "strategies": [],
        "cannot_install": True,
        "url": "https://vfpx.github.io/",
        "manual_note": (
            "Visual FoxPro 9 is a legacy product and cannot be installed automatically.\n\n"
            "Options:\n"
            "  • Download the free VFP9 SP2 runtime from https://vfpx.github.io/\n"
            "  • Open the generated .prg file directly in the Visual FoxPro 9 IDE\n\n"
            "Code generation and editing work fully — only ▶ Run Code requires the runtime."
        ),
    },
}


def _refresh_windows_path() -> bool:
    """
    Re-read the user and system PATH from the Windows registry and update
    os.environ["PATH"] in the running process.

    winget / choco update the registry when they install, but not the
    environment of already-running processes.  Calling this after a
    successful install lets the app find newly-added executables without
    restarting, so `shutil.which()` and subprocess calls work immediately.

    Returns True on success, False if not on Windows or if the registry
    read fails.
    """
    try:
        import winreg
        parts: list[str] = []
        for root, subkey in [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    if val:
                        parts.append(val)
            except (FileNotFoundError, OSError):
                pass
        if parts:
            os.environ["PATH"] = os.pathsep.join(parts)
        return True
    except Exception:
        return False


def is_winget_available() -> bool:
    """Return True if winget (Windows Package Manager) is on PATH."""
    return shutil.which("winget") is not None


def is_choco_available() -> bool:
    """Return True if Chocolatey (choco) is on PATH."""
    return shutil.which("choco") is not None


def is_runtime_available(language: str) -> bool:
    """
    Return True if the runtime for *language* is on PATH.

    Python is always available (we're running in it).
    For other languages, the "check" executable from RUNTIME_INFO is used
    when present; otherwise the first word of LANGUAGE_CONFIG["cmd"]() is used.
    """
    if language == "python":
        return True
    # Use the dedicated "check" binary from RUNTIME_INFO if registered
    info = RUNTIME_INFO.get(language, {})
    check_exe = info.get("check")
    if check_exe:
        return shutil.which(check_exe) is not None
    # Fall back to the first element of the runner command
    cfg = LANGUAGE_CONFIG.get(language)
    if cfg is None:
        return False
    return shutil.which(cfg["cmd"]()[0]) is not None


def install_runtime(
    language: str,
    progress_cb=None,
) -> tuple[bool, str]:
    """
    Install the runtime for *language* by trying each strategy in order.

    Strategies are tried sequentially:
      - If the strategy's primary tool (winget / choco) is not on PATH,
        that strategy is skipped and the next one is tried.
      - After every successful strategy, the Windows PATH is refreshed
        from the registry so the new binary is findable immediately.

    Returns:
        (success: bool, log: str)
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    info = RUNTIME_INFO.get(language)
    if info is None:
        return False, f"No install info registered for language: {language!r}"

    if info.get("cannot_install"):
        return False, info.get("manual_note", "This runtime cannot be installed automatically.")

    strategies = info.get("strategies", [])
    if not strategies:
        return False, f"No install strategies defined for {language!r}."

    all_logs: list[str] = []

    for strategy in strategies:
        label = strategy.get("label", "unknown")
        steps = strategy.get("steps", [])
        if not steps:
            continue

        # Skip strategy if its primary tool isn't available
        first_cmd = steps[0][0] if steps[0] else ""
        if first_cmd == "winget" and not is_winget_available():
            msg = f"[SKIP] winget not found — skipping '{label}' strategy."
            _cb(msg)
            all_logs.append(msg)
            continue
        if first_cmd == "choco" and not is_choco_available():
            msg = f"[SKIP] Chocolatey not found — skipping '{label}' strategy."
            _cb(msg)
            all_logs.append(msg)
            continue

        _cb(f"\n── Strategy: {label} ────────────────────────")
        all_logs.append(f"\n── Strategy: {label} ────────────────────────")

        strategy_ok = True
        for step in steps:
            cmd_str = " ".join(step)
            _cb(f"[RUN] {cmd_str}")
            all_logs.append(f"[RUN] {cmd_str}")
            try:
                result = subprocess.run(
                    step,
                    capture_output=True,
                    text=True,
                    timeout=300,     # 5 minutes per step
                )
                out = result.stdout.strip()
                err = result.stderr.strip()
                if out:
                    all_logs.append(out)
                if result.returncode != 0:
                    msg = err or f"Exit code {result.returncode}"
                    all_logs.append(f"[FAIL] {msg}")
                    _cb(f"[FAIL] Step failed: {cmd_str}")
                    strategy_ok = False
                    break
                else:
                    _cb(f"[OK] Done: {cmd_str}")
                    all_logs.append(f"[OK] Done.")
            except subprocess.TimeoutExpired:
                all_logs.append(f"[FAIL] Timed out (5 min): {cmd_str}")
                _cb("[FAIL] Step timed out.")
                strategy_ok = False
                break
            except FileNotFoundError as exc:
                all_logs.append(f"[FAIL] Command not found: {exc}")
                _cb(f"[FAIL] {exc}")
                strategy_ok = False
                break
            except Exception as exc:
                all_logs.append(f"[FAIL] Unexpected error: {exc}")
                _cb(f"[FAIL] {exc}")
                strategy_ok = False
                break

        if strategy_ok:
            # Refresh the process PATH from registry so new binaries are found now
            _cb("[INFO] Refreshing PATH from Windows registry…")
            _refresh_windows_path()

            note = info.get("post_install_note", "")
            if note:
                _cb(f"[NOTE] {note}")
                all_logs.append(f"\n[NOTE] {note}")

            check = info.get("check", "")
            if is_runtime_available(language):
                all_logs.append(f"\n✅ {info['name']} is now available on PATH.")
            else:
                all_logs.append(
                    f"\n⚠ Install completed but '{check}' is still not found on PATH.\n"
                    "  Close and reopen this app (or log off/on) to apply the new PATH."
                )
            return True, "\n".join(all_logs)

    # All strategies failed or were skipped
    url = info.get("url", "")
    all_logs.append(
        f"\n❌ Could not auto-install {info.get('name', language)}.\n"
        f"   Possible fixes:\n"
        f"   • Install winget:  https://aka.ms/winget\n"
        f"   • Install Chocolatey:  https://chocolatey.org/install\n"
        f"   • Manual download:  {url}"
    )
    return False, "\n".join(all_logs)


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


# ── Generic (non-Python) code runner ─────────────────────────────

def _run_generic(
    code: str,
    language: str,
    timeout: int = 60,
    progress_cb=None,
) -> RunResult:
    """
    Execute *code* using the runtime registered in LANGUAGE_CONFIG[language].
    No auto-install is attempted — the runtime must already be on PATH.
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    cfg = LANGUAGE_CONFIG.get(language)
    if cfg is None:
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Unsupported language: {language!r}. "
                   f"Supported: {list(LANGUAGE_CONFIG)}",
            exit_code=-1,
        )

    cmd = cfg["cmd"]()
    ext = cfg["ext"]

    _cb(f"Executing {language} code...")
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=ext, delete=False, encoding="utf-8"
    )
    try:
        tmp.write(code)
        tmp.flush()
        tmp.close()

        result = subprocess.run(
            cmd + [tmp.name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        _cb("✓ Execution complete." if result.returncode == 0 else "✗ Execution failed.")
        return RunResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )

    except subprocess.TimeoutExpired:
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Timed out after {timeout}s — check for infinite loops.",
            exit_code=-1,
            timed_out=True,
        )
    except FileNotFoundError:
        return RunResult(
            success=False,
            stdout="",
            stderr=(
                f"'{cmd[0]}' was not found on PATH.\n"
                f"Install {language.upper()} and make sure it is in your system PATH."
            ),
            exit_code=-1,
        )
    except Exception as exc:
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Failed to launch {language} process: {exc}",
            exit_code=-1,
        )
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


# ── Code execution ────────────────────────────────────────────────

def run_python_code(
    code: str,
    timeout: int = 60,
    progress_cb=None,
    language: str = "python",
) -> RunResult:
    """
    Full pipeline for the selected language.

    For Python:  detect missing packages → auto-install → execute
                 (matplotlib figures are captured and returned as PNGs)
    For others:  write to a temp file and execute with the appropriate
                 runtime (e.g. `php`, `node`) — no auto-install step.

    Args:
        code:        Source code to run
        timeout:     Max seconds before killing the process
        progress_cb: Optional callable(message) for step updates
        language:    One of the keys in LANGUAGE_CONFIG ("python", "php", …)

    Returns:
        RunResult with stdout, stderr, exit code, and optional plot paths
    """
    # ── Non-Python path (simple runner) ──────────────────────────
    if language != "python":
        return _run_generic(code, language=language, timeout=timeout,
                            progress_cb=progress_cb)

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
