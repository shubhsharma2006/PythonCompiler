"""
logger.py — Structured compiler logging.
"""

import sys

# ANSI colours
_COLORS = {
    'DEBUG': '\033[2m',    # dim
    'INFO':  '\033[96m',   # cyan
    'STAGE': '\033[1m\033[96m',  # bold cyan
    'OK':    '\033[92m',   # green
    'WARN':  '\033[93m',   # yellow
    'ERROR': '\033[91m',   # red
}
_RESET = '\033[0m'


class CompilerLogger:
    """Structured logger for compiler stages."""

    def __init__(self, verbose=False, quiet=False):
        self.verbose = verbose
        self.quiet = quiet

    def stage(self, title):
        if self.quiet:
            return
        bar = '─' * 60
        print(f'\n{_COLORS["STAGE"]}┌{bar}┐')
        print(f'│  {title:<58}│')
        print(f'└{bar}┘{_RESET}')

    def info(self, msg):
        if not self.quiet:
            print(f'  {_COLORS["INFO"]}ℹ{_RESET} {msg}')

    def ok(self, msg):
        if not self.quiet:
            print(f'  {_COLORS["OK"]}✔{_RESET} {msg}')

    def warn(self, msg):
        if not self.quiet:
            print(f'  {_COLORS["WARN"]}⚠{_RESET} {msg}')

    def error(self, msg):
        print(f'  {_COLORS["ERROR"]}✘{_RESET} {msg}', file=sys.stderr)

    def debug(self, msg):
        if self.verbose:
            print(f'  {_COLORS["DEBUG"]}[DBG]{_RESET} {msg}')

    def emit(self, text):
        """Print raw text (for token/AST/IR dumps)."""
        if not self.quiet:
            print(text)
