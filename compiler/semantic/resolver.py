from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    ClassDef,
    CompareExpr,
    ConstantExpr,
    DeleteStmt,
    DictExpr,
    ExceptHandler,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    IfStmt,
    IfExpr,
    IndexExpr,
    ImportStmt,
    LambdaExpr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    SliceExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WhileStmt,
)
from compiler.core.types import FunctionType, ValueType
from compiler.semantic.model import Scope, SymbolTable
from compiler.utils.error_handler import ErrorHandler


class NameResolver:
    BUILTIN_NAMES = {
        "len", "range", "str", "repr", "ascii", "int", "float", "bool", "list", "dict", "set", "tuple",
        "enumerate", "zip", "map", "filter", "reversed", "sorted", "iter", "next", "abs", "round", "min",
        "max", "sum", "pow", "divmod", "hash", "hex", "oct", "bin", "chr", "ord", "format", "print",
        "input", "open", "any", "all", "isinstance", "issubclass", "hasattr", "getattr", "setattr",
        "delattr", "callable", "id", "type", "object", "super", "property", "staticmethod", "classmethod",
        "vars", "dir", "Exception", "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
        "RuntimeError", "StopIteration", "NameError", "ImportError", "OSError", "IOError",
        "FileNotFoundError", "ZeroDivisionError", "OverflowError", "MemoryError", "RecursionError",
        "NotImplementedError", "AssertionError", "SystemExit", "KeyboardInterrupt", "GeneratorExit",
        "ArithmeticError", "LookupError",
    }

    def __init__(self, errors: ErrorHandler):
        self.errors = errors
        self.table: SymbolTable | None = None
        self.current_function: FunctionType | None = None
        self.local_functions: list[dict[str, FunctionType]] = []

    def resolve(self, program: Program, table: SymbolTable) -> None:
        self.table = table
        for function in table.functions.values():
            function.state = "unvisited"
            function.reachable = False

        for statement in program.body:
            if isinstance(statement, FunctionDef):
                for default in statement.defaults:
                    self._resolve_expr(default, table.global_scope)
                continue
            self._resolve_statement(statement, table.global_scope)

        for function in table.functions.values():
            if function.state != "done":
                self._resolve_function(function)

    @staticmethod
    def _is_builtin_function(name: str) -> bool:
        return name in NameResolver.BUILTIN_NAMES

    def _resolve_function(self, function: FunctionType) -> None:
        if function.state == "done":
            return
        if function.state == "resolving":
            return
        function.state = "resolving"
        scope = Scope(self.table.global_scope)
        self.local_functions.append({})
        for param in function.param_names:
            scope.define(param, ValueType.UNKNOWN)

        previous = self.current_function
        self.current_function = function
        for statement in function.node.body:
            self._resolve_statement(statement, scope)
        self.current_function = previous
        self.local_functions.pop()
        function.state = "done"

    def _resolve_statement(self, statement, scope: Scope) -> None:
        if isinstance(statement, AssignStmt):
            if scope is self.table.global_scope and statement.name in self.table.functions:
                self._error(statement, f"cannot assign to function name {statement.name!r}")
                return
            self._resolve_expr(statement.value, scope)
            self._define_name(scope, statement.name, ValueType.UNKNOWN)
            return

        if isinstance(statement, UnpackAssignStmt):
            self._resolve_expr(statement.value, scope)
            for target in statement.targets:
                self._define_name(scope, target, ValueType.UNKNOWN)
            return

        if isinstance(statement, AttributeAssignStmt):
            self._resolve_expr(statement.object, scope)
            self._resolve_expr(statement.value, scope)
            return

        if isinstance(statement, PassStmt):
            return

        if isinstance(statement, GlobalStmt):
            for name in statement.names:
                scope.declare_global(name)
            return

        if isinstance(statement, NonlocalStmt):
            if self.current_function is None:
                self._error(statement, "nonlocal is only valid inside a function")
                return
            for name in statement.names:
                if scope.lookup_enclosing(name) is None:
                    self._error(statement, f"no binding for nonlocal {name!r} found")
                    continue
                scope.declare_nonlocal(name)
            return

        if isinstance(statement, DeleteStmt):
            for target in statement.targets:
                self._resolve_delete_target(target, scope)
            return

        if isinstance(statement, ImportStmt):
            self._define_name(scope, statement.alias or statement.module, ValueType.UNKNOWN)
            return

        if isinstance(statement, FromImportStmt):
            self._define_name(scope, statement.alias or statement.name, ValueType.UNKNOWN)
            return

        if isinstance(statement, PrintStmt):
            for value in statement.values:
                self._resolve_expr(value, scope)
            if statement.sep is not None:
                self._resolve_expr(statement.sep, scope)
            if statement.end is not None:
                self._resolve_expr(statement.end, scope)
            return

        if isinstance(statement, ExprStmt):
            if not isinstance(statement.expr, (CallExpr, MethodCallExpr)):
                self._error(statement, "only function and method calls may be used as standalone expressions")
            self._resolve_expr(statement.expr, scope)
            return

        if isinstance(statement, IfStmt):
            self._resolve_expr(statement.condition, scope)
            for child in statement.body:
                self._resolve_statement(child, scope)
            for child in statement.orelse:
                self._resolve_statement(child, scope)
            return

        if isinstance(statement, WhileStmt):
            self._resolve_expr(statement.condition, scope)
            for child in statement.body:
                self._resolve_statement(child, scope)
            for child in statement.orelse:
                self._resolve_statement(child, scope)
            return

        if isinstance(statement, ForStmt):
            self._resolve_expr(statement.iterator, scope)
            self._define_name(scope, statement.target, ValueType.UNKNOWN)
            for child in statement.body:
                self._resolve_statement(child, scope)
            for child in statement.orelse:
                self._resolve_statement(child, scope)
            return

        if isinstance(statement, TryStmt):
            for child in statement.body:
                self._resolve_statement(child, scope)
            for handler in statement.handlers:
                self._resolve_handler(handler, scope)
            for child in statement.finalbody:
                self._resolve_statement(child, scope)
            return

        if isinstance(statement, FunctionDef):
            for default in statement.defaults:
                self._resolve_expr(default, scope)
            local_function = FunctionType(
                name=statement.name,
                param_names=statement.params,
                param_types=[ValueType.UNKNOWN for _ in statement.params],
                defaults_count=len(statement.defaults),
                node=statement,
            )
            self._define_name(scope, statement.name, ValueType.UNKNOWN)
            if self.local_functions:
                self.local_functions[-1][statement.name] = local_function
            self._resolve_local_function(statement, scope, local_function)
            return

        if isinstance(statement, ClassDef):
            self._define_name(scope, statement.name, ValueType.UNKNOWN)
            for method in statement.methods:
                method_function = FunctionType(
                    name=f"{statement.name}.{method.name}",
                    param_names=method.params,
                    param_types=[ValueType.UNKNOWN for _ in method.params],
                    defaults_count=len(method.defaults),
                    node=method,
                )
                for default in method.defaults:
                    self._resolve_expr(default, scope)
                self._resolve_local_function(method, scope, method_function)
            return

        if isinstance(statement, ReturnStmt):
            if self.current_function is None:
                self._error(statement, "return is only valid inside a function")
                return
            if statement.value is not None:
                self._resolve_expr(statement.value, scope)
            return

        if isinstance(statement, RaiseStmt):
            self._resolve_expr(statement.value, scope)

    def _resolve_expr(self, expr, scope: Scope) -> None:
        if isinstance(expr, ConstantExpr):
            return

        if isinstance(expr, NameExpr):
            if self._is_builtin_function(expr.name):
                return
            if expr.name in self.table.functions:
                self._error(expr, f"function {expr.name!r} cannot be used as a value")
                return
            if scope.lookup(expr.name) is None:
                self._error(expr, f"undefined variable {expr.name!r}")
            return

        if isinstance(expr, UnaryExpr):
            self._resolve_expr(expr.operand, scope)
            return

        if isinstance(expr, BinaryExpr):
            self._resolve_expr(expr.left, scope)
            self._resolve_expr(expr.right, scope)
            return

        if isinstance(expr, CompareExpr):
            self._resolve_expr(expr.left, scope)
            self._resolve_expr(expr.right, scope)
            return

        if isinstance(expr, BoolOpExpr):
            self._resolve_expr(expr.left, scope)
            self._resolve_expr(expr.right, scope)
            return

        if isinstance(expr, CallExpr):
            if expr.func_name == "print":
                self._error(expr, "print() is only valid as a statement")
                return
            if self._is_builtin_function(expr.func_name):
                for arg in expr.args:
                    self._resolve_expr(arg, scope)
                for arg in expr.kwargs.values():
                    self._resolve_expr(arg, scope)
                return
            function = self.table.functions.get(expr.func_name)
            local_function = self._lookup_local_function(expr.func_name)
            target = function or local_function
            if target is None:
                if scope.lookup(expr.func_name) is not None:
                    for arg in expr.args:
                        self._resolve_expr(arg, scope)
                    for arg in expr.kwargs.values():
                        self._resolve_expr(arg, scope)
                    return
                self._error(expr, f"undefined function {expr.func_name!r}")
                return
            self._validate_call_shape(expr, target)
            target.reachable = True
            for arg in expr.args:
                self._resolve_expr(arg, scope)
            for arg in expr.kwargs.values():
                self._resolve_expr(arg, scope)
            if function is not None:
                self._resolve_function(function)
            return

        if isinstance(expr, ListExpr):
            for element in expr.elements:
                self._resolve_expr(element, scope)
            return

        if isinstance(expr, TupleExpr):
            for element in expr.elements:
                self._resolve_expr(element, scope)
            return

        if isinstance(expr, DictExpr):
            for key in expr.keys:
                self._resolve_expr(key, scope)
            for value in expr.values:
                self._resolve_expr(value, scope)
            return

        if isinstance(expr, SetExpr):
            for element in expr.elements:
                self._resolve_expr(element, scope)
            return

        if isinstance(expr, IfExpr):
            self._resolve_expr(expr.condition, scope)
            self._resolve_expr(expr.body, scope)
            self._resolve_expr(expr.orelse, scope)
            return

        if isinstance(expr, LambdaExpr):
            self._resolve_local_function(
                expr.func_def,
                scope,
                FunctionType(
                    name=expr.func_def.name,
                    param_names=expr.func_def.params,
                    param_types=[ValueType.UNKNOWN for _ in expr.func_def.params],
                    defaults_count=len(expr.func_def.defaults),
                    node=expr.func_def,
                )
            )
            return

        if isinstance(expr, IndexExpr):
            self._resolve_expr(expr.collection, scope)
            self._resolve_expr(expr.index, scope)
            return

        if isinstance(expr, SliceExpr):
            if expr.lower is not None:
                self._resolve_expr(expr.lower, scope)
            if expr.upper is not None:
                self._resolve_expr(expr.upper, scope)
            if expr.step is not None:
                self._resolve_expr(expr.step, scope)
            return

        if isinstance(expr, AttributeExpr):
            self._resolve_expr(expr.object, scope)
            return

        if isinstance(expr, MethodCallExpr):
            self._resolve_expr(expr.object, scope)
            for arg in expr.args:
                self._resolve_expr(arg, scope)
            for arg in expr.kwargs.values():
                self._resolve_expr(arg, scope)

    def _define_name(self, scope: Scope, name: str, value_type: ValueType) -> None:
        if name in scope.global_names:
            scope.root().define(name, value_type)
            return
        if name in scope.nonlocal_names:
            parent = scope.parent
            while parent is not None and parent.parent is not None:
                if name in parent.values:
                    parent.define(name, value_type)
                    return
                parent = parent.parent
            return
        scope.define(name, value_type)

    def _resolve_delete_target(self, target, scope: Scope) -> None:
        if isinstance(target, NameExpr):
            if scope.lookup(target.name) is None:
                self._error(target, f"undefined variable {target.name!r}")
            return
        if isinstance(target, IndexExpr):
            self._resolve_expr(target.collection, scope)
            self._resolve_expr(target.index, scope)
            return
        self._error(target, "unsupported delete target")

    def _error(self, node, message: str) -> None:
        self.errors.error("Semantic", message, node.span.line, node.span.column, node.span.end_line, node.span.end_column)

    def _resolve_local_function(self, statement: FunctionDef, enclosing_scope: Scope, function: FunctionType) -> None:
        scope = Scope(enclosing_scope)
        scope.define(statement.name, ValueType.UNKNOWN)
        for param in statement.params:
            scope.define(param, ValueType.UNKNOWN)

        previous = self.current_function
        self.current_function = function
        self.local_functions.append({statement.name: function})
        for child in statement.body:
            self._resolve_statement(child, scope)
        self.current_function = previous
        self.local_functions.pop()

    def _validate_call_shape(self, expr: CallExpr, function: FunctionType) -> None:
        total_params = len(function.param_names)
        required_params = total_params - function.defaults_count
        if len(expr.args) > total_params:
            self._error(expr, f"function {expr.func_name!r} expects at most {total_params} arguments, got {len(expr.args)}")
            return

        provided = set(function.param_names[: len(expr.args)])
        for name in expr.kwargs:
            if name not in function.param_names:
                self._error(expr, f"function {expr.func_name!r} got unexpected keyword argument {name!r}")
                continue
            if name in provided:
                self._error(expr, f"function {expr.func_name!r} got multiple values for argument {name!r}")
                continue
            provided.add(name)

        missing = [name for name in function.param_names[:required_params] if name not in provided]
        if missing:
            self._error(expr, f"function {expr.func_name!r} missing required argument {missing[0]!r}")

    def _lookup_local_function(self, name: str) -> FunctionType | None:
        for scope in reversed(self.local_functions):
            if name in scope:
                return scope[name]
        return None

    def _resolve_handler(self, handler: ExceptHandler, scope: Scope) -> None:
        handler_scope = Scope(scope)
        if handler.type_name is not None and handler_scope.lookup(handler.type_name) is None and not self._is_builtin_function(handler.type_name):
            self._error(handler, f"undefined exception type {handler.type_name!r}")
        if handler.name is not None:
            handler_scope.define(handler.name, ValueType.UNKNOWN)
        for child in handler.body:
            self._resolve_statement(child, handler_scope)
