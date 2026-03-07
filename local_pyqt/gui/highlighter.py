# gui/highlighter.py
# Syntax highlighters for QPlainTextEdit.
# Currently supports Python and PHP.

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


# ─────────────────────────────────────────────────────────────────
# PHP syntax highlighter
# ─────────────────────────────────────────────────────────────────

_PHP_RULES: list[tuple[str, QTextCharFormat]] = [

    # Double-quoted strings (with variable interpolation support)
    (r'"[^"\\]*(\\.[^"\\]*)*"',             _fmt("#16a34a")),
    # Single-quoted strings (no interpolation)
    (r"'[^'\\]*(\\.[^'\\]*)*'",             _fmt("#16a34a")),
    # Heredoc / Nowdoc openers  <<<EOT  <<<'EOT'
    (r"<<<\s*'?\w+'?",                       _fmt("#16a34a", italic=True)),

    # PHP opening / closing tags
    (r"<\?php|<\?=|\?>",                    _fmt("#7c3aed", bold=True)),

    # Keywords
    (
        r"\b(abstract|and|array|as|break|callable|case|catch|class|clone|"
        r"const|continue|declare|default|do|echo|else|elseif|empty|enddeclare|"
        r"endfor|endforeach|endif|endswitch|endwhile|enum|extends|final|"
        r"finally|fn|for|foreach|function|global|goto|if|implements|"
        r"include|include_once|instanceof|insteadof|interface|isset|list|"
        r"match|namespace|new|null|or|print|private|protected|public|"
        r"readonly|require|require_once|return|static|switch|throw|trait|"
        r"try|unset|use|var|while|xor|yield|true|false|null)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Type declarations (PHP 8+)
    (
        r"\b(string|int|float|bool|void|array|object|callable|iterable|"
        r"never|mixed|self|parent|static)\b",
        _fmt("#0369a1"),
    ),

    # Variables  $name  $this  $variableName
    (r"\$[a-zA-Z_][a-zA-Z0-9_]*",          _fmt("#b45309", bold=True)),

    # Built-in functions (most common)
    (
        r"\b(var_dump|print_r|var_export|count|strlen|str_contains|"
        r"str_starts_with|str_ends_with|substr|strpos|str_replace|trim|"
        r"ltrim|rtrim|explode|implode|array_map|array_filter|array_keys|"
        r"array_values|array_merge|array_push|array_pop|in_array|sort|"
        r"rsort|usort|range|sprintf|printf|number_format|round|floor|"
        r"ceil|abs|min|max|rand|intval|floatval|strval|boolval|is_null|"
        r"is_int|is_float|is_string|is_array|is_bool|is_numeric|"
        r"json_encode|json_decode|file_get_contents|file_put_contents|"
        r"header|http_response_code|htmlspecialchars|htmlentities|"
        r"date|time|strtotime|mktime|microtime|sleep|usleep)\b",
        _fmt("#0369a1"),
    ),

    # Numbers (int, float, hex, binary, octal)
    (r"\b0[xX][0-9a-fA-F]+\b",             _fmt("#b45309")),
    (r"\b0[bB][01]+\b",                     _fmt("#b45309")),
    (r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b",    _fmt("#b45309")),

    # Function / class names after function / class
    (r"\bfunction\s+(\w+)",                 _fmt("#0891b2", bold=True)),
    (r"\bclass\s+(\w+)",                    _fmt("#7c3aed", bold=True)),

    # Attributes  #[Route(...)]  #[Override]
    (r"#\[[\w\\,\s\"'()]*\]",              _fmt("#d97706", italic=True)),

    # Line comments (// and #) — must come before block comments
    (r"//[^\n]*",                           _fmt("#a8a29e", italic=True)),
    (r"#(?!\[)[^\n]*",                      _fmt("#a8a29e", italic=True)),

    # Block comments  /* ... */
    (r"/\*[\s\S]*?\*/",                     _fmt("#a8a29e", italic=True)),
]

_PHP_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(pat), fmt) for pat, fmt in _PHP_RULES
]


class PhpHighlighter(QSyntaxHighlighter):
    """Applies PHP token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _PHP_COMPILED_RULES:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ─────────────────────────────────────────────────────────────────
# Factory helper
# ─────────────────────────────────────────────────────────────────

def make_highlighter(language: str, document) -> QSyntaxHighlighter:
    """
    Return the correct syntax highlighter for *language*, attached to
    *document*.  Falls back to PythonHighlighter for unknown languages.
    """
    lang = language.lower()
    if lang == "php":
        return PhpHighlighter(document)
    return PythonHighlighter(document)
