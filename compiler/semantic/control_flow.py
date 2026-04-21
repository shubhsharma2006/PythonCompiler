from __future__ import annotations

from compiler.core.ast import ClassDef, ForStmt, FunctionDef, IfStmt, Program, ReturnStmt, TryStmt, WhileStmt, BreakStmt, ContinueStmt, WithStmt
from compiler.core.types import ValueType
from compiler.semantic.model import SymbolTable
from compiler.utils.error_handler import ErrorHandler


class ControlFlowChecker:
    def __init__(self, errors: ErrorHandler):
        self.errors = errors

    def check(self, program: Program, table: SymbolTable) -> None:
        self._check_statements(program.body, table)

    def _check_statements(self, statements, table: SymbolTable) -> None:
        for statement in statements:
            if isinstance(statement, FunctionDef):
                function = table.functions.get(statement.name)
                return_type = function.return_type if function is not None else ValueType.UNKNOWN
                if return_type not in (ValueType.VOID, ValueType.UNKNOWN) and not self._must_return(statement.body):
                    self._error(statement, f"function {statement.name!r} may exit without returning {return_type.value}")
                self._check_statements(statement.body, table)
            elif isinstance(statement, ClassDef):
                for method in statement.methods:
                    self._check_statements([method], table)
            elif isinstance(statement, IfStmt):
                self._check_statements(statement.body, table)
                self._check_statements(statement.orelse, table)
            elif isinstance(statement, WhileStmt):
                self.in_loop = getattr(self, "in_loop", 0) + 1
                self._check_statements(statement.body, table)
                self.in_loop -= 1
                self._check_statements(statement.orelse, table)
            elif isinstance(statement, ForStmt):
                self.in_loop = getattr(self, "in_loop", 0) + 1
                self._check_statements(statement.body, table)
                self.in_loop -= 1
                self._check_statements(statement.orelse, table)
            elif isinstance(statement, TryStmt):
                self._check_statements(statement.body, table)
                for handler in statement.handlers:
                    self._check_statements(handler.body, table)
                self._check_statements(statement.finalbody, table)
            elif isinstance(statement, WithStmt):
                self._check_statements(statement.body, table)
            elif isinstance(statement, (BreakStmt, ContinueStmt)):
                if not getattr(self, "in_loop", 0):
                    name = "break" if isinstance(statement, BreakStmt) else "continue"
                    self._error(statement, f"{name} outside loop")

    def _must_return(self, statements) -> bool:
        for statement in statements:
            if isinstance(statement, ReturnStmt):
                return True
            if isinstance(statement, IfStmt):
                if self._must_return(statement.body) and self._must_return(statement.orelse):
                    return True
            if isinstance(statement, TryStmt):
                if self._must_return(statement.finalbody):
                    return True
                body_returns = self._must_return(statement.body)
                handlers_return = all(self._must_return(handler.body) for handler in statement.handlers)
                if body_returns and (not statement.handlers or handlers_return):
                    return True
            if isinstance(statement, WhileStmt):
                continue
        return False

    def _error(self, node, message: str) -> None:
        self.errors.error("Semantic", message, node.span.line, node.span.column, node.span.end_line, node.span.end_column)
