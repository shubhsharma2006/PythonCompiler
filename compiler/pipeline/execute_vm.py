from __future__ import annotations

import os

from compiler.vm import BytecodeInterpreter, BytecodeLowerer, VMError

from .analyze import _analyze_source
from .imports import _load_bytecode_module, _module_name_for_filename
from .model import CompilationResult


def execute_source(
    source: str,
    *,
    filename: str = "<stdin>",
    frontend: str = "cpython",
) -> CompilationResult:
    result = _analyze_source(source, filename=filename, frontend=frontend)
    if not result.success or result.program is None:
        return result

    bytecode = BytecodeLowerer().lower(
        result.program,
        module_name=_module_name_for_filename(filename),
        filename=os.path.abspath(filename) if filename != "<stdin>" else filename,
    )
    result.bytecode = bytecode

    try:
        result.run_output = BytecodeInterpreter(module_loader=_load_bytecode_module).run(bytecode)
    except VMError as exc:
        result.errors.error("Runtime", str(exc))
        result.run_error = str(exc)
        result.success = False
    return result
