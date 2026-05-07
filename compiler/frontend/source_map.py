"""Source location and diagnostic utilities for the owned lexer.

Provides :class:`SourceLocation` for precise position tracking and
:class:`Diagnostic` for structured error reporting during lexing.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Severity(Enum):
    """Diagnostic severity levels."""
    ERROR = auto()
    WARNING = auto()
    NOTE = auto()


@dataclass(frozen=True)
class SourceLocation:
    """A position inside a source file (1-indexed line, 0-indexed column)."""
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class SourceRange:
    """A contiguous range within a source file."""
    start: SourceLocation
    end: SourceLocation

    def __str__(self) -> str:
        if self.start.line == self.end.line:
            return f"line {self.start.line}, col {self.start.column}-{self.end.column}"
        return f"{self.start} .. {self.end}"


@dataclass(frozen=True)
class Diagnostic:
    """A structured diagnostic message produced during lexing."""
    severity: Severity
    message: str
    location: SourceLocation

    def __str__(self) -> str:
        label = self.severity.name.lower()
        return f"{label}: {self.message} at {self.location}"
