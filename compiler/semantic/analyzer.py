from __future__ import annotations

from compiler.core.ast import Program
from compiler.semantic.control_flow import ControlFlowChecker
from compiler.semantic.model import SemanticModel
from compiler.semantic.resolver import NameResolver
from compiler.semantic.symbols import SymbolCollector
from compiler.semantic.type_checker import TypeChecker
from compiler.utils.error_handler import ErrorHandler


class SemanticAnalyzer:
    def __init__(self, errors: ErrorHandler):
        self.errors = errors

    def analyze(self, program: Program) -> SemanticModel:
        symbols = SymbolCollector(self.errors).collect(program)
        if self.errors.has_errors():
            return SemanticModel(
                globals=dict(symbols.global_scope.values),
                functions=symbols.functions,
                expr_types={},
                container_elem_types={},
                container_var_elem_types={},
            )

        NameResolver(self.errors).resolve(program, symbols)
        checker = TypeChecker(self.errors)
        expr_types = checker.check(program, symbols)
        ControlFlowChecker(self.errors).check(program, symbols)

        return SemanticModel(
            globals=dict(symbols.global_scope.values),
            functions=symbols.functions,
            expr_types=expr_types,
            container_elem_types=checker.container_elem_types,
            container_var_elem_types=checker.container_var_elem_types,
        )
