from __future__ import annotations

from compiler.frontend.owned_lexer import tokenize_source
from compiler.frontend.source import SourceFile
from compiler.frontend.source_map import Severity
from compiler.frontend.token_types import cpython_kind, cpython_exact_kind, TokenType
from compiler.frontend.tokens import LexToken, LexedSource
from compiler.utils.error_handler import ErrorHandler


def lex_source(source: str, filename: str, errors: ErrorHandler) -> LexedSource | None:
    source_file = SourceFile(filename=filename, text=source)
    owned_tokens, diagnostics = tokenize_source(source)

    # Forward any lexer diagnostics to the project error handler
    for diagnostic in diagnostics:
        if diagnostic.severity == Severity.ERROR:
            errors.error(
                "Syntax",
                diagnostic.message,
                diagnostic.location.line,
                diagnostic.location.column,
            )

    if errors.has_errors():
        return None

    # Convert owned tokens into the downstream LexToken format
    tokens: list[LexToken] = []
    for tok in owned_tokens:
        kind = cpython_kind(tok.type)
        exact = cpython_exact_kind(tok.type)
        tokens.append(
            LexToken(
                kind=kind,
                text=tok.text,
                line=tok.line,
                column=tok.column,
                end_line=tok.end_line,
                end_column=tok.end_column,
                exact_kind=exact,
            )
        )

    return LexedSource(source=source_file, tokens=tokens)
