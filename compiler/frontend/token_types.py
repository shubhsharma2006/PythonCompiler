"""Comprehensive token type definitions for the owned lexer.

This module defines every token kind the lexer can emit, including
keywords, operators, delimiters, literals, and structural tokens
(INDENT, DEDENT, NEWLINE, EOF).
"""
from __future__ import annotations

from enum import Enum, auto


class TokenType(Enum):
    """All token categories emitted by the owned lexer."""

    # ── Structural ──────────────────────────────────────────────────
    NEWLINE = auto()       # logical newline (end of a statement)
    NL = auto()            # non-logical newline (blank / continuation)
    INDENT = auto()        # increase in indentation level
    DEDENT = auto()        # decrease in indentation level
    EOF = auto()           # end-of-file sentinel
    ENCODING = auto()      # CPython-compat: encoding declaration token
    COMMENT = auto()       # a # comment (preserved for tooling)

    # ── Literals ────────────────────────────────────────────────────
    INTEGER = auto()       # 42, 0x1A, 0o77, 0b1010
    FLOAT = auto()         # 3.14, 1e-3, .5
    STRING = auto()        # "hello", 'world', """triple""", r"raw"
    FSTRING_START = auto() # f" prefix (future use)
    FSTRING_END = auto()   # closing quote of f-string (future use)

    # ── Identifier / Name ──────────────────────────────────────────
    NAME = auto()          # any valid identifier that is not a keyword

    # ── Keywords ────────────────────────────────────────────────────
    KW_FALSE = auto()
    KW_NONE = auto()
    KW_TRUE = auto()
    KW_AND = auto()
    KW_AS = auto()
    KW_ASSERT = auto()
    KW_ASYNC = auto()
    KW_AWAIT = auto()
    KW_BREAK = auto()
    KW_CLASS = auto()
    KW_CONTINUE = auto()
    KW_DEF = auto()
    KW_DEL = auto()
    KW_ELIF = auto()
    KW_ELSE = auto()
    KW_EXCEPT = auto()
    KW_FINALLY = auto()
    KW_FOR = auto()
    KW_FROM = auto()
    KW_GLOBAL = auto()
    KW_IF = auto()
    KW_IMPORT = auto()
    KW_IN = auto()
    KW_IS = auto()
    KW_LAMBDA = auto()
    KW_NONLOCAL = auto()
    KW_NOT = auto()
    KW_OR = auto()
    KW_PASS = auto()
    KW_RAISE = auto()
    KW_RETURN = auto()
    KW_TRY = auto()
    KW_WHILE = auto()
    KW_WITH = auto()
    KW_YIELD = auto()

    # ── Operators ───────────────────────────────────────────────────
    PLUS = auto()          # +
    MINUS = auto()         # -
    STAR = auto()          # *
    SLASH = auto()         # /
    DOUBLESLASH = auto()   # //
    PERCENT = auto()       # %
    DOUBLESTAR = auto()    # **
    AT = auto()            # @

    PLUSEQUAL = auto()     # +=
    MINUSEQUAL = auto()    # -=
    STAREQUAL = auto()     # *=
    SLASHEQUAL = auto()    # /=
    DOUBLESLASHEQUAL = auto()  # //=
    PERCENTEQUAL = auto()  # %=
    DOUBLESTAREQUAL = auto()  # **=
    ATEQUAL = auto()       # @=

    EQEQUAL = auto()       # ==
    NOTEQUAL = auto()      # !=
    LESS = auto()          # <
    GREATER = auto()       # >
    LESSEQUAL = auto()     # <=
    GREATEREQUAL = auto()  # >=

    EQUAL = auto()         # =
    COLONEQUAL = auto()    # :=

    AMPERSAND = auto()     # &
    VBAR = auto()          # |
    CIRCUMFLEX = auto()    # ^
    TILDE = auto()         # ~
    LEFTSHIFT = auto()     # <<
    RIGHTSHIFT = auto()    # >>

    AMPERSANDEQUAL = auto()    # &=
    VBAREQUAL = auto()         # |=
    CIRCUMFLEXEQUAL = auto()   # ^=
    LEFTSHIFTEQUAL = auto()    # <<=
    RIGHTSHIFTEQUAL = auto()   # >>=

    # ── Delimiters ──────────────────────────────────────────────────
    LPAREN = auto()        # (
    RPAREN = auto()        # )
    LBRACKET = auto()      # [
    RBRACKET = auto()      # ]
    LBRACE = auto()        # {
    RBRACE = auto()        # }
    DOT = auto()           # .
    COMMA = auto()         # ,
    COLON = auto()         # :
    SEMI = auto()          # ;
    ARROW = auto()         # ->
    ELLIPSIS = auto()      # ...

    # ── Error / Unknown ─────────────────────────────────────────────
    ERROR = auto()         # unrecognized character sequence


# ── Keyword lookup table ────────────────────────────────────────────
KEYWORD_MAP: dict[str, TokenType] = {
    "False": TokenType.KW_FALSE,
    "None": TokenType.KW_NONE,
    "True": TokenType.KW_TRUE,
    "and": TokenType.KW_AND,
    "as": TokenType.KW_AS,
    "assert": TokenType.KW_ASSERT,
    "async": TokenType.KW_ASYNC,
    "await": TokenType.KW_AWAIT,
    "break": TokenType.KW_BREAK,
    "class": TokenType.KW_CLASS,
    "continue": TokenType.KW_CONTINUE,
    "def": TokenType.KW_DEF,
    "del": TokenType.KW_DEL,
    "elif": TokenType.KW_ELIF,
    "else": TokenType.KW_ELSE,
    "except": TokenType.KW_EXCEPT,
    "finally": TokenType.KW_FINALLY,
    "for": TokenType.KW_FOR,
    "from": TokenType.KW_FROM,
    "global": TokenType.KW_GLOBAL,
    "if": TokenType.KW_IF,
    "import": TokenType.KW_IMPORT,
    "in": TokenType.KW_IN,
    "is": TokenType.KW_IS,
    "lambda": TokenType.KW_LAMBDA,
    "nonlocal": TokenType.KW_NONLOCAL,
    "not": TokenType.KW_NOT,
    "or": TokenType.KW_OR,
    "pass": TokenType.KW_PASS,
    "raise": TokenType.KW_RAISE,
    "return": TokenType.KW_RETURN,
    "try": TokenType.KW_TRY,
    "while": TokenType.KW_WHILE,
    "with": TokenType.KW_WITH,
    "yield": TokenType.KW_YIELD,
}

# ── CPython `tokenize` compatibility name mapping ───────────────────
# The downstream pipeline stores token kinds as string names matching
# CPython's ``tokenize.tok_name`` dictionary.  This table translates
# our ``TokenType`` values to those canonical names so the rest of the
# compiler sees identical strings regardless of whether the CPython
# tokenizer or our owned lexer produced the token stream.
_TOKENTYPE_TO_CPYTHON_NAME: dict[TokenType, str] = {
    TokenType.NEWLINE: "NEWLINE",
    TokenType.NL: "NL",
    TokenType.INDENT: "INDENT",
    TokenType.DEDENT: "DEDENT",
    TokenType.EOF: "ENDMARKER",
    TokenType.ENCODING: "ENCODING",
    TokenType.COMMENT: "COMMENT",

    TokenType.INTEGER: "NUMBER",
    TokenType.FLOAT: "NUMBER",
    TokenType.STRING: "STRING",

    TokenType.NAME: "NAME",

    TokenType.ERROR: "ERRORTOKEN",
}

# All keywords map to "NAME" in CPython's tokenize output
for _kw in KEYWORD_MAP.values():
    _TOKENTYPE_TO_CPYTHON_NAME[_kw] = "NAME"

# All operators and delimiters map to "OP" in CPython's tokenize output
_OP_TYPES = {
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
    TokenType.DOUBLESLASH, TokenType.PERCENT, TokenType.DOUBLESTAR,
    TokenType.AT,
    TokenType.PLUSEQUAL, TokenType.MINUSEQUAL, TokenType.STAREQUAL,
    TokenType.SLASHEQUAL, TokenType.DOUBLESLASHEQUAL,
    TokenType.PERCENTEQUAL, TokenType.DOUBLESTAREQUAL, TokenType.ATEQUAL,
    TokenType.EQEQUAL, TokenType.NOTEQUAL, TokenType.LESS,
    TokenType.GREATER, TokenType.LESSEQUAL, TokenType.GREATEREQUAL,
    TokenType.EQUAL, TokenType.COLONEQUAL,
    TokenType.AMPERSAND, TokenType.VBAR, TokenType.CIRCUMFLEX,
    TokenType.TILDE, TokenType.LEFTSHIFT, TokenType.RIGHTSHIFT,
    TokenType.AMPERSANDEQUAL, TokenType.VBAREQUAL,
    TokenType.CIRCUMFLEXEQUAL, TokenType.LEFTSHIFTEQUAL,
    TokenType.RIGHTSHIFTEQUAL,
    TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACKET,
    TokenType.RBRACKET, TokenType.LBRACE, TokenType.RBRACE,
    TokenType.DOT, TokenType.COMMA, TokenType.COLON, TokenType.SEMI,
    TokenType.ARROW, TokenType.ELLIPSIS,
}
for _op in _OP_TYPES:
    _TOKENTYPE_TO_CPYTHON_NAME[_op] = "OP"

# Exact-kind names for operators (matches CPython's `tokenize.exact_type`)
_TOKENTYPE_TO_EXACT_NAME: dict[TokenType, str] = {
    TokenType.PLUS: "PLUS",
    TokenType.MINUS: "MINUS",
    TokenType.STAR: "STAR",
    TokenType.SLASH: "SLASH",
    TokenType.DOUBLESLASH: "DOUBLESLASH",
    TokenType.PERCENT: "PERCENT",
    TokenType.DOUBLESTAR: "DOUBLESTAR",
    TokenType.AT: "AT",
    TokenType.PLUSEQUAL: "PLUSEQUAL",
    TokenType.MINUSEQUAL: "MINEQUAL",
    TokenType.STAREQUAL: "STAREQUAL",
    TokenType.SLASHEQUAL: "SLASHEQUAL",
    TokenType.DOUBLESLASHEQUAL: "DOUBLESLASHEQUAL",
    TokenType.PERCENTEQUAL: "PERCENTEQUAL",
    TokenType.DOUBLESTAREQUAL: "DOUBLESTAREQUAL",
    TokenType.ATEQUAL: "ATEQUAL",
    TokenType.EQEQUAL: "EQEQUAL",
    TokenType.NOTEQUAL: "NOTEQUAL",
    TokenType.LESS: "LESS",
    TokenType.GREATER: "GREATER",
    TokenType.LESSEQUAL: "LESSEQUAL",
    TokenType.GREATEREQUAL: "GREATEREQUAL",
    TokenType.EQUAL: "EQUAL",
    TokenType.COLONEQUAL: "COLONEQUAL",
    TokenType.AMPERSAND: "AMPER",
    TokenType.VBAR: "VBAR",
    TokenType.CIRCUMFLEX: "CIRCUMFLEX",
    TokenType.TILDE: "TILDE",
    TokenType.LEFTSHIFT: "LEFTSHIFT",
    TokenType.RIGHTSHIFT: "RIGHTSHIFT",
    TokenType.AMPERSANDEQUAL: "AMPEREQUAL",
    TokenType.VBAREQUAL: "VBAREQUAL",
    TokenType.CIRCUMFLEXEQUAL: "CIRCUMFLEXEQUAL",
    TokenType.LEFTSHIFTEQUAL: "LEFTSHIFTEQUAL",
    TokenType.RIGHTSHIFTEQUAL: "RIGHTSHIFTEQUAL",
    TokenType.LPAREN: "LPAR",
    TokenType.RPAREN: "RPAR",
    TokenType.LBRACKET: "LSQB",
    TokenType.RBRACKET: "RSQB",
    TokenType.LBRACE: "LBRACE",
    TokenType.RBRACE: "RBRACE",
    TokenType.DOT: "DOT",
    TokenType.COMMA: "COMMA",
    TokenType.COLON: "COLON",
    TokenType.SEMI: "SEMI",
    TokenType.ARROW: "RARROW",
    TokenType.ELLIPSIS: "ELLIPSIS",
}


def cpython_kind(token_type: TokenType) -> str:
    """Return the CPython ``tokenize.tok_name`` string for *token_type*."""
    return _TOKENTYPE_TO_CPYTHON_NAME.get(token_type, "OP")


def cpython_exact_kind(token_type: TokenType) -> str:
    """Return the CPython exact-type string for *token_type*.

    For non-operator tokens this falls back to :func:`cpython_kind`.
    """
    return _TOKENTYPE_TO_EXACT_NAME.get(token_type, cpython_kind(token_type))
