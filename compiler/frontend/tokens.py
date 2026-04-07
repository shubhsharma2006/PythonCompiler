"""
tokens.py — Token types and Token class.
"""

from enum import Enum, auto


class TokenType(Enum):
    # Literals
    INTEGER    = auto()
    FLOAT      = auto()
    STRING     = auto()
    IDENTIFIER = auto()

    # Keywords
    IF      = auto()
    ELIF    = auto()
    ELSE    = auto()
    WHILE   = auto()
    FOR     = auto()
    IN      = auto()
    RANGE   = auto()
    DEF     = auto()
    RETURN  = auto()
    PRINT   = auto()
    TRUE    = auto()
    FALSE   = auto()
    AND     = auto()
    OR      = auto()
    NOT     = auto()

    # Arithmetic
    PLUS    = auto()
    MINUS   = auto()
    STAR    = auto()
    SLASH   = auto()
    PERCENT = auto()

    # Augmented assignment
    PLUS_EQ  = auto()
    MINUS_EQ = auto()
    STAR_EQ  = auto()
    SLASH_EQ = auto()

    # Comparison
    EQ      = auto()   # ==
    NEQ     = auto()   # !=
    LT      = auto()   # <
    GT      = auto()   # >
    LTE     = auto()   # <=
    GTE     = auto()   # >=

    # Assignment
    ASSIGN  = auto()   # =

    # Delimiters
    LPAREN  = auto()
    RPAREN  = auto()
    LBRACE  = auto()
    RBRACE  = auto()
    COMMA   = auto()
    COLON   = auto()

    # Structure
    NEWLINE = auto()
    EOF     = auto()


# Map keyword strings to token types
KEYWORD_MAP = {
    'if':     TokenType.IF,
    'elif':   TokenType.ELIF,
    'else':   TokenType.ELSE,
    'while':  TokenType.WHILE,
    'for':    TokenType.FOR,
    'in':     TokenType.IN,
    'range':  TokenType.RANGE,
    'def':    TokenType.DEF,
    'return': TokenType.RETURN,
    'print':  TokenType.PRINT,
    'True':   TokenType.TRUE,
    'False':  TokenType.FALSE,
    'and':    TokenType.AND,
    'or':     TokenType.OR,
    'not':    TokenType.NOT,
}


class Token:
    """A lexical token with type, value, and source location."""

    __slots__ = ('type', 'value', 'line', 'column')

    def __init__(self, type: TokenType, value, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"
