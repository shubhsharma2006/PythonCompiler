"""Token stream cursor for the owned parser.

Provides :class:`TokenCursor` — a positioned view over a flat token list
with lookahead, expectation helpers, and :class:`SourceSpan` generation.
"""
from __future__ import annotations

from compiler.core.ast import SourceSpan
from compiler.frontend.tokens import LexToken


class TokenCursor:
    """Navigates a flat ``list[LexToken]`` with single-token lookahead."""

    def __init__(self, tokens: list[LexToken]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ── Position ────────────────────────────────────────────────────

    @property
    def pos(self) -> int:
        return self._pos

    def at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    # ── Peek / Advance ──────────────────────────────────────────────

    def peek(self) -> LexToken:
        """Return current token without consuming it."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return self._tokens[-1]  # EOF sentinel

    def peek_kind(self) -> str:
        return self.peek().kind

    def peek_text(self) -> str:
        return self.peek().text

    def peek_next(self) -> LexToken:
        """Return the token after current (1-ahead lookahead)."""
        idx = self._pos + 1
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]

    def advance(self) -> LexToken:
        """Consume and return the current token."""
        tok = self.peek()
        if self._pos < len(self._tokens):
            self._pos += 1
        return tok

    # ── Matching ────────────────────────────────────────────────────

    def check(self, kind: str, text: str | None = None) -> bool:
        """Return True if current token matches *kind* (and optionally *text*)."""
        tok = self.peek()
        if tok.kind != kind:
            return False
        if text is not None and tok.text != text:
            return False
        return True

    def check_text(self, text: str) -> bool:
        """Return True if current token's text matches."""
        return self.peek().text == text

    def match(self, kind: str, text: str | None = None) -> LexToken | None:
        """Consume and return token if it matches, else return None."""
        if self.check(kind, text):
            return self.advance()
        return None

    def expect(self, kind: str, text: str | None = None, msg: str | None = None) -> LexToken:
        """Consume and return token, raising :class:`ParseError` on mismatch."""
        tok = self.match(kind, text)
        if tok is not None:
            return tok
        actual = self.peek()
        expected_desc = f"{kind}" if text is None else f"{kind} '{text}'"
        error_msg = msg or f"expected {expected_desc}, got {actual.kind} '{actual.text}'"
        raise ParseError(error_msg, actual.line, actual.column)

    # ── Skipping utilities ──────────────────────────────────────────

    def skip_newlines(self) -> None:
        """Skip NEWLINE and NL tokens."""
        while not self.at_end() and self.peek_kind() in ("NEWLINE", "NL"):
            self.advance()

    def skip_comments(self) -> None:
        """Skip COMMENT tokens."""
        while not self.at_end() and self.peek_kind() == "COMMENT":
            self.advance()

    def skip_noise(self) -> None:
        """Skip NEWLINE, NL, COMMENT, and ENCODING tokens."""
        while not self.at_end() and self.peek_kind() in ("NEWLINE", "NL", "COMMENT", "ENCODING"):
            self.advance()

    # ── Span helpers ────────────────────────────────────────────────

    def span_from(self, start_token: LexToken) -> SourceSpan:
        """Build a SourceSpan from *start_token* to the previously consumed token."""
        if self._pos > 0:
            end = self._tokens[self._pos - 1]
        else:
            end = start_token
        return SourceSpan(
            line=start_token.line,
            column=start_token.column,
            end_line=end.end_line,
            end_column=end.end_column,
        )

    def current_span(self) -> SourceSpan:
        tok = self.peek()
        return SourceSpan(
            line=tok.line, column=tok.column,
            end_line=tok.end_line, end_column=tok.end_column,
        )


class ParseError(Exception):
    """Raised by the parser on unrecoverable syntax errors."""

    def __init__(self, message: str, line: int = 1, column: int = 0) -> None:
        super().__init__(message)
        self.line = line
        self.column = column
