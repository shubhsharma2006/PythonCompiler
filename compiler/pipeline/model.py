from __future__ import annotations

from dataclasses import dataclass

from compiler.frontend import LexedSource, ParsedModule
from compiler.ir import IRModule
from compiler.semantic import SemanticModel
from compiler.utils.error_handler import ErrorHandler
from compiler.vm import BytecodeModule


@dataclass
class CompilationResult:
    success: bool
    errors: ErrorHandler
    lexed: LexedSource | None = None
    parsed: ParsedModule | None = None
    program: object | None = None
    semantic: SemanticModel | None = None
    bytecode: BytecodeModule | None = None
    ir: IRModule | None = None
    ssa: IRModule | None = None
    c_code: str | None = None
    output_path: str | None = None
    runtime_header_path: str | None = None
    runtime_source_path: str | None = None
    executable_path: str | None = None
    run_output: str | None = None
    run_error: str | None = None
