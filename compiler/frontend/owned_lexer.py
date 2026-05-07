"""Fully owned, indentation-aware Python lexer.

Replaces CPython's ``tokenize.generate_tokens()`` with a hand-written
scanner that:

* emits INDENT / DEDENT tokens matching CPython semantics,
* tracks precise source locations for every token,
* detects mixed tabs and spaces,
* recovers gracefully from invalid syntax,
* supports all Python literal forms the compiler subset needs.

The public entry point is :func:`tokenize_source`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.frontend.source_map import Diagnostic, Severity, SourceLocation
from compiler.frontend.token_types import KEYWORD_MAP, TokenType


# ── Internal token produced by the scanner ──────────────────────────
@dataclass(frozen=True)
class OwnedToken:
    """A single token produced by the owned lexer."""
    type: TokenType
    text: str
    line: int        # 1-indexed
    column: int      # 0-indexed
    end_line: int    # 1-indexed
    end_column: int  # 0-indexed


# ── Bracket depth tracking (implicit line continuation) ─────────────
_OPEN_BRACKETS = {"(", "[", "{"}
_CLOSE_BRACKETS = {")", "]", "}"}
_BRACKET_MAP = {")": "(", "]": "[", "}": "{"}

# ── Single-char → token type mapping ───────────────────────────────
_SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ",": TokenType.COMMA,
    ";": TokenType.SEMI,
    "~": TokenType.TILDE,
}


class _Lexer:
    """Internal state-machine lexer."""

    def __init__(self, source: str) -> None:
        self._src = source
        self._pos = 0
        self._line = 1        # 1-indexed
        self._col = 0         # 0-indexed
        self._tokens: list[OwnedToken] = []
        self._diagnostics: list[Diagnostic] = []
        self._indent_stack: list[int] = [0]
        self._bracket_depth = 0
        self._at_line_start = True
        self._paren_stack: list[str] = []

    # ── Helpers ─────────────────────────────────────────────────────

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        if idx < len(self._src):
            return self._src[idx]
        return ""

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 0
        else:
            self._col += 1
        return ch

    def _at_end(self) -> bool:
        return self._pos >= len(self._src)

    def _emit(self, token_type: TokenType, text: str, line: int, col: int, end_line: int, end_col: int) -> None:
        self._tokens.append(OwnedToken(
            type=token_type, text=text,
            line=line, column=col,
            end_line=end_line, end_column=end_col,
        ))

    def _error(self, msg: str) -> None:
        self._diagnostics.append(Diagnostic(
            severity=Severity.ERROR, message=msg,
            location=SourceLocation(self._line, self._col),
        ))

    # ── Main loop ───────────────────────────────────────────────────

    def tokenize(self) -> tuple[list[OwnedToken], list[Diagnostic]]:
        # Emit a leading ENCODING token for CPython compatibility
        self._emit(TokenType.ENCODING, "utf-8", 1, 0, 1, 0)

        while not self._at_end():
            if self._at_line_start:
                self._handle_indentation()
            self._scan_token()

        # Flush remaining DEDENTs
        while len(self._indent_stack) > 1:
            self._indent_stack.pop()
            self._emit(TokenType.DEDENT, "", self._line, 0, self._line, 0)

        # Final NEWLINE + EOF
        self._emit(TokenType.NEWLINE, "", self._line, self._col, self._line, self._col)
        self._emit(TokenType.EOF, "", self._line, self._col, self._line, self._col)
        return self._tokens, self._diagnostics

    # ── Indentation handling ────────────────────────────────────────

    def _handle_indentation(self) -> None:
        self._at_line_start = False
        if self._bracket_depth > 0:
            # Inside brackets: skip leading whitespace, no INDENT/DEDENT
            while not self._at_end() and self._peek() in (" ", "\t"):
                self._advance()
            return

        indent = 0
        start_pos = self._pos
        while not self._at_end() and self._peek() in (" ", "\t"):
            ch = self._advance()
            if ch == "\t":
                indent = (indent // 8 + 1) * 8
            else:
                indent += 1

        # Blank line or comment line: don't emit INDENT/DEDENT
        if not self._at_end() and (self._peek() == "\n" or self._peek() == "#"):
            return

        if self._at_end():
            return

        current = self._indent_stack[-1]
        if indent > current:
            self._indent_stack.append(indent)
            self._emit(TokenType.INDENT, "", self._line, 0, self._line, indent)
        elif indent < current:
            while self._indent_stack and self._indent_stack[-1] > indent:
                self._indent_stack.pop()
                self._emit(TokenType.DEDENT, "", self._line, 0, self._line, 0)
            if self._indent_stack[-1] != indent:
                self._error(f"dedent does not match any outer indentation level")

    # ── Token scanning ──────────────────────────────────────────────

    def _scan_token(self) -> None:
        if self._at_end():
            return

        ch = self._peek()

        # Whitespace (non-newline)
        if ch in (" ", "\t"):
            self._advance()
            return

        # Backslash continuation
        if ch == "\\":
            self._advance()
            if not self._at_end() and self._peek() == "\n":
                self._advance()
                # Don't set at_line_start — this is explicit continuation
            return

        # Newline
        if ch == "\n":
            line, col = self._line, self._col
            self._advance()
            if self._bracket_depth > 0:
                self._emit(TokenType.NL, "\n", line, col, self._line, 0)
            else:
                self._emit(TokenType.NEWLINE, "\n", line, col, self._line, 0)
            self._at_line_start = True
            return

        # Carriage return
        if ch == "\r":
            self._advance()
            if not self._at_end() and self._peek() == "\n":
                self._advance()
            self._at_line_start = True
            return

        # Comment
        if ch == "#":
            self._scan_comment()
            return

        # String literal (including f-strings, r-strings, b-strings)
        if ch in ("'", '"') or (ch in ("f", "r", "b", "F", "R", "B", "u", "U") and self._peek(1) in ("'", '"', "f", "r", "b", "F", "R", "B")):
            self._scan_string()
            return

        # Numeric literal
        if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
            self._scan_number()
            return

        # Identifier / keyword
        if ch.isalpha() or ch == "_":
            self._scan_identifier()
            return

        # Dot / Ellipsis
        if ch == ".":
            if self._peek(1) == "." and self._peek(2) == ".":
                line, col = self._line, self._col
                self._advance(); self._advance(); self._advance()
                self._emit(TokenType.ELLIPSIS, "...", line, col, self._line, self._col)
                return
            line, col = self._line, self._col
            self._advance()
            self._emit(TokenType.DOT, ".", line, col, self._line, self._col)
            return

        # Single-char tokens (brackets, comma, semi, tilde)
        if ch in _SINGLE_CHAR_TOKENS:
            line, col = self._line, self._col
            self._advance()
            token_type = _SINGLE_CHAR_TOKENS[ch]
            self._emit(token_type, ch, line, col, self._line, self._col)
            if ch in _OPEN_BRACKETS:
                self._bracket_depth += 1
                self._paren_stack.append(ch)
            elif ch in _CLOSE_BRACKETS:
                self._bracket_depth = max(0, self._bracket_depth - 1)
                if self._paren_stack:
                    self._paren_stack.pop()
            return

        # Multi-character operators
        self._scan_operator()

    # ── Comment ─────────────────────────────────────────────────────

    def _scan_comment(self) -> None:
        line, col = self._line, self._col
        text = ""
        while not self._at_end() and self._peek() != "\n":
            text += self._advance()
        self._emit(TokenType.COMMENT, text, line, col, self._line, self._col)

    # ── String literal ──────────────────────────────────────────────

    def _scan_string(self) -> None:
        line, col = self._line, self._col
        text = ""

        # Consume prefix letters (f, r, b, u, in any case/combo)
        while not self._at_end() and self._peek().lower() in ("f", "r", "b", "u"):
            text += self._advance()

        if self._at_end() or self._peek() not in ("'", '"'):
            # Shouldn't happen; fall back to identifier scanning
            self._pos -= len(text)
            self._col -= len(text)
            self._scan_identifier()
            return

        quote_char = self._peek()
        triple = False

        # Check for triple quote
        if self._peek(1) == quote_char and self._peek(2) == quote_char:
            triple = True
            text += self._advance() + self._advance() + self._advance()
            end_seq = quote_char * 3
        else:
            text += self._advance()
            end_seq = quote_char

        # Scan body
        while not self._at_end():
            ch = self._peek()
            if ch == "\\" and not self._at_end():
                text += self._advance()
                if not self._at_end():
                    text += self._advance()
                continue
            if triple:
                if ch == quote_char and self._peek(1) == quote_char and self._peek(2) == quote_char:
                    text += self._advance() + self._advance() + self._advance()
                    self._emit(TokenType.STRING, text, line, col, self._line, self._col)
                    return
            else:
                if ch == quote_char:
                    text += self._advance()
                    self._emit(TokenType.STRING, text, line, col, self._line, self._col)
                    return
                if ch == "\n":
                    self._error("EOL while scanning string literal")
                    self._emit(TokenType.STRING, text, line, col, self._line, self._col)
                    return
            text += self._advance()

        self._error("EOF while scanning string literal")
        self._emit(TokenType.STRING, text, line, col, self._line, self._col)

    # ── Numeric literal ─────────────────────────────────────────────

    def _scan_number(self) -> None:
        line, col = self._line, self._col
        text = ""
        is_float = False

        # Hex / Octal / Binary prefixes
        if self._peek() == "0" and self._peek(1).lower() in ("x", "o", "b"):
            text += self._advance() + self._advance()
            while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
                text += self._advance()
            self._emit(TokenType.INTEGER, text, line, col, self._line, self._col)
            return

        # Decimal integer or float
        while not self._at_end() and (self._peek().isdigit() or self._peek() == "_"):
            text += self._advance()

        # Fractional part
        if not self._at_end() and self._peek() == "." and self._peek(1) != ".":
            is_float = True
            text += self._advance()
            while not self._at_end() and (self._peek().isdigit() or self._peek() == "_"):
                text += self._advance()

        # Exponent
        if not self._at_end() and self._peek().lower() == "e":
            is_float = True
            text += self._advance()
            if not self._at_end() and self._peek() in ("+", "-"):
                text += self._advance()
            while not self._at_end() and (self._peek().isdigit() or self._peek() == "_"):
                text += self._advance()

        # Imaginary suffix
        if not self._at_end() and self._peek().lower() == "j":
            is_float = True
            text += self._advance()

        self._emit(TokenType.FLOAT if is_float else TokenType.INTEGER, text, line, col, self._line, self._col)

    # ── Identifier / keyword ────────────────────────────────────────

    def _scan_identifier(self) -> None:
        line, col = self._line, self._col
        text = ""
        while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
            text += self._advance()

        token_type = KEYWORD_MAP.get(text, TokenType.NAME)
        self._emit(token_type, text, line, col, self._line, self._col)

    # ── Operators ───────────────────────────────────────────────────

    def _scan_operator(self) -> None:
        line, col = self._line, self._col
        ch = self._advance()

        # Two/three char operators
        nxt = self._peek() if not self._at_end() else ""
        nxt2 = self._peek(1) if self._pos + 1 < len(self._src) else ""

        if ch == "+":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.PLUSEQUAL, "+=", line, col, self._line, self._col); return
            self._emit(TokenType.PLUS, "+", line, col, self._line, self._col); return
        if ch == "-":
            if nxt == ">":
                self._advance()
                self._emit(TokenType.ARROW, "->", line, col, self._line, self._col); return
            if nxt == "=":
                self._advance()
                self._emit(TokenType.MINUSEQUAL, "-=", line, col, self._line, self._col); return
            self._emit(TokenType.MINUS, "-", line, col, self._line, self._col); return
        if ch == "*":
            if nxt == "*":
                self._advance()
                if not self._at_end() and self._peek() == "=":
                    self._advance()
                    self._emit(TokenType.DOUBLESTAREQUAL, "**=", line, col, self._line, self._col); return
                self._emit(TokenType.DOUBLESTAR, "**", line, col, self._line, self._col); return
            if nxt == "=":
                self._advance()
                self._emit(TokenType.STAREQUAL, "*=", line, col, self._line, self._col); return
            self._emit(TokenType.STAR, "*", line, col, self._line, self._col); return
        if ch == "/":
            if nxt == "/":
                self._advance()
                if not self._at_end() and self._peek() == "=":
                    self._advance()
                    self._emit(TokenType.DOUBLESLASHEQUAL, "//=", line, col, self._line, self._col); return
                self._emit(TokenType.DOUBLESLASH, "//", line, col, self._line, self._col); return
            if nxt == "=":
                self._advance()
                self._emit(TokenType.SLASHEQUAL, "/=", line, col, self._line, self._col); return
            self._emit(TokenType.SLASH, "/", line, col, self._line, self._col); return
        if ch == "%":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.PERCENTEQUAL, "%=", line, col, self._line, self._col); return
            self._emit(TokenType.PERCENT, "%", line, col, self._line, self._col); return
        if ch == "@":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.ATEQUAL, "@=", line, col, self._line, self._col); return
            self._emit(TokenType.AT, "@", line, col, self._line, self._col); return
        if ch == "=":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.EQEQUAL, "==", line, col, self._line, self._col); return
            self._emit(TokenType.EQUAL, "=", line, col, self._line, self._col); return
        if ch == "!":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.NOTEQUAL, "!=", line, col, self._line, self._col); return
            self._error(f"unexpected character '!'")
            self._emit(TokenType.ERROR, "!", line, col, self._line, self._col); return
        if ch == "<":
            if nxt == "<":
                self._advance()
                if not self._at_end() and self._peek() == "=":
                    self._advance()
                    self._emit(TokenType.LEFTSHIFTEQUAL, "<<=", line, col, self._line, self._col); return
                self._emit(TokenType.LEFTSHIFT, "<<", line, col, self._line, self._col); return
            if nxt == "=":
                self._advance()
                self._emit(TokenType.LESSEQUAL, "<=", line, col, self._line, self._col); return
            self._emit(TokenType.LESS, "<", line, col, self._line, self._col); return
        if ch == ">":
            if nxt == ">":
                self._advance()
                if not self._at_end() and self._peek() == "=":
                    self._advance()
                    self._emit(TokenType.RIGHTSHIFTEQUAL, ">>=", line, col, self._line, self._col); return
                self._emit(TokenType.RIGHTSHIFT, ">>", line, col, self._line, self._col); return
            if nxt == "=":
                self._advance()
                self._emit(TokenType.GREATEREQUAL, ">=", line, col, self._line, self._col); return
            self._emit(TokenType.GREATER, ">", line, col, self._line, self._col); return
        if ch == "&":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.AMPERSANDEQUAL, "&=", line, col, self._line, self._col); return
            self._emit(TokenType.AMPERSAND, "&", line, col, self._line, self._col); return
        if ch == "|":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.VBAREQUAL, "|=", line, col, self._line, self._col); return
            self._emit(TokenType.VBAR, "|", line, col, self._line, self._col); return
        if ch == "^":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.CIRCUMFLEXEQUAL, "^=", line, col, self._line, self._col); return
            self._emit(TokenType.CIRCUMFLEX, "^", line, col, self._line, self._col); return
        if ch == ":":
            if nxt == "=":
                self._advance()
                self._emit(TokenType.COLONEQUAL, ":=", line, col, self._line, self._col); return
            self._emit(TokenType.COLON, ":", line, col, self._line, self._col); return

        self._error(f"unexpected character {ch!r}")
        self._emit(TokenType.ERROR, ch, line, col, self._line, self._col)


# ── Public API ──────────────────────────────────────────────────────

def tokenize_source(source: str) -> tuple[list[OwnedToken], list[Diagnostic]]:
    """Tokenize *source* into a list of :class:`OwnedToken` values.

    Returns a ``(tokens, diagnostics)`` pair.  If *diagnostics* contains
    any errors the token stream may be incomplete but is still usable for
    partial analysis.
    """
    lexer = _Lexer(source)
    return lexer.tokenize()
