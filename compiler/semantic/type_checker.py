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
    DictExpr,
    ExceptHandler,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    IfStmt,
    IndexExpr,
    ImportStmt,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    WhileStmt,
)
from compiler.core.types import FunctionType, ValueType, can_truth_test, is_numeric, merge_types
from compiler.semantic.model import Scope, SymbolTable
from compiler.utils.error_handler import ErrorHandler


class TypeChecker:
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
        self.expr_types: dict[int, ValueType] = {}
        self.current_function: FunctionType | None = None
        self.local_functions: list[dict[str, FunctionType]] = []

    def check(self, program: Program, table: SymbolTable) -> dict[int, ValueType]:
        self.table = table
        for function in table.functions.values():
            function.state = "unvisited"
            function.return_type = ValueType.UNKNOWN
            function.local_types = {}

        for statement in program.body:
            if isinstance(statement, FunctionDef):
                continue
            self._check_statement(statement, table.global_scope)

        for function in table.functions.values():
            if function.state != "done":
                self._check_function(function)

        return self.expr_types

    @staticmethod
    def _is_builtin_function(name: str) -> bool:
        return name in TypeChecker.BUILTIN_NAMES

    def _check_function(self, function: FunctionType) -> None:
        if function.state == "done":
            return
        if function.state == "checking":
            return
        function.state = "checking"
        function.return_type = ValueType.UNKNOWN
        function.local_types = {}
        scope = Scope(self.table.global_scope)
        self.local_functions.append({})
        for param_name, param_type in zip(function.param_names, function.param_types):
            scope.define(param_name, param_type)
            function.local_types[param_name] = param_type

        previous = self.current_function
        self.current_function = function
        for statement in function.node.body:
            self._check_statement(statement, scope)
        self.current_function = previous
        self.local_functions.pop()

        if function.return_type == ValueType.UNKNOWN:
            function.return_type = ValueType.VOID
        function.state = "done"

    def _check_statement(self, statement, scope: Scope) -> None:
        if isinstance(statement, AssignStmt):
            value_type = self._check_expr(statement.value, scope)
            existing = scope.lookup(statement.name) if scope is self.table.global_scope else scope.values.get(statement.name)
            merged = merge_types(existing or ValueType.UNKNOWN, value_type)
            if merged is None:
                self._error(statement, f"cannot assign {value_type.value} to {statement.name!r} previously typed as {existing.value}")
                return
            scope.define(statement.name, merged)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = merged
            return

        if isinstance(statement, AttributeAssignStmt):
            object_type = self._check_expr(statement.object, scope)
            value_type = self._check_expr(statement.value, scope)
            if object_type == ValueType.VOID:
                self._error(statement.object, "cannot assign an attribute on a void value")
            if value_type == ValueType.VOID:
                self._error(statement.value, "cannot assign a void value to an attribute")
            return

        if isinstance(statement, ImportStmt):
            scope.define(statement.alias or statement.module, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.alias or statement.module] = ValueType.UNKNOWN
            return

        if isinstance(statement, FromImportStmt):
            scope.define(statement.alias or statement.name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.alias or statement.name] = ValueType.UNKNOWN
            return

        if isinstance(statement, PrintStmt):
            for value in statement.values:
                value_type = self._check_expr(value, scope)
                if value_type == ValueType.VOID:
                    self._error(statement, "cannot print a void expression")
            if statement.sep is not None:
                sep_type = self._check_expr(statement.sep, scope)
                if sep_type not in {ValueType.STRING, ValueType.UNKNOWN}:
                    self._error(statement.sep, f"print() sep must be str, got {sep_type.value}")
            if statement.end is not None:
                end_type = self._check_expr(statement.end, scope)
                if end_type not in {ValueType.STRING, ValueType.UNKNOWN}:
                    self._error(statement.end, f"print() end must be str, got {end_type.value}")
            return

        if isinstance(statement, ExprStmt):
            self._check_expr(statement.expr, scope)
            return

        if isinstance(statement, IfStmt):
            condition_type = self._check_expr(statement.condition, scope)
            if condition_type != ValueType.UNKNOWN and not can_truth_test(condition_type):
                self._error(statement.condition, f"condition must be bool or numeric, got {condition_type.value}")
            for child in statement.body:
                self._check_statement(child, scope)
            for child in statement.orelse:
                self._check_statement(child, scope)
            return

        if isinstance(statement, WhileStmt):
            condition_type = self._check_expr(statement.condition, scope)
            if condition_type != ValueType.UNKNOWN and not can_truth_test(condition_type):
                self._error(statement.condition, f"condition must be bool or numeric, got {condition_type.value}")
            for child in statement.body:
                self._check_statement(child, scope)
            for child in statement.orelse:
                self._check_statement(child, scope)
            return

        if isinstance(statement, ForStmt):
            iterator_type = self._check_expr(statement.iterator, scope)
            scope.define(statement.target, ValueType.INT if self._is_range_call(statement.iterator) else ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.target] = ValueType.INT if self._is_range_call(statement.iterator) else ValueType.UNKNOWN
            if iterator_type == ValueType.VOID:
                self._error(statement.iterator, "for-loop iterator cannot be void")
            for child in statement.body:
                self._check_statement(child, scope)
            for child in statement.orelse:
                self._check_statement(child, scope)
            return

        if isinstance(statement, TryStmt):
            for child in statement.body:
                self._check_statement(child, scope)
            for handler in statement.handlers:
                self._check_handler(handler, scope)
            for child in statement.finalbody:
                self._check_statement(child, scope)
            return

        if isinstance(statement, FunctionDef):
            local_function = FunctionType(
                name=statement.name,
                param_names=statement.params,
                param_types=[ValueType.UNKNOWN for _ in statement.params],
                node=statement,
            )
            scope.define(statement.name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = ValueType.UNKNOWN
            if self.local_functions:
                self.local_functions[-1][statement.name] = local_function
            self._check_local_function(statement, scope, local_function)
            return

        if isinstance(statement, ClassDef):
            scope.define(statement.name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = ValueType.UNKNOWN
            for method in statement.methods:
                method_function = FunctionType(
                    name=f"{statement.name}.{method.name}",
                    param_names=method.params,
                    param_types=[ValueType.UNKNOWN for _ in method.params],
                    node=method,
                )
                self._check_local_function(method, scope, method_function)
            return

        if isinstance(statement, ReturnStmt):
            if self.current_function is None:
                return
            value_type = ValueType.VOID if statement.value is None else self._check_expr(statement.value, scope)
            merged = merge_types(self.current_function.return_type, value_type)
            if merged is None:
                self._error(statement, f"incompatible return type {value_type.value} in function {self.current_function.name!r}")
                return
            self.current_function.return_type = merged
            return

        if isinstance(statement, RaiseStmt):
            value_type = self._check_expr(statement.value, scope)
            if value_type == ValueType.VOID:
                self._error(statement, "cannot raise a void expression")

    def _check_expr(self, expr, scope: Scope) -> ValueType:
        if isinstance(expr, ConstantExpr):
            if isinstance(expr.value, bool):
                return self._set_expr_type(expr, ValueType.BOOL)
            if isinstance(expr.value, int):
                return self._set_expr_type(expr, ValueType.INT)
            if isinstance(expr.value, float):
                return self._set_expr_type(expr, ValueType.FLOAT)
            return self._set_expr_type(expr, ValueType.STRING)

        if isinstance(expr, NameExpr):
            if self._is_builtin_function(expr.name):
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            value_type = scope.lookup(expr.name) or ValueType.UNKNOWN
            return self._set_expr_type(expr, value_type)

        if isinstance(expr, UnaryExpr):
            operand_type = self._check_expr(expr.operand, scope)
            if expr.op == "-":
                if operand_type != ValueType.UNKNOWN and not is_numeric(operand_type):
                    self._error(expr, f"unary '-' requires a numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, operand_type if operand_type != ValueType.UNKNOWN else ValueType.INT)
            if expr.op == "not":
                if operand_type != ValueType.UNKNOWN and not can_truth_test(operand_type):
                    self._error(expr, f"'not' requires a bool or numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, ValueType.BOOL)

        if isinstance(expr, BinaryExpr):
            left_type = self._check_expr(expr.left, scope)
            right_type = self._check_expr(expr.right, scope)
            if expr.op == "+" and left_type in {ValueType.STRING, ValueType.UNKNOWN} and right_type in {ValueType.STRING, ValueType.UNKNOWN}:
                if left_type == ValueType.STRING or right_type == ValueType.STRING:
                    return self._set_expr_type(expr, ValueType.STRING)
            if left_type != ValueType.UNKNOWN and not is_numeric(left_type):
                self._error(expr.left, f"{expr.op} requires numeric operands, got {left_type.value}")
            if right_type != ValueType.UNKNOWN and not is_numeric(right_type):
                self._error(expr.right, f"{expr.op} requires numeric operands, got {right_type.value}")
            result = merge_types(left_type, right_type) or ValueType.UNKNOWN
            if expr.op == "/":
                result = ValueType.FLOAT
            return self._set_expr_type(expr, result)

        if isinstance(expr, CompareExpr):
            left_type = self._check_expr(expr.left, scope)
            right_type = self._check_expr(expr.right, scope)
            if expr.op in {"in", "not in", "is", "is not"}:
                return self._set_expr_type(expr, ValueType.BOOL)
            if expr.op in ("<", "<=", ">", ">="):
                if left_type != ValueType.UNKNOWN and not is_numeric(left_type):
                    self._error(expr.left, f"{expr.op} requires numeric operands, got {left_type.value}")
                if right_type != ValueType.UNKNOWN and not is_numeric(right_type):
                    self._error(expr.right, f"{expr.op} requires numeric operands, got {right_type.value}")
            else:
                merged = merge_types(left_type, right_type)
                if merged is None and left_type != ValueType.UNKNOWN and right_type != ValueType.UNKNOWN:
                    self._error(expr, f"cannot compare {left_type.value} with {right_type.value}")
            return self._set_expr_type(expr, ValueType.BOOL)

        if isinstance(expr, BoolOpExpr):
            left_type = self._check_expr(expr.left, scope)
            right_type = self._check_expr(expr.right, scope)
            if left_type != ValueType.UNKNOWN and not can_truth_test(left_type):
                self._error(expr.left, f"{expr.op} requires bool or numeric operands, got {left_type.value}")
            if right_type != ValueType.UNKNOWN and not can_truth_test(right_type):
                self._error(expr.right, f"{expr.op} requires bool or numeric operands, got {right_type.value}")
            return self._set_expr_type(expr, ValueType.BOOL)

        if isinstance(expr, CallExpr):
            if self._is_builtin_function(expr.func_name):
                return self._check_builtin_call(expr, scope)
            function = self.table.functions.get(expr.func_name)
            local_function = self._lookup_local_function(expr.func_name)
            target = function or local_function
            if target is None:
                for arg in expr.args:
                    self._check_expr(arg, scope)
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            arg_types = [self._check_expr(arg, scope) for arg in expr.args]
            updated = False
            for index, arg_type in enumerate(arg_types):
                if index >= len(target.param_types):
                    break
                merged = merge_types(target.param_types[index], arg_type)
                if merged is None:
                    self._error(expr.args[index], f"argument {index + 1} to {expr.func_name!r} has incompatible type {arg_type.value}")
                    continue
                if merged != target.param_types[index]:
                    target.param_types[index] = merged
                    updated = True
            target.reachable = True
            if function is not None:
                if updated and function.state == "done":
                    function.state = "unvisited"
                self._check_function(function)
            return self._set_expr_type(expr, target.return_type)

        if isinstance(expr, ListExpr):
            for element in expr.elements:
                element_type = self._check_expr(element, scope)
                if element_type == ValueType.VOID:
                    self._error(element, "list elements cannot be void")
            return self._set_expr_type(expr, ValueType.LIST)

        if isinstance(expr, TupleExpr):
            for element in expr.elements:
                element_type = self._check_expr(element, scope)
                if element_type == ValueType.VOID:
                    self._error(element, "tuple elements cannot be void")
            return self._set_expr_type(expr, ValueType.TUPLE)

        if isinstance(expr, DictExpr):
            for key in expr.keys:
                key_type = self._check_expr(key, scope)
                if key_type == ValueType.VOID:
                    self._error(key, "dict keys cannot be void")
            for value in expr.values:
                value_type = self._check_expr(value, scope)
                if value_type == ValueType.VOID:
                    self._error(value, "dict values cannot be void")
            return self._set_expr_type(expr, ValueType.DICT)

        if isinstance(expr, SetExpr):
            for element in expr.elements:
                element_type = self._check_expr(element, scope)
                if element_type == ValueType.VOID:
                    self._error(element, "set elements cannot be void")
            return self._set_expr_type(expr, ValueType.SET)

        if isinstance(expr, IndexExpr):
            collection_type = self._check_expr(expr.collection, scope)
            index_type = self._check_expr(expr.index, scope)
            if collection_type == ValueType.DICT:
                if index_type == ValueType.VOID:
                    self._error(expr.index, "dict index cannot be void")
            elif index_type not in {ValueType.INT, ValueType.UNKNOWN}:
                self._error(expr.index, f"index must be int, got {index_type.value}")
            if collection_type not in {ValueType.LIST, ValueType.TUPLE, ValueType.STRING, ValueType.DICT, ValueType.UNKNOWN}:
                self._error(expr.collection, f"cannot index value of type {collection_type.value}")
            result_type = ValueType.STRING if collection_type == ValueType.STRING else ValueType.UNKNOWN
            return self._set_expr_type(expr, result_type)

        if isinstance(expr, AttributeExpr):
            object_type = self._check_expr(expr.object, scope)
            if object_type == ValueType.VOID:
                self._error(expr.object, "cannot access an attribute on a void value")
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        if isinstance(expr, MethodCallExpr):
            object_type = self._check_expr(expr.object, scope)
            if object_type == ValueType.VOID:
                self._error(expr.object, "cannot call a method on a void value")
            for arg in expr.args:
                self._check_expr(arg, scope)
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        return self._set_expr_type(expr, ValueType.UNKNOWN)

    def _set_expr_type(self, expr, value_type: ValueType) -> ValueType:
        expr.inferred_type = value_type
        self.expr_types[id(expr)] = value_type
        return value_type

    def _error(self, node, message: str) -> None:
        self.errors.error("Semantic", message, node.span.line, node.span.column, node.span.end_line, node.span.end_column)

    def _check_local_function(self, statement: FunctionDef, enclosing_scope: Scope, local_function: FunctionType) -> None:
        scope = Scope(enclosing_scope)
        scope.define(statement.name, ValueType.UNKNOWN)
        for param_name in statement.params:
            scope.define(param_name, ValueType.UNKNOWN)
            local_function.local_types[param_name] = ValueType.UNKNOWN

        previous = self.current_function
        self.current_function = local_function
        self.local_functions.append({statement.name: local_function})
        for child in statement.body:
            self._check_statement(child, scope)
        self.current_function = previous
        self.local_functions.pop()
        if local_function.return_type == ValueType.UNKNOWN:
            local_function.return_type = ValueType.VOID

    def _lookup_local_function(self, name: str) -> FunctionType | None:
        for scope in reversed(self.local_functions):
            if name in scope:
                return scope[name]
        return None

    def _check_handler(self, handler: ExceptHandler, scope: Scope) -> None:
        handler_scope = Scope(scope)
        if handler.name is not None:
            handler_scope.define(handler.name, ValueType.UNKNOWN)
        for child in handler.body:
            self._check_statement(child, handler_scope)

    def _check_builtin_call(self, expr: CallExpr, scope: Scope) -> ValueType:
        arg_types = [self._check_expr(arg, scope) for arg in expr.args]
        if expr.func_name == "print":
            return self._set_expr_type(expr, ValueType.VOID)
        if expr.func_name == "len":
            if len(arg_types) != 1:
                self._error(expr, "len() expects exactly 1 argument")
                return self._set_expr_type(expr, ValueType.INT)
            container_type = arg_types[0]
            if container_type not in {ValueType.LIST, ValueType.TUPLE, ValueType.STRING, ValueType.DICT, ValueType.SET, ValueType.UNKNOWN}:
                self._error(expr.args[0], f"len() expects a list, tuple, string, dict, or set, got {container_type.value}")
            return self._set_expr_type(expr, ValueType.INT)
        if expr.func_name == "range":
            if len(arg_types) not in {1, 2, 3}:
                self._error(expr, "range() expects 1 to 3 arguments")
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            for index, arg_type in enumerate(arg_types, start=1):
                if arg_type not in {ValueType.INT, ValueType.UNKNOWN}:
                    self._error(expr.args[index - 1], f"range() argument {index} must be int, got {arg_type.value}")
            return self._set_expr_type(expr, ValueType.UNKNOWN)
        if expr.func_name in {"str", "repr", "ascii"}:
            return self._set_expr_type(expr, ValueType.STRING)
        if expr.func_name == "dict":
            return self._set_expr_type(expr, ValueType.DICT)
        if expr.func_name == "set":
            return self._set_expr_type(expr, ValueType.SET)
        if expr.func_name == "list":
            return self._set_expr_type(expr, ValueType.LIST)
        if expr.func_name == "tuple":
            return self._set_expr_type(expr, ValueType.TUPLE)
        return self._set_expr_type(expr, ValueType.UNKNOWN)

    @staticmethod
    def _is_range_call(expr) -> bool:
        return isinstance(expr, CallExpr) and expr.func_name == "range"
