"""
config.py — Compiler-wide configuration and constants.
"""

VERSION = "2.0.0"
COMPILER_NAME = "MiniPyC"

# Language keywords
KEYWORDS = {
    'if', 'elif', 'else', 'while', 'for', 'in', 'range',
    'def', 'return', 'print',
    'True', 'False', 'and', 'or', 'not',
}

# Maximum errors before aborting
MAX_ERRORS = 20

# Optimization levels
OPT_NONE = 0
OPT_BASIC = 1  # constant folding
OPT_FULL = 2   # + dead code elimination + copy propagation
