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
# Each entry describes HOW to install the runtime for a language.
# "steps" is an ordered list of commands; they are run sequentially.
# "cannot_install" marks runtimes that must be installed manually.

RUNTIME_INFO: dict[str, dict] = {
    "php": {
        "name":    "PHP 8",
        "check":   "php",
        "steps": [
            ["winget", "install", "PHP.PHP.8.3",
             "--accept-source-agreements", "--accept-package-agreements"],
        ],
        "cannot_install": False,
        "url": "https://www.php.net/downloads",
    },
    "csharp": {
        "name":    "dotnet-script (C# scripting)",
        "check":   "dotnet-script",
        "steps": [
            # Step 1: install .NET SDK (required before dotnet tool install)
            ["winget", "install", "Microsoft.DotNet.SDK.8",
             "--accept-source-agreements", "--accept-package-agreements"],
            # Step 2: install dotnet-script global tool
            ["dotnet", "tool", "install", "-g", "dotnet-script"],
        ],
        "cannot_install": False,
        "url": "https://github.com/dotnet-script/dotnet-script",
    },
    "kotlin": {
        "name":    "Kotlin (kotlinc)",
        "check":   "kotlinc",
        "steps": [
            ["winget", "install", "JetBrains.Kotlin",
             "--accept-source-agreements", "--accept-package-agreements"],
        ],
        "cannot_install": False,
        "url": "https://kotlinlang.org/docs/command-line.html",
    },
    "dart": {
        "name":    "Dart SDK",
        "check":   "dart",
        "steps": [
            ["winget", "install", "Dart.Dart",
             "--accept-source-agreements", "--accept-package-agreements"],
        ],
        "cannot_install": False,
        "url": "https://dart.dev/get-dart",
    },
    "foxpro": {
        "name":    "Visual FoxPro 9",
        "check":   "vfp9",
        "steps":   [],
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


def is_runtime_available(language: str) -> bool:
    """Return True if the runtime for *language* is on PATH (or is Python itself)."""
    if language == "python":
        return True
    cfg = LANGUAGE_CONFIG.get(language)
    if cfg is None:
        return False
    return shutil.which(cfg["cmd"]()[0]) is not None


def install_runtime(
    language: str,
    progress_cb=None,
) -> tuple[bool, str]:
    """
    Run the sequential install steps for *language*'s runtime.

    Each step is a command list passed to subprocess.run().
    Progress messages are emitted via *progress_cb(msg)* if provided.

    Returns:
        (success: bool, log: str)
        success is True when all steps finished without error codes.
        Even on success the caller should warn the user to restart their
        terminal so the new PATH entry is visible.
    """
    def _cb(msg: str) -> None:
        if progress_cb:
            progress_cb(msg)

    info = RUNTIME_INFO.get(language)
    if info is None:
        return False, f"No install info registered for language: {language!r}"

    if info.get("cannot_install"):
        return False, info.get("manual_note", "This runtime cannot be installed automatically.")

    log_lines: list[str] = []

    for step in info["steps"]:
        cmd_str = " ".join(step)
        _cb(f"[INSTALL] Running: {cmd_str}")
        log_lines.append(f"[INSTALL] Running: {cmd_str}")

        try:
            result = subprocess.run(
                step,
                capture_output=True,
                text=True,
                timeout=300,          # 5 minutes per step
            )
            if result.stdout.strip():
                log_lines.append(result.stdout.strip())
            if result.returncode != 0:
                err = result.stderr.strip() or f"Exit code {result.returncode}"
                log_lines.append(f"[ERROR] {err}")
                _cb(f"[ERROR] Step failed: {cmd_str}")
                return False, "\n".join(log_lines)
            else:
                _cb(f"[OK] Completed: {cmd_str}")
                log_lines.append(f"[OK] Completed: {cmd_str}")

        except subprocess.TimeoutExpired:
            log_lines.append(f"[ERROR] Timed out after 5 minutes: {cmd_str}")
            _cb("[ERROR] Install step timed out.")
            return False, "\n".join(log_lines)
        except FileNotFoundError as exc:
            log_lines.append(f"[ERROR] Command not found: {exc}")
            _cb(f"[ERROR] Command not found: {exc}")
            return False, "\n".join(log_lines)
        except Exception as exc:
            log_lines.append(f"[ERROR] Unexpected error: {exc}")
            _cb(f"[ERROR] {exc}")
            return False, "\n".join(log_lines)

    # Verify the binary is now visible on PATH
    if is_runtime_available(language):
        log_lines.append(f"\n✅ {info['name']} is now available on PATH.")
    else:
        log_lines.append(
            f"\n⚠ Install steps completed but '{info['check']}' is still not found on PATH.\n"
            "  You may need to restart your system or open a new terminal session\n"
            "  for the PATH change to take effect."
        )

    return True, "\n".join(log_lines)


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
