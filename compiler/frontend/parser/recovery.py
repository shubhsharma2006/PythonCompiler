"""Error recovery utilities for the owned parser.

Provides :func:`synchronize` which skips tokens to a known safe
restart point (e.g. NEWLINE, DEDENT, or statement-starting keyword)
so the parser can report multiple errors per file.
"""
from __future__ import annotations

from compiler.frontend.parser.token_cursor import TokenCursor

# Keywords that typically start a new statement
_SYNC_KEYWORDS = {
    "def", "class", "if", "elif", "else", "for", "while", "return",
    "try", "except", "finally", "with", "import", "from", "raise",
    "break", "continue", "pass", "del", "global", "nonlocal", "assert",
}


def synchronize(cursor: TokenCursor) -> None:
    """Advance *cursor* past tokens until a likely statement boundary.

    This allows the parser to recover from a syntax error and continue
    parsing subsequent statements, collecting multiple diagnostics in a
    single pass.
    """
    while not cursor.at_end():
        kind = cursor.peek_kind()

        # Reached a statement boundary — stop
        if kind in ("NEWLINE", "DEDENT", "ENDMARKER"):
            if kind == "NEWLINE":
                cursor.advance()
            return

        # Reached a keyword that starts a statement — stop (don't consume)
        if kind == "NAME" and cursor.peek_text() in _SYNC_KEYWORDS:
            return

        cursor.advance()
