from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    CallValueExpr,
    ClassDef,
    Comprehension,
    CompareExpr,
    CompareChainExpr,
    ConstantExpr,
    DeleteStmt,
    DictExpr,
    DictCompExpr,
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
    ListCompExpr,
    MethodCallExpr,
    NameExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    SetCompExpr,
    SliceExpr,
    StarUnpackAssignStmt,
    StarredExpr,
    KwStarredExpr,
    NamedExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WhileStmt,
    WithStmt,
)
from compiler.core.signature import bind_call_arguments
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
                for default in statement.defaults:
                    self._check_expr(default, table.global_scope)
                for default in statement.kwonly_defaults.values():
                    self._check_expr(default, table.global_scope)
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
        for param_name in function.kwonly_names:
            param_type = function.kwonly_types.get(param_name, ValueType.UNKNOWN)
            scope.define(param_name, param_type)
            function.local_types[param_name] = param_type
        if function.vararg_name is not None:
            scope.define(function.vararg_name, ValueType.TUPLE)
            function.local_types[function.vararg_name] = ValueType.TUPLE
        if function.kwarg_name is not None:
            scope.define(function.kwarg_name, ValueType.DICT)
            function.local_types[function.kwarg_name] = ValueType.DICT

        previous = self.current_function
        self.current_function = function
        for statement in function.node.body:
            self._check_statement(statement, scope)
        self.current_function = previous
        self.local_functions.pop()

        if function.return_type == ValueType.UNKNOWN and not function.has_value_return:
            function.return_type = ValueType.VOID
        function.state = "done"

    def _check_statement(self, statement, scope: Scope) -> None:
        if isinstance(statement, AssignStmt):
            value_type = self._check_expr(statement.value, scope)
            existing = self._existing_local_type(scope, statement.name)
            merged = merge_types(existing or ValueType.UNKNOWN, value_type)
            if merged is None:
                self._error(statement, f"cannot assign {value_type.value} to {statement.name!r} previously typed as {existing.value}")
                return
            self._define_name(scope, statement.name, merged)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = merged
            return

        if isinstance(statement, UnpackAssignStmt):
            value_type = self._check_expr(statement.value, scope)
            if value_type == ValueType.VOID:
                self._error(statement.value, "cannot unpack a void value")
            for target in statement.targets:
                self._define_name(scope, target, ValueType.UNKNOWN)
                if self.current_function is not None:
                    self.current_function.local_types[target] = ValueType.UNKNOWN
            return

        if isinstance(statement, StarUnpackAssignStmt):
            value_type = self._check_expr(statement.value, scope)
            if value_type == ValueType.VOID:
                self._error(statement.value, "cannot unpack a void value")
            for target in statement.prefix_targets:
                self._define_name(scope, target, ValueType.UNKNOWN)
                if self.current_function is not None:
                    self.current_function.local_types[target] = ValueType.UNKNOWN
            self._define_name(scope, statement.starred_target, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.starred_target] = ValueType.UNKNOWN
            for target in statement.suffix_targets:
                self._define_name(scope, target, ValueType.UNKNOWN)
                if self.current_function is not None:
                    self.current_function.local_types[target] = ValueType.UNKNOWN
            return

        if isinstance(statement, AttributeAssignStmt):
            object_type = self._check_expr(statement.object, scope)
            value_type = self._check_expr(statement.value, scope)
            if object_type == ValueType.VOID:
                self._error(statement.object, "cannot assign an attribute on a void value")
            if value_type == ValueType.VOID:
                self._error(statement.value, "cannot assign a void value to an attribute")
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
                self._check_delete_target(target, scope)
            return

        if isinstance(statement, ImportStmt):
            binding_name = self._import_binding_name(statement)
            self._define_name(scope, binding_name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[binding_name] = ValueType.UNKNOWN
            return

        if isinstance(statement, FromImportStmt):
            self._define_name(scope, statement.alias or statement.name, ValueType.UNKNOWN)
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
            target_type = ValueType.INT if self._is_range_call(statement.iterator) else ValueType.UNKNOWN
            if isinstance(statement.target, list):
                for name in statement.target:
                    self._define_name(scope, name, target_type)
                    if self.current_function is not None:
                        self.current_function.local_types[name] = target_type
            else:
                self._define_name(scope, statement.target, target_type)
                if self.current_function is not None:
                    self.current_function.local_types[statement.target] = target_type
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
            for child in statement.orelse:
                self._check_statement(child, scope)
            for child in statement.finalbody:
                self._check_statement(child, scope)
            return

        if isinstance(statement, WithStmt):
            context_type = self._check_expr(statement.context_expr, scope)
            if context_type == ValueType.VOID:
                self._error(statement.context_expr, "with context expression cannot be void")
            if statement.optional_var is not None:
                self._define_name(scope, statement.optional_var, ValueType.UNKNOWN)
                if self.current_function is not None:
                    self.current_function.local_types[statement.optional_var] = ValueType.UNKNOWN
            for child in statement.body:
                self._check_statement(child, scope)
            return

        if isinstance(statement, FunctionDef):
            for default in statement.defaults:
                self._check_expr(default, scope)
            for default in statement.kwonly_defaults.values():
                self._check_expr(default, scope)
            local_function = FunctionType(
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
            self._define_name(scope, statement.name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = ValueType.UNKNOWN
            if self.local_functions:
                self.local_functions[-1][statement.name] = local_function
            self._check_local_function(statement, scope, local_function)
            return

        if isinstance(statement, ClassDef):
            self._define_name(scope, statement.name, ValueType.UNKNOWN)
            if self.current_function is not None:
                self.current_function.local_types[statement.name] = ValueType.UNKNOWN
            for base in statement.bases:
                base_type = self._check_expr(base, scope)
                if base_type == ValueType.VOID:
                    self._error(base, "class base cannot be void")
            for attribute in statement.attributes:
                value_type = self._check_expr(attribute.value, scope)
                if value_type == ValueType.VOID:
                    self._error(attribute, "class attribute cannot be assigned a void value")
            for method in statement.methods:
                method_function = FunctionType(
                    name=f"{statement.name}.{method.name}",
                    param_names=method.params,
                    param_types=[ValueType.UNKNOWN for _ in method.params],
                    defaults_count=len(method.defaults),
                    kwonly_names=method.kwonly_params,
                    kwonly_types={name: ValueType.UNKNOWN for name in method.kwonly_params},
                    kwonly_defaults=set(method.kwonly_defaults),
                    vararg_name=method.vararg,
                    kwarg_name=method.kwarg,
                    node=method,
                )
                for default in method.defaults:
                    self._check_expr(default, scope)
                for default in method.kwonly_defaults.values():
                    self._check_expr(default, scope)
                self._check_local_function(method, scope, method_function)
            return

        if isinstance(statement, ReturnStmt):
            if self.current_function is None:
                return
            value_type = ValueType.VOID if statement.value is None else self._check_expr(statement.value, scope)
            if statement.value is not None:
                self.current_function.has_value_return = True
            merged = merge_types(self.current_function.return_type, value_type)
            if merged is None:
                self._error(statement, f"incompatible return type {value_type.value} in function {self.current_function.name!r}")
                return
            self.current_function.return_type = merged
            return

        if isinstance(statement, RaiseStmt):
            if statement.value is not None:
                value_type = self._check_expr(statement.value, scope)
                if value_type == ValueType.VOID:
                    self._error(statement, "cannot raise a void expression")
            if statement.cause is not None:
                cause_type = self._check_expr(statement.cause, scope)
                if cause_type == ValueType.VOID:
                    self._error(statement, "cannot raise from a void expression")

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
            if expr.name in self.table.functions:
                self._check_function(self.table.functions[expr.name])
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            value_type = scope.lookup(expr.name) or ValueType.UNKNOWN
            if value_type == ValueType.UNKNOWN and scope.has_wildcard_import():
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            return self._set_expr_type(expr, value_type)

        if isinstance(expr, UnaryExpr):
            operand_type = self._check_expr(expr.operand, scope)
            if expr.op == "-":
                if operand_type != ValueType.UNKNOWN and not is_numeric(operand_type):
                    self._error(expr, f"unary '-' requires a numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, operand_type if operand_type != ValueType.UNKNOWN else ValueType.INT)
            if expr.op == "+":
                if operand_type != ValueType.UNKNOWN and not is_numeric(operand_type):
                    self._error(expr, f"unary '+' requires a numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, operand_type if operand_type != ValueType.UNKNOWN else ValueType.INT)
            if expr.op == "not":
                if operand_type != ValueType.UNKNOWN and not can_truth_test(operand_type):
                    self._error(expr, f"'not' requires a bool or numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, ValueType.BOOL)
            if expr.op == "~":
                if operand_type != ValueType.UNKNOWN and not is_numeric(operand_type):
                    self._error(expr, f"unary '~' requires a numeric operand, got {operand_type.value}")
                return self._set_expr_type(expr, operand_type if operand_type != ValueType.UNKNOWN else ValueType.INT)

        if isinstance(expr, StarredExpr):
            inner_type = self._check_expr(expr.value, scope)
            if inner_type == ValueType.VOID:
                self._error(expr.value, "cannot splat a void value")
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        if isinstance(expr, KwStarredExpr):
            inner_type = self._check_expr(expr.value, scope)
            if inner_type == ValueType.VOID:
                self._error(expr.value, "cannot splat a void value")
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        if isinstance(expr, NamedExpr):
            value_type = self._check_expr(expr.value, scope)
            # Scope doesn't track assignments separately; updating the binding is enough.
            scope.define(expr.target, value_type)
            return self._set_expr_type(expr, value_type)

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
            if expr.op in {"//", "&", "|", "^", "<<", ">>"}:
                result = ValueType.INT
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

        if isinstance(expr, CompareChainExpr):
            operand_types = [self._check_expr(operand, scope) for operand in expr.operands]
            for index, op in enumerate(expr.ops):
                left_type = operand_types[index]
                right_type = operand_types[index + 1]
                if op in {"in", "not in", "is", "is not"}:
                    continue
                if op in {"<", "<=", ">", ">="}:
                    if left_type != ValueType.UNKNOWN and not is_numeric(left_type):
                        self._error(expr.operands[index], f"{op} requires numeric operands, got {left_type.value}")
                    if right_type != ValueType.UNKNOWN and not is_numeric(right_type):
                        self._error(expr.operands[index + 1], f"{op} requires numeric operands, got {right_type.value}")
                    continue
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
                for arg in expr.kwargs.values():
                    self._check_expr(arg, scope)
                return self._set_expr_type(expr, ValueType.UNKNOWN)
            self._validate_call_shape(expr, target)
            arg_types = [self._check_expr(arg, scope) for arg in expr.args]
            kwarg_types = {name: self._check_expr(arg, scope) for name, arg in expr.kwargs.items()}
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
            for name, arg_type in kwarg_types.items():
                if name in target.param_names:
                    index = target.param_names.index(name)
                    merged = merge_types(target.param_types[index], arg_type)
                    if merged is None:
                        self._error(expr.kwargs[name], f"argument {name!r} to {expr.func_name!r} has incompatible type {arg_type.value}")
                        continue
                    if merged != target.param_types[index]:
                        target.param_types[index] = merged
                        updated = True
                    continue
                if name not in target.kwonly_names:
                    continue
                existing = target.kwonly_types.get(name, ValueType.UNKNOWN)
                merged = merge_types(existing, arg_type)
                if merged is None:
                    self._error(expr.kwargs[name], f"argument {name!r} to {expr.func_name!r} has incompatible type {arg_type.value}")
                    continue
                if merged != existing:
                    target.kwonly_types[name] = merged
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

        if isinstance(expr, IfExpr):
            condition_type = self._check_expr(expr.condition, scope)
            if condition_type != ValueType.UNKNOWN and not can_truth_test(condition_type):
                self._error(expr.condition, f"ternary condition must be bool or numeric, got {condition_type.value}")
            body_type = self._check_expr(expr.body, scope)
            orelse_type = self._check_expr(expr.orelse, scope)
            merged = merge_types(body_type, orelse_type)
            result_type = merged if merged is not None else ValueType.UNKNOWN
            return self._set_expr_type(expr, result_type)

        if isinstance(expr, LambdaExpr):
            for default in expr.func_def.defaults:
                self._check_expr(default, scope)
            for default in expr.func_def.kwonly_defaults.values():
                self._check_expr(default, scope)
            local_function = FunctionType(
                name=expr.func_def.name,
                param_names=expr.func_def.params,
                param_types=[ValueType.UNKNOWN for _ in expr.func_def.params],
                defaults_count=len(expr.func_def.defaults),
                kwonly_names=expr.func_def.kwonly_params,
                kwonly_types={name: ValueType.UNKNOWN for name in expr.func_def.kwonly_params},
                kwonly_defaults=set(expr.func_def.kwonly_defaults),
                vararg_name=expr.func_def.vararg,
                kwarg_name=expr.func_def.kwarg,
                node=expr.func_def,
            )
            self._check_local_function(expr.func_def, scope, local_function)
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        if isinstance(expr, CallValueExpr):
            callee_type = self._check_expr(expr.callee, scope)
            if callee_type == ValueType.VOID:
                self._error(expr.callee, "cannot call a void value")
            for arg in expr.args:
                arg_type = self._check_expr(arg, scope)
                if arg_type == ValueType.VOID:
                    self._error(arg, "cannot pass a void expression as an argument")
            for arg in expr.kwargs.values():
                arg_type = self._check_expr(arg, scope)
                if arg_type == ValueType.VOID:
                    self._error(arg, "cannot pass a void expression as a keyword argument")
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        if isinstance(expr, ListCompExpr):
            comp_scope = self._check_comprehension(expr.generators, scope)
            element_type = self._check_expr(expr.element, comp_scope)
            if element_type == ValueType.VOID:
                self._error(expr.element, "list comprehension elements cannot be void")
            return self._set_expr_type(expr, ValueType.LIST)

        if isinstance(expr, SetCompExpr):
            comp_scope = self._check_comprehension(expr.generators, scope)
            element_type = self._check_expr(expr.element, comp_scope)
            if element_type == ValueType.VOID:
                self._error(expr.element, "set comprehension elements cannot be void")
            return self._set_expr_type(expr, ValueType.SET)

        if isinstance(expr, DictCompExpr):
            comp_scope = self._check_comprehension(expr.generators, scope)
            key_type = self._check_expr(expr.key, comp_scope)
            value_type = self._check_expr(expr.value, comp_scope)
            if key_type == ValueType.VOID:
                self._error(expr.key, "dict comprehension keys cannot be void")
            if value_type == ValueType.VOID:
                self._error(expr.value, "dict comprehension values cannot be void")
            return self._set_expr_type(expr, ValueType.DICT)

        if isinstance(expr, IndexExpr):
            collection_type = self._check_expr(expr.collection, scope)
            index_type = self._check_expr(expr.index, scope)
            if isinstance(expr.index, SliceExpr):
                if collection_type not in {ValueType.LIST, ValueType.TUPLE, ValueType.STRING, ValueType.UNKNOWN}:
                    self._error(expr.collection, f"cannot slice value of type {collection_type.value}")
                result_type = ValueType.STRING if collection_type == ValueType.STRING else ValueType.UNKNOWN
                return self._set_expr_type(expr, result_type)
            if collection_type == ValueType.DICT:
                if index_type == ValueType.VOID:
                    self._error(expr.index, "dict index cannot be void")
            elif index_type not in {ValueType.INT, ValueType.UNKNOWN}:
                self._error(expr.index, f"index must be int, got {index_type.value}")
            if collection_type not in {ValueType.LIST, ValueType.TUPLE, ValueType.STRING, ValueType.DICT, ValueType.UNKNOWN}:
                self._error(expr.collection, f"cannot index value of type {collection_type.value}")
            result_type = ValueType.STRING if collection_type == ValueType.STRING else ValueType.UNKNOWN
            return self._set_expr_type(expr, result_type)

        if isinstance(expr, SliceExpr):
            for part_name, part in (("lower", expr.lower), ("upper", expr.upper), ("step", expr.step)):
                if part is None:
                    continue
                part_type = self._check_expr(part, scope)
                if part_type not in {ValueType.INT, ValueType.UNKNOWN}:
                    self._error(part, f"slice {part_name} must be int, got {part_type.value}")
            return self._set_expr_type(expr, ValueType.UNKNOWN)

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
            for arg in expr.kwargs.values():
                self._check_expr(arg, scope)
            return self._set_expr_type(expr, ValueType.UNKNOWN)

        return self._set_expr_type(expr, ValueType.UNKNOWN)

    def _existing_local_type(self, scope: Scope, name: str) -> ValueType | None:
        if scope is self.table.global_scope:
            return scope.lookup(name)
        if name in scope.global_names:
            return scope.root().lookup(name)
        if name in scope.nonlocal_names:
            return scope.lookup_enclosing(name)
        return scope.values.get(name)

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

    def _check_delete_target(self, target, scope: Scope) -> None:
        if isinstance(target, NameExpr):
            return
        if isinstance(target, AttributeExpr):
            object_type = self._check_expr(target.object, scope)
            if object_type == ValueType.VOID:
                self._error(target.object, "cannot delete an attribute from a void value")
            return
        if isinstance(target, IndexExpr):
            self._check_expr(target.collection, scope)
            self._check_expr(target.index, scope)
            return
        self._error(target, "unsupported delete target")

    def _set_expr_type(self, expr, value_type: ValueType) -> ValueType:
        expr.inferred_type = value_type
        self.expr_types[id(expr)] = value_type
        return value_type

    def _check_comprehension(self, generators: list[Comprehension], scope: Scope) -> Scope:
        comp_scope = Scope(scope)
        for generator in generators:
            self._check_expr(generator.iterator, comp_scope)
            comp_scope.define(generator.target, ValueType.UNKNOWN)
            for condition in generator.ifs:
                condition_type = self._check_expr(condition, comp_scope)
                if condition_type != ValueType.UNKNOWN and not can_truth_test(condition_type):
                    self._error(condition, f"comprehension condition must be truth-testable, got {condition_type.value}")
        return comp_scope

    def _error(self, node, message: str) -> None:
        self.errors.error("Semantic", message, node.span.line, node.span.column, node.span.end_line, node.span.end_column)

    def _check_local_function(self, statement: FunctionDef, enclosing_scope: Scope, local_function: FunctionType) -> None:
        scope = Scope(enclosing_scope)
        scope.define(statement.name, ValueType.UNKNOWN)
        for param_name in statement.params:
            scope.define(param_name, ValueType.UNKNOWN)
            local_function.local_types[param_name] = ValueType.UNKNOWN
        for param_name in statement.kwonly_params:
            scope.define(param_name, ValueType.UNKNOWN)
            local_function.local_types[param_name] = ValueType.UNKNOWN
        if statement.vararg is not None:
            scope.define(statement.vararg, ValueType.TUPLE)
            local_function.local_types[statement.vararg] = ValueType.TUPLE
        if statement.kwarg is not None:
            scope.define(statement.kwarg, ValueType.DICT)
            local_function.local_types[statement.kwarg] = ValueType.DICT

        previous = self.current_function
        self.current_function = local_function
        self.local_functions.append({statement.name: local_function})
        for child in statement.body:
            self._check_statement(child, scope)
        self.current_function = previous
        self.local_functions.pop()
        if local_function.return_type == ValueType.UNKNOWN and not local_function.has_value_return:
            local_function.return_type = ValueType.VOID

    def _validate_call_shape(self, expr: CallExpr, function: FunctionType) -> None:
        # Calls with *args splats are dynamic in shape. Let runtime handle arity.
        if any(isinstance(arg, StarredExpr) for arg in expr.args):
            return
        if getattr(expr, "kw_starred", []):
            return
        positional_defaults = [object() for _ in range(function.defaults_count)]
        kwonly_defaults = {name: object() for name in function.kwonly_defaults}
        try:
            bind_call_arguments(
                expr.func_name,
                function.param_names,
                positional_defaults,
                [object() for _ in expr.args],
                {name: object() for name in expr.kwargs},
                kwonly_params=function.kwonly_names,
                kwonly_defaults=kwonly_defaults,
                vararg_name=function.vararg_name,
                kwarg_name=function.kwarg_name,
            )
        except ValueError as exc:
            self._error(expr, str(exc))

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
        for arg in expr.kwargs.values():
            self._check_expr(arg, scope)
        if expr.func_name == "print":
            return self._set_expr_type(expr, ValueType.VOID)
        if expr.func_name == "len":
            if expr.kwargs:
                self._error(expr, "len() does not accept keyword arguments")
                return self._set_expr_type(expr, ValueType.INT)
            if len(arg_types) != 1:
                self._error(expr, "len() expects exactly 1 argument")
                return self._set_expr_type(expr, ValueType.INT)
            container_type = arg_types[0]
            if container_type not in {ValueType.LIST, ValueType.TUPLE, ValueType.STRING, ValueType.DICT, ValueType.SET, ValueType.UNKNOWN}:
                self._error(expr.args[0], f"len() expects a list, tuple, string, dict, or set, got {container_type.value}")
            return self._set_expr_type(expr, ValueType.INT)
        if expr.func_name == "range":
            if expr.kwargs:
                self._error(expr, "range() does not accept keyword arguments")
                return self._set_expr_type(expr, ValueType.UNKNOWN)
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

    @staticmethod
    def _import_binding_name(statement: ImportStmt) -> str:
        return statement.alias or statement.module.split(".", 1)[0]
    @staticmethod
    def _is_range_call(expr) -> bool:
        return isinstance(expr, CallExpr) and expr.func_name == "range"

    @staticmethod
    def _import_binding_name(statement: ImportStmt) -> str:
        return statement.alias or statement.module.split(".", 1)[0]
