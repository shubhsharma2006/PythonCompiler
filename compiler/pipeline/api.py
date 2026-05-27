from __future__ import annotations

from .analyze import _analyze_source
from .compile_native import compile_source
from .execute_vm import execute_source
from .model import CompilationResult


def check_source(
    source: str,
    *,
    filename: str = "<stdin>",
    frontend: str = "owned",
) -> CompilationResult:
    return _analyze_source(source, filename=filename, frontend=frontend)


__all__ = ["CompilationResult", "check_source", "compile_source", "execute_source"]
