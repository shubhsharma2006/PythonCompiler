"""
error_handler.py — Centralized error reporting with source context.
"""

import sys


class CompilerError:
    """A single compiler error/warning."""
    def __init__(self, kind, message, line=None, column=None):
        self.kind = kind        # 'Lexical', 'Syntax', 'Semantic', 'Type', 'Codegen'
        self.message = message
        self.line = line
        self.column = column

    def __str__(self):
        loc = ""
        if self.line is not None:
            loc = f" [Line {self.line}"
            if self.column is not None:
                loc += f", Col {self.column}"
            loc += "]"
        return f"{self.kind} Error{loc}: {self.message}"


class ErrorHandler:
    """Collects and reports compiler errors with source context."""

    def __init__(self, source=""):
        self.source_lines = source.splitlines() if source else []
        self.errors = []
        self.warnings = []

    def error(self, kind, message, line=None, column=None):
        """Record an error."""
        err = CompilerError(kind, message, line, column)
        self.errors.append(err)

    def warning(self, kind, message, line=None, column=None):
        """Record a warning."""
        w = CompilerError(kind, message, line, column)
        self.warnings.append(w)

    def has_errors(self):
        return len(self.errors) > 0

    def report(self, file=sys.stderr):
        """Print all errors and warnings with source context."""
        for w in self.warnings:
            print(f"\033[93mWarning: {w}\033[0m", file=file)
        for e in self.errors:
            print(f"\033[91mError: {e}\033[0m", file=file)
            if e.line and 1 <= e.line <= len(self.source_lines):
                src = self.source_lines[e.line - 1]
                print(f"  {e.line:4} | {src}", file=file)
                if e.column and e.column > 0:
                    pointer = " " * (e.column - 1) + "^"
                    print(f"       | {pointer}", file=file)

    def raise_if_errors(self, stage="Compilation"):
        """Report errors and exit if any exist."""
        if self.has_errors():
            self.report()
            print(f"\n\033[91m{stage} failed with {len(self.errors)} error(s).\033[0m",
                  file=sys.stderr)
            sys.exit(1)
