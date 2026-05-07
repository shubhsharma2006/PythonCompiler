from __future__ import annotations

import ast

from compiler.frontend.cst import ParsedModule
from compiler.frontend.lexer import lex_source
from compiler.frontend.tokens import LexedSource
from compiler.utils.error_handler import ErrorHandler


def parse_tokens(lexed: LexedSource, errors: ErrorHandler) -> ParsedModule | None:
    try:
        syntax_tree = ast.parse(lexed.source.text, filename=lexed.source.filename, mode="exec")
    except SyntaxError as exc:
        errors.error("Syntax", exc.msg, exc.lineno, (exc.offset or 1) - 1)
        return None
    return ParsedModule(source=lexed.source, tokens=lexed.tokens, syntax_tree=syntax_tree)


def parse_source(source: str, filename: str, errors: ErrorHandler):
    lexed = lex_source(source, filename, errors)
    if lexed is None or errors.has_errors():
        return None
    return parse_tokens(lexed, errors)
