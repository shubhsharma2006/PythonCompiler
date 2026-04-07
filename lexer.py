"""
lexer.py — Lexical Analyser using PLY (Production)
====================================================
Supports: keywords (if/elif/else/while/def/return/print),
identifiers, numbers, strings, arithmetic/comparison/augmented
assignment operators, braces. Includes a TokenFilter.
"""

import ply.lex as lex

# ── Token list ──────────────────────────────────────────────────

tokens = (
    'NUMBER', 'STRING', 'ID',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MODULO',
    'PLUSEQ', 'MINUSEQ', 'TIMESEQ', 'DIVEQ',
    'EQUALS', 'EQEQ', 'NEQ', 'LT', 'GT', 'LTE', 'GTE',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'COLON', 'COMMA', 'NEWLINE',
    'IF', 'ELIF', 'ELSE', 'WHILE', 'DEF', 'RETURN', 'PRINT',
)

KEYWORDS = {
    'if': 'IF', 'elif': 'ELIF', 'else': 'ELSE', 'while': 'WHILE',
    'def': 'DEF', 'return': 'RETURN', 'print': 'PRINT',
}

# ── Multi-char operators (PLY sorts by regex length, longest first) ──

t_PLUSEQ  = r'\+='
t_MINUSEQ = r'-='
t_TIMESEQ = r'\*='
t_DIVEQ   = r'/='
t_EQEQ    = r'=='
t_NEQ     = r'!='
t_LTE     = r'<='
t_GTE     = r'>='

# ── Single-char operators ──────────────────────────────────────

t_LT     = r'<'
t_GT     = r'>'
t_PLUS   = r'\+'
t_MINUS  = r'-'
t_TIMES  = r'\*'
t_DIVIDE = r'/'
t_MODULO = r'%'
t_EQUALS = r'='
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_COLON  = r':'
t_COMMA  = r','

# ── Complex tokens ─────────────────────────────────────────────

def t_NUMBER(t):
    r'\d+(\.\d+)?'
    t.value = float(t.value) if '.' in t.value else int(t.value)
    return t

def t_STRING(t):
    r'"[^"]*"|\'[^\']*\''
    t.value = t.value[1:-1]
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = KEYWORDS.get(t.value, 'ID')
    return t

def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += t.value.count('\n')
    return t

def t_COMMENT(t):
    r'\#[^\n]*'
    pass

t_ignore = ' \t'

def t_error(t):
    print(f"  [Lexer] Line {t.lineno}: Unexpected character {t.value[0]!r}")
    t.lexer.skip(1)

raw_lexer = lex.lex()


# ── Token Filter ───────────────────────────────────────────────

class FilteredLexer:
    """Wraps PLY lexer, filters problematic NEWLINE tokens."""

    def __init__(self, raw):
        self.raw = raw
        self._tokens = []
        self._pos = 0

    @property
    def lineno(self):
        return self.raw.lineno

    @lineno.setter
    def lineno(self, val):
        self.raw.lineno = val

    def input(self, data):
        self.raw.input(data)
        self.raw.lineno = 1
        all_toks = []
        while True:
            t = self.raw.token()
            if t is None:
                break
            all_toks.append(t)
        self._tokens = self._filter(all_toks)
        self._pos = 0

    def token(self):
        if self._pos < len(self._tokens):
            t = self._tokens[self._pos]
            self._pos += 1
            return t
        return None

    @staticmethod
    def _filter(tokens):
        result = []
        for i, tok in enumerate(tokens):
            if tok.type == 'NEWLINE':
                if result and result[-1].type == 'LBRACE':
                    continue
                j = i + 1
                while j < len(tokens) and tokens[j].type == 'NEWLINE':
                    j += 1
                if j < len(tokens) and tokens[j].type in ('RBRACE', 'ELSE', 'ELIF'):
                    continue
                if result and result[-1].type == 'NEWLINE':
                    continue
            result.append(tok)
        while result and result[-1].type == 'NEWLINE':
            result.pop()
        return result


lexer = FilteredLexer(raw_lexer)


def tokenize(source: str):
    """Tokenize source and return list of tokens."""
    lexer.input(source)
    toks = []
    while True:
        tok = lexer.token()
        if tok is None:
            break
        toks.append(tok)
    return toks
