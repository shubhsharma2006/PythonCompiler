from __future__ import annotations

from compiler.core.ast import ClassDef, FunctionDef, Program
from compiler.core.types import FunctionType, ValueType
from compiler.semantic.model import SymbolTable
from compiler.utils.error_handler import ErrorHandler


class SymbolCollector:
    def __init__(self, errors: ErrorHandler):
        self.errors = errors

    def collect(self, program: Program) -> SymbolTable:
        table = SymbolTable()
        for statement in program.body:
            if isinstance(statement, FunctionDef):
                if statement.name in table.functions or statement.name in table.global_scope.values:
                    self._error(statement, f"duplicate definition for {statement.name!r}")
                    continue
                table.functions[statement.name] = FunctionType(
                    name=statement.name,
                    param_names=statement.params,
                    param_types=[ValueType.UNKNOWN for _ in statement.params],
                    defaults_count=len(statement.defaults),
                    kwonly_names=statement.kwonly_params,
                    kwonly_types={name: ValueType.UNKNOWN for name in statement.kwonly_params},
                    kwonly_defaults=set(statement.kwonly_defaults),
                    vararg_name=statement.vararg,
                    kwarg_name=statement.kwarg,
                    node=statement,
                )
            elif isinstance(statement, ClassDef):
                if statement.name in table.functions or statement.name in table.global_scope.values:
                    self._error(statement, f"duplicate definition for {statement.name!r}")
                    continue
                table.global_scope.define(statement.name, ValueType.UNKNOWN)
        return table

    def _error(self, node, message: str) -> None:
        self.errors.error("Semantic", message, node.span.line, node.span.column, node.span.end_line, node.span.end_column)
