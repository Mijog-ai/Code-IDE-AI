# gui/highlighter.py
# Python syntax highlighter for QPlainTextEdit

from __future__ import annotations

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(
    color: str,
    bold: bool = False,
    italic: bool = False,
) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


# Token rules: (regex_pattern, format)
_RULES: list[tuple[str, QTextCharFormat]] = [

    # Triple-quoted strings (must come before single-char strings)
    (r'"""[\s\S]*?"""',                     _fmt("#16a34a", italic=True)),
    (r"'''[\s\S]*?'''",                     _fmt("#16a34a", italic=True)),

    # Single / double quoted strings
    (r'"[^"\\]*(\\.[^"\\]*)*"',             _fmt("#16a34a")),
    (r"'[^'\\]*(\\.[^'\\]*)*'",             _fmt("#16a34a")),

    # Decorators
    (r"@[\w.]+",                            _fmt("#d97706", bold=True)),

    # Keywords
    (
        r"\b(False|None|True|and|as|assert|async|await|break|class|continue|"
        r"def|del|elif|else|except|finally|for|from|global|if|import|in|is|"
        r"lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Built-ins
    (
        r"\b(abs|all|any|bin|bool|breakpoint|bytes|callable|chr|classmethod|"
        r"compile|complex|delattr|dict|dir|divmod|enumerate|eval|exec|filter|"
        r"float|format|frozenset|getattr|globals|hasattr|hash|help|hex|id|"
        r"input|int|isinstance|issubclass|iter|len|list|locals|map|max|"
        r"memoryview|min|next|object|oct|open|ord|pow|print|property|range|"
        r"repr|reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|"
        r"super|tuple|type|vars|zip)\b",
        _fmt("#0369a1"),
    ),

    # self / cls
    (r"\b(self|cls)\b",                     _fmt("#d97706")),

    # Numbers (int, float, hex, binary, octal)
    (r"\b0[xX][0-9a-fA-F]+\b",             _fmt("#b45309")),
    (r"\b0[bB][01]+\b",                     _fmt("#b45309")),
    (r"\b0[oO][0-7]+\b",                    _fmt("#b45309")),
    (r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b",    _fmt("#b45309")),

    # Function / class names after def / class
    (r"\bdef\s+(\w+)",                      _fmt("#0891b2", bold=True)),
    (r"\bclass\s+(\w+)",                    _fmt("#7c3aed", bold=True)),

    # Comments (must come last so they override everything)
    (r"#[^\n]*",                            _fmt("#a8a29e", italic=True)),
]

# Compile rules once at module load time
_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(pat), fmt) for pat, fmt in _RULES
]


class PythonHighlighter(QSyntaxHighlighter):
    """Applies Python token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _COMPILED_RULES:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
