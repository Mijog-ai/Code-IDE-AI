# components/editor.py
import streamlit as st
from streamlit_ace import st_ace
from code_runner import run_python_code, format_output


def render_editor_panel():
    """
    Render the right-side editor panel containing:
    - ACE code editor (editable, syntax highlighted)
    - Run button
    - Output display box
    """

    # ── Panel header ──────────────────────────────────────────────
    st.markdown(
        '<div class="panel-header">📝 &nbsp; CODE EDITOR</div>',
        unsafe_allow_html=True
    )

    # ── Toolbar row: language tag + action buttons ─────────────────
    tool_col1, tool_col2, tool_col3 = st.columns([2, 1, 1])

    with tool_col1:
        st.markdown(
            '<span style="'
            'background:#fef3c7;'
            'color:#d97706;'
            'font-size:0.72rem;'
            'font-weight:600;'
            'padding:3px 10px;'
            'border-radius:99px;'
            'border:1px solid #fde68a;'
            'font-family: JetBrains Mono, monospace;'
            'letter-spacing:0.5px;'
            '">Python 3</span>',
            unsafe_allow_html=True,
        )

    with tool_col2:
        # Copy button — writes code to clipboard via JS
        if st.button("⎘ Copy", use_container_width=True, key="copy_btn"):
            st.session_state.copy_triggered = True

    with tool_col3:
        # Clear editor button
        if st.button("✕ Clear", use_container_width=True, key="clear_editor_btn"):
            st.session_state.generated_code = ""
            st.session_state.run_output = ""
            st.session_state.run_status = ""
            st.rerun()

    # ── ACE Code Editor ───────────────────────────────────────────
    # st_ace renders a full Monaco-like code editor in the browser.
    # It returns the current editor content on every Streamlit rerun.
    edited_code = st_ace(
        value=st.session_state.generated_code,
        language="python",
        theme=st.session_state.get("editor_theme", "tomorrow"),
        font_size=st.session_state.get("font_size", 14),
        tab_size=4,
        show_gutter=True,       # line numbers
        show_print_margin=False,
        wrap=False,
        auto_update=True,
        min_lines=22,
        max_lines=22,
        key="ace_editor",
    )

    # Sync editor content back to session state
    # so code_runner always has the latest version
    if edited_code is not None:
        st.session_state.generated_code = edited_code

    # ── Run button ────────────────────────────────────────────────
    st.markdown("<div style='margin-top: 8px;'>", unsafe_allow_html=True)

    # In components/editor.py — replace the run button + execute block

    run_clicked = st.button(
        "▶  Run Code",
        use_container_width=True,
        key="run_btn",
    )

    if run_clicked:
        code_to_run = st.session_state.generated_code.strip()

        if not code_to_run:
            st.warning("Nothing to run — editor is empty.")
        else:
            # Peek at imports so we can warn the user upfront
            from code_runner import extract_imports, is_package_installed, STDLIB_MODULES, resolve_pip_name

            imports = extract_imports(code_to_run)
            missing = [
                resolve_pip_name(m) for m in imports
                if m not in STDLIB_MODULES and not is_package_installed(m)
            ]

            if missing:
                # Show a friendly warning before the spinner appears
                pkg_list = ", ".join(missing)
                st.info(
                    f"📦 Missing packages detected: **{pkg_list}**\n\n"
                    f"Installing automatically — this may take 20–30 seconds on first run. Please wait...",
                    icon="⏳"
                )

            with st.spinner(
                    f"Installing {len(missing)} package(s) and running..." if missing else "Running..."
            ):
                result = run_python_code(code_to_run, timeout=60)
                output, status = format_output(result)
                st.session_state.run_output = output
                st.session_state.run_status = status

            if result.installed_packages:
                st.success(f"✅ Auto-installed: {', '.join(result.installed_packages)}")

            st.rerun()

    # ── Output display ────────────────────────────────────────────
    if st.session_state.run_output or st.session_state.run_status:
        render_output_box(
            st.session_state.run_output,
            st.session_state.run_status,
        )


def render_output_box(output: str, status: str):
    """
    Render the code execution output with color-coded status.

    Args:
        output: The text to display (stdout + stderr)
        status: "success" | "error" | "timeout"
    """

    # Style based on outcome
    if status == "success":
        border_color = "#86efac"   # green
        bg_color     = "#f0fdf4"
        header_color = "#16a34a"
        icon         = "✓"
        label        = "Output"
    elif status == "timeout":
        border_color = "#fdba74"   # orange
        bg_color     = "#fff7ed"
        header_color = "#ea580c"
        icon         = "⏱"
        label        = "Timed Out"
    else:
        border_color = "#fca5a5"   # red
        bg_color     = "#fef2f2"
        header_color = "#dc2626"
        icon         = "✗"
        label        = "Error"

    st.markdown(
        f"""
        <div style="
            background: {bg_color};
            border: 1px solid {border_color};
            border-radius: 8px;
            padding: 12px 16px;
            margin-top: 10px;
        ">
            <div style="
                font-size: 0.68rem;
                font-weight: 600;
                letter-spacing: 1px;
                text-transform: uppercase;
                color: {header_color};
                margin-bottom: 8px;
                font-family: 'Inter', sans-serif;
            ">{icon} &nbsp; {label}</div>
            <pre style="
                margin: 0;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.8rem;
                color: #1c1917;
                white-space: pre-wrap;
                word-break: break-word;
                max-height: 180px;
                overflow-y: auto;
                line-height: 1.6;
            ">{output}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )