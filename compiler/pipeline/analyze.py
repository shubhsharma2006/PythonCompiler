from __future__ import annotations

from dataclasses import fields, is_dataclass

from compiler.frontend import lex_source, lower_cst, parse_to_program, parse_tokens
from compiler.optimizer import ConstantFolder
from compiler.semantic import SemanticAnalyzer
from compiler.utils.error_handler import ErrorHandler

from .model import CompilationResult


def _normalize_program_for_frontend_compare(node):
    if is_dataclass(node):
        kwargs = {}
        for field in fields(node):
            if not field.init:
                continue
            value = getattr(node, field.name)
            if field.name == "span":
                kwargs[field.name] = type(value)()
            elif isinstance(value, list):
                kwargs[field.name] = [_normalize_program_for_frontend_compare(item) for item in value]
            elif isinstance(value, dict):
                kwargs[field.name] = {
                    key: _normalize_program_for_frontend_compare(item)
                    for key, item in value.items()
                }
            else:
                kwargs[field.name] = _normalize_program_for_frontend_compare(value)
        return type(node)(**kwargs)
    return node


def _analyze_source(
    source: str,
    *,
    filename: str = "<stdin>",
    frontend: str = "cpython",
) -> CompilationResult:
    errors = ErrorHandler(source=source, filename=filename)
    lexed = lex_source(source, filename, errors)
    if lexed is None or errors.has_errors():
        return CompilationResult(success=False, errors=errors, lexed=lexed)

    parsed = None
    if frontend == "owned":
        owned_errors = ErrorHandler(source=source, filename=filename)
        owned_program = parse_to_program(lexed, owned_errors)

        cpython_errors = ErrorHandler(source=source, filename=filename)
        parsed = parse_tokens(lexed, cpython_errors)
        cpython_program = None
        if parsed is not None and not cpython_errors.has_errors():
            cpython_program = lower_cst(parsed, cpython_errors)

        owned_ok = owned_program is not None and not owned_errors.has_errors()
        cpython_ok = cpython_program is not None and not cpython_errors.has_errors()

        if owned_ok and cpython_ok:
            if _normalize_program_for_frontend_compare(owned_program) == _normalize_program_for_frontend_compare(cpython_program):
                program = owned_program
            else:
                program = cpython_program
        elif cpython_ok:
            program = cpython_program
        elif owned_ok:
            program = owned_program
        else:
            chosen_errors = cpython_errors if parsed is None or cpython_errors.has_errors() else owned_errors
            return CompilationResult(
                success=False,
                errors=chosen_errors,
                lexed=lexed,
                parsed=parsed,
                program=cpython_program if cpython_program is not None else owned_program,
            )
    else:
        parsed = parse_tokens(lexed, errors)
        if parsed is None or errors.has_errors():
            return CompilationResult(success=False, errors=errors, lexed=lexed, parsed=parsed)

        program = lower_cst(parsed, errors)
        if program is None or errors.has_errors():
            return CompilationResult(success=False, errors=errors, lexed=lexed, parsed=parsed, program=program)

    semantic = SemanticAnalyzer(errors).analyze(program)
    if errors.has_errors():
        return CompilationResult(success=False, errors=errors, lexed=lexed, parsed=parsed, program=program, semantic=semantic)

    program = ConstantFolder().optimize(program)
    semantic = SemanticAnalyzer(errors).analyze(program)
    if errors.has_errors():
        return CompilationResult(success=False, errors=errors, lexed=lexed, parsed=parsed, program=program, semantic=semantic)

    return CompilationResult(
        success=True,
        errors=errors,
        lexed=lexed,
        parsed=parsed,
        program=program,
        semantic=semantic,
    )
