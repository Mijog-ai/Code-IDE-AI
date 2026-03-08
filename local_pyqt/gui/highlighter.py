# gui/highlighter.py
# Syntax highlighters for QPlainTextEdit.
# Supports: Python, PHP, C# / ASP.NET, Kotlin, Flutter / Dart.

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
# C# / ASP.NET syntax highlighter
# ─────────────────────────────────────────────────────────────────

_CSHARP_RULES: list[tuple[str, QTextCharFormat]] = [

    # Verbatim strings  @"..."
    (r'@"[^"]*"',                           _fmt("#16a34a")),
    # Interpolated strings  $"..."
    (r'\$"[^"\\]*(\\.[^"\\]*)*"',           _fmt("#16a34a")),
    # Regular strings / chars
    (r'"[^"\\]*(\\.[^"\\]*)*"',             _fmt("#16a34a")),
    (r"'[^'\\]*(\\.[^'\\]*)*'",             _fmt("#16a34a")),

    # Attributes  [HttpGet]  [Route("api/v1")]
    (r"\[[\w\s.,\(\)\"'/=\\]+\]",          _fmt("#d97706", italic=True)),

    # Keywords
    (
        r"\b(abstract|as|async|await|base|bool|break|byte|case|catch|char|"
        r"checked|class|const|continue|decimal|default|delegate|do|double|"
        r"dynamic|else|enum|event|explicit|extern|false|finally|fixed|float|"
        r"for|foreach|get|goto|if|implicit|in|init|int|interface|internal|"
        r"is|lock|long|namespace|new|not|null|object|operator|out|override|"
        r"params|partial|private|protected|public|readonly|record|ref|"
        r"required|return|sbyte|sealed|set|short|sizeof|stackalloc|static|"
        r"string|struct|switch|this|throw|true|try|typeof|uint|ulong|"
        r"unchecked|unsafe|ushort|using|var|virtual|void|volatile|when|"
        r"where|while|with|yield)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Common BCL / ASP.NET types
    (
        r"\b(Console|Math|String|StringBuilder|List|Dictionary|HashSet|Queue|"
        r"Stack|Array|Tuple|Task|Thread|IEnumerable|IList|ICollection|"
        r"IDictionary|IQueryable|Exception|DateTime|TimeSpan|Guid|Regex|"
        r"HttpClient|JsonSerializer|File|Directory|Path|Stream|Encoding|"
        r"CancellationToken|ILogger|IServiceProvider|IActionResult|"
        r"ControllerBase|WebApplication|WebApplicationBuilder|IConfiguration|"
        r"IHostBuilder|IWebHostEnvironment|ClaimsPrincipal|HttpContext)\b",
        _fmt("#0369a1"),
    ),

    # Numbers
    (r"\b0[xX][0-9a-fA-F]+[uUlL]*\b",     _fmt("#b45309")),
    (r"\b\d+\.\d+[fFdDmM]?\b",             _fmt("#b45309")),
    (r"\b\d+[uUlLfFdDmM]?\b",              _fmt("#b45309")),

    # Method name after return type  void Foo(  Task<T> Bar(
    (r"\b([A-Z]\w*)\s+(\w+)\s*\(",         _fmt("#0891b2", bold=True)),
    (r"\bclass\s+(\w+)",                    _fmt("#7c3aed", bold=True)),
    (r"\brecord\s+(\w+)",                   _fmt("#7c3aed", bold=True)),
    (r"\binterface\s+(\w+)",                _fmt("#0891b2", bold=True)),

    # XML doc comments  ///
    (r"///[^\n]*",                          _fmt("#16a34a", italic=True)),
    # Block comments  /* ... */
    (r"/\*[\s\S]*?\*/",                     _fmt("#a8a29e", italic=True)),
    # Line comments  //
    (r"//[^\n]*",                           _fmt("#a8a29e", italic=True)),
]

_CSHARP_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(pat), fmt) for pat, fmt in _CSHARP_RULES
]


class CSharpHighlighter(QSyntaxHighlighter):
    """Applies C# / ASP.NET token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _CSHARP_COMPILED_RULES:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ─────────────────────────────────────────────────────────────────
# Kotlin syntax highlighter
# ─────────────────────────────────────────────────────────────────

_KOTLIN_RULES: list[tuple[str, QTextCharFormat]] = [

    # Triple-quoted strings  """..."""
    (r'"""[\s\S]*?"""',                     _fmt("#16a34a", italic=True)),
    # Regular strings / chars
    (r'"[^"\\]*(\\.[^"\\]*)*"',             _fmt("#16a34a")),
    (r"'[^'\\]*(\\.[^'\\]*)*'",             _fmt("#16a34a")),

    # Annotations  @Override  @Composable  @SuppressWarnings
    (r"@[\w.]+",                            _fmt("#d97706", bold=True)),

    # Keywords
    (
        r"\b(abstract|actual|annotation|as|break|by|catch|class|companion|"
        r"const|constructor|continue|crossinline|data|do|dynamic|else|enum|"
        r"expect|external|false|final|finally|for|fun|get|if|import|in|"
        r"infix|init|inline|inner|interface|internal|is|it|lateinit|noinline|"
        r"null|object|open|operator|out|override|package|private|protected|"
        r"public|reified|return|sealed|set|suspend|tailrec|this|throw|true|"
        r"try|typealias|val|var|vararg|when|where|while)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Built-in types / stdlib
    (
        r"\b(Int|Long|Short|Byte|Double|Float|Boolean|Char|String|Any|Unit|"
        r"Nothing|Array|List|MutableList|Map|MutableMap|Set|MutableSet|"
        r"Sequence|Iterable|Collection|Pair|Triple|Result|Flow|StateFlow|"
        r"SharedFlow|CoroutineScope|Deferred|Job|Channel|Mutex)\b",
        _fmt("#0369a1"),
    ),

    # Numbers
    (r"\b0[xX][0-9a-fA-F]+[uUlL]*\b",     _fmt("#b45309")),
    (r"\b\d+\.\d+[fF]?\b",                 _fmt("#b45309")),
    (r"\b\d+[uUlL]?\b",                    _fmt("#b45309")),

    # fun / class declarations
    (r"\bfun\s+(\w+)",                      _fmt("#0891b2", bold=True)),
    (r"\bclass\s+(\w+)",                    _fmt("#7c3aed", bold=True)),
    (r"\bobject\s+(\w+)",                   _fmt("#7c3aed", bold=True)),
    (r"\binterface\s+(\w+)",                _fmt("#0891b2", bold=True)),

    # Block comments  /* ... */
    (r"/\*[\s\S]*?\*/",                     _fmt("#a8a29e", italic=True)),
    # Line comments  //
    (r"//[^\n]*",                           _fmt("#a8a29e", italic=True)),
]

_KOTLIN_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(pat), fmt) for pat, fmt in _KOTLIN_RULES
]


class KotlinHighlighter(QSyntaxHighlighter):
    """Applies Kotlin token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _KOTLIN_COMPILED_RULES:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ─────────────────────────────────────────────────────────────────
# Flutter / Dart syntax highlighter
# ─────────────────────────────────────────────────────────────────

_DART_RULES: list[tuple[str, QTextCharFormat]] = [

    # Triple-quoted strings  """..."""  '''...'''
    (r'"""[\s\S]*?"""',                     _fmt("#16a34a", italic=True)),
    (r"'''[\s\S]*?'''",                     _fmt("#16a34a", italic=True)),
    # Regular strings
    (r'"[^"\\]*(\\.[^"\\]*)*"',             _fmt("#16a34a")),
    (r"'[^'\\]*(\\.[^'\\]*)*'",             _fmt("#16a34a")),

    # Annotations  @override  @required  @immutable
    (r"@[\w.]+",                            _fmt("#d97706", bold=True)),

    # Keywords
    (
        r"\b(abstract|as|assert|async|await|break|case|catch|class|const|"
        r"continue|covariant|default|deferred|do|dynamic|else|enum|export|"
        r"extends|extension|external|factory|false|final|finally|for|"
        r"Function|get|hide|if|implements|import|in|interface|is|late|"
        r"library|mixin|new|null|on|operator|part|required|rethrow|return|"
        r"sealed|set|show|static|super|switch|sync|this|throw|true|try|"
        r"typedef|var|void|when|while|with|yield)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Built-in types + Flutter widget names
    (
        r"\b(int|double|num|String|bool|List|Map|Set|Iterable|Future|Stream|"
        r"Object|dynamic|Never|Null|Symbol|Type|Duration|DateTime|Uri|"
        r"RegExp|Comparable|Iterator|Widget|StatelessWidget|StatefulWidget|"
        r"State|BuildContext|Key|GlobalKey|ValueKey|MaterialApp|CupertinoApp|"
        r"Scaffold|AppBar|Text|Column|Row|Container|Padding|Center|Expanded|"
        r"SizedBox|Stack|Align|Positioned|ListView|GridView|SingleChildScrollView|"
        r"TextStyle|Colors|EdgeInsets|BorderRadius|BoxDecoration|Icon|"
        r"ElevatedButton|TextButton|IconButton|FloatingActionButton|"
        r"TextField|Form|GestureDetector|Navigator|Route|Provider|"
        r"ChangeNotifier|ValueNotifier|StreamBuilder|FutureBuilder)\b",
        _fmt("#0369a1"),
    ),

    # Numbers
    (r"\b0[xX][0-9a-fA-F]+\b",             _fmt("#b45309")),
    (r"\b\d+\.\d+\b",                       _fmt("#b45309")),
    (r"\b\d+\b",                            _fmt("#b45309")),

    # class / function declarations
    (r"\bclass\s+(\w+)",                    _fmt("#7c3aed", bold=True)),
    (r"\bvoid\s+(\w+)",                     _fmt("#0891b2", bold=True)),
    (r"\b(\w+)\s+(\w+)\s*\(",               _fmt("#0891b2")),

    # Doc comments  ///
    (r"///[^\n]*",                          _fmt("#16a34a", italic=True)),
    # Block comments  /* ... */
    (r"/\*[\s\S]*?\*/",                     _fmt("#a8a29e", italic=True)),
    # Line comments  //
    (r"//[^\n]*",                           _fmt("#a8a29e", italic=True)),
]

_DART_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = [
    (QRegularExpression(pat), fmt) for pat, fmt in _DART_RULES
]


class DartHighlighter(QSyntaxHighlighter):
    """Applies Flutter / Dart token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _DART_COMPILED_RULES:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ─────────────────────────────────────────────────────────────────
# Visual FoxPro syntax highlighter
# ─────────────────────────────────────────────────────────────────

_FOXPRO_RULES: list[tuple[str, QTextCharFormat]] = [

    # Strings: "...", '...', [...]   (VFP supports all three delimiters)
    (r'"[^"]*"',                                _fmt("#16a34a")),
    (r"'[^']*'",                                _fmt("#16a34a")),
    (r"\[[^\]]*\]",                             _fmt("#16a34a")),

    # Boolean / null literals  .T.  .F.  .NULL.  .Y.  .N.
    (r"\.[TFYN]\.|\.NULL\.",                    _fmt("#7c3aed", bold=True)),

    # Keywords (case-insensitive flag set on each pattern via QRegularExpression)
    (
        r"\b(ACCEPT|ACTIVATE|ADD|ALTER|APPEND|AVERAGE|BROWSE|BUILD|CALCULATE|"
        r"CALL|CANCEL|CASE|CATCH|CHANGE|CLEAR|CLOSE|COMPILE|CONTINUE|COPY|"
        r"COUNT|CREATE|DECLARE|DEFAULT|DEFINE|DELETE|DIMENSION|DIR|DO|ELSE|"
        r"ELSEIF|END|ENDCASE|ENDDEFINE|ENDDO|ENDFUNC|ENDIF|ENDPROC|ENDTRY|"
        r"ENDWITH|ERASE|EXIT|EXPORT|FINALLY|FOR|FUNCTION|GO|GOTO|IF|IMPORT|"
        r"INDEX|INPUT|INSERT|JOIN|KEYBOARD|LABEL|LIST|LOCAL|LOCATE|LOOP|"
        r"MODIFY|MOVE|NEXT|OTHERWISE|PACK|PARAMETERS|PRIVATE|PROCEDURE|"
        r"PUBLIC|QUIT|READ|RECALL|REINDEX|RELEASE|RENAME|REPLACE|REPORT|"
        r"RESTORE|RETURN|REVERT|RUN|SAVE|SCAN|SELECT|SET|SKIP|SORT|STORE|"
        r"SUM|TABLE|THIS|THISFORM|THISFORMSET|TRY|TYPE|UPDATE|USE|WAIT|"
        r"WHERE|WITH|WHILE|ZAP)\b",
        _fmt("#7c3aed", bold=True),
    ),

    # Built-in functions (most commonly used)
    (
        r"\b(ABS|ACOPY|ADEL|ADIR|AELEM|AFIELDS|AFONT|AGETCLASS|AGETFILEVERSION|"
        r"AINS|ALEN|ALIAS|ALLTRIM|ASC|ASORT|ASUBSCRIPT|AT|ATC|ATCLINE|ATLINE|"
        r"BETWEEN|BITAND|BITOR|BITXOR|CDOW|CHR|CMONTH|COL|CREATEOBJECT|"
        r"CTOD|CURDIR|DATE|DATETIME|DAY|DBF|DELETED|DIFFERENCE|DOW|DTOC|"
        r"DTOS|EMPTY|EOF|EVALUATE|FIELD|FILE|FLOCK|FOUND|FULLPATH|GETENV|"
        r"HOUR|IIF|INDBC|INLIST|INT|ISALPHA|ISBLANK|ISDIGIT|ISLOWER|ISNULL|"
        r"ISUPPER|LEFT|LEN|LIKE|LTRIM|MAX|MDY|MESSAGEBOX|MIN|MINUTE|MOD|"
        r"MONTH|NORMALIZE|OCCURS|PADL|PADR|PADC|PAYMENT|PROGRAM|PROPER|"
        r"PUTFILE|RAND|RECCOUNT|RECNO|REPLICATE|RIGHT|RLOCK|ROUND|ROW|RTRIM|"
        r"SECONDS|SEEK|SELECT|SET|SIGN|SOUNDEX|SPACE|SQRT|STR|STRTRAN|STUFF|"
        r"SUBSTR|SYS|TIME|TRANSFORM|TRIM|TTOC|TTOD|TXNLEVEL|TYPE|UPPER|"
        r"USED|VAL|VARTYPE|WEEK|YEAR)\b",
        _fmt("#0369a1"),
    ),

    # Numbers
    (r"\b\d+\.\d+\b",                           _fmt("#b45309")),
    (r"\b\d+\b",                                _fmt("#b45309")),

    # DEFINE CLASS / PROCEDURE / FUNCTION declarations
    (r"\bDEFINE\s+CLASS\s+(\w+)",               _fmt("#0891b2", bold=True)),
    (r"\bPROCEDURE\s+(\w+)",                    _fmt("#0891b2", bold=True)),
    (r"\bFUNCTION\s+(\w+)",                     _fmt("#0891b2", bold=True)),

    # Inline comment  &&  (must come before full-line *)
    (r"&&[^\n]*",                               _fmt("#a8a29e", italic=True)),
    # Full-line comment  *  (only at start of line)
    (r"^\*[^\n]*",                              _fmt("#a8a29e", italic=True)),
    # C-style line comment  //  (VFP8+)
    (r"//[^\n]*",                               _fmt("#a8a29e", italic=True)),
]

# VFP is case-insensitive — enable CaseInsensitiveOption on keyword/function rules
_FOXPRO_COMPILED_RULES: list[tuple[QRegularExpression, QTextCharFormat]] = []
for _pat, _fmt_val in _FOXPRO_RULES:
    _rx = QRegularExpression(_pat)
    # Apply case-insensitive flag to keyword/built-in patterns (large \b(...)\b groups)
    if r"\b(" in _pat:
        _rx.setPatternOptions(
            QRegularExpression.PatternOption.CaseInsensitiveOption
        )
    _FOXPRO_COMPILED_RULES.append((_rx, _fmt_val))


class FoxProHighlighter(QSyntaxHighlighter):
    """Applies Visual FoxPro token colouring to a QTextDocument."""

    def __init__(self, document) -> None:
        super().__init__(document)

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in _FOXPRO_COMPILED_RULES:
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
    if lang == "csharp":
        return CSharpHighlighter(document)
    if lang == "kotlin":
        return KotlinHighlighter(document)
    if lang == "dart":
        return DartHighlighter(document)
    if lang == "foxpro":
        return FoxProHighlighter(document)
    return PythonHighlighter(document)
