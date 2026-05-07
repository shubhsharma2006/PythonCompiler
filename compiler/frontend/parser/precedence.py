"""Operator precedence (binding power) tables for Pratt parsing.

Each operator is assigned a *left binding power* (lbp).  Higher values
bind tighter.  The Pratt loop in ``expr_parser.py`` uses these values to
decide whether to continue consuming infix operators.
"""
from __future__ import annotations

# ── Binding power levels (ascending tightness) ─────────────────────
BP_NONE        = 0
BP_LAMBDA      = 1
BP_TERNARY     = 2    # if ... else (right-associative)
BP_WALRUS      = 3    # :=
BP_OR          = 4    # or
BP_AND         = 5    # and
BP_NOT         = 6    # not (prefix)
BP_COMPARE     = 7    # == != < > <= >= in not-in is is-not
BP_BIT_OR      = 8    # |
BP_BIT_XOR     = 9    # ^
BP_BIT_AND     = 10   # &
BP_SHIFT       = 11   # << >>
BP_ADD         = 12   # + -
BP_MUL         = 13   # * / // % @
BP_UNARY       = 14   # - + ~ (prefix)
BP_POWER       = 15   # ** (right-associative)
BP_CALL        = 16   # f(...)
BP_INDEX       = 16   # x[...]
BP_ATTR        = 16   # x.y

# ── Infix operator → (left bp, right bp) ───────────────────────────
# Right-associative operators have right bp = left bp - 1
INFIX_BP: dict[str, tuple[int, int]] = {
    "or":   (BP_OR, BP_OR),
    "and":  (BP_AND, BP_AND),
    "|":    (BP_BIT_OR, BP_BIT_OR),
    "^":    (BP_BIT_XOR, BP_BIT_XOR),
    "&":    (BP_BIT_AND, BP_BIT_AND),
    "<<":   (BP_SHIFT, BP_SHIFT),
    ">>":   (BP_SHIFT, BP_SHIFT),
    "+":    (BP_ADD, BP_ADD),
    "-":    (BP_ADD, BP_ADD),
    "*":    (BP_MUL, BP_MUL),
    "/":    (BP_MUL, BP_MUL),
    "//":   (BP_MUL, BP_MUL),
    "%":    (BP_MUL, BP_MUL),
    "@":    (BP_MUL, BP_MUL),
    "**":   (BP_POWER, BP_POWER - 1),   # right-associative
}

# ── Comparison operators (all same precedence, chained) ─────────────
COMPARE_OPS: set[str] = {
    "==", "!=", "<", ">", "<=", ">=", "in", "not in", "is", "is not",
}

# ── Unary prefix operators ──────────────────────────────────────────
UNARY_OPS: dict[str, int] = {
    "-": BP_UNARY,
    "+": BP_UNARY,
    "~": BP_UNARY,
    "not": BP_NOT,
}

# ── Augmented assignment operators ──────────────────────────────────
AUGASSIGN_OPS: dict[str, str] = {
    "+=": "+", "-=": "-", "*=": "*", "/=": "/",
    "//=": "//", "%=": "%", "**=": "**", "@=": "@",
    "&=": "&", "|=": "|", "^=": "^",
    "<<=": "<<", ">>=": ">>",
}
