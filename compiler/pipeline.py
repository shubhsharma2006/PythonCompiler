from __future__ import annotations

from dataclasses import dataclass
import copy
import os
import subprocess

from compiler.backend import CCodeGenerator
from compiler.core.ast import (
    AttributeAssignStmt,
    AttributeExpr,
    BoolOpExpr,
    CallExpr,
    CompareExpr,
    DictCompExpr,
    ClassDef,
    DeleteStmt,
    DictExpr,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    IfStmt,
    ImportStmt,
    IndexExpr,
    ListCompExpr,
    PrintStmt,
    Program,
    RaiseStmt,
    SetExpr,
    SetCompExpr,
    TryStmt,
    WhileStmt,
    BinaryExpr,
    UnaryExpr,
    ListExpr,
    MethodCallExpr,
    NonlocalStmt,
    TupleExpr,
    SliceExpr,
    UnpackAssignStmt,
    WithStmt,
)
from compiler.core.types import ValueType
from compiler.frontend import LexedSource, ParsedModule, lex_source, lower_cst, parse_tokens
from compiler.ir import (
    CFGConstantPropagation,
    IRGenerator,
    IRModule,
    SSAConstantPropagation,
    SSACopyPropagation,
    SSADeadCodeEliminator,
    SSADestructor,
    SSAValuePropagation,
    SSATransformer,
)
from compiler.optimizer import ConstantFolder
from compiler.runtime import CRuntimeSupport
from compiler.semantic import SemanticAnalyzer, SemanticModel
from compiler.utils.error_handler import ErrorHandler
from compiler.vm import BytecodeInterpreter, BytecodeLowerer, BytecodeModule, VMError


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


def _program_uses_imports(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, (ImportStmt, FromImportStmt)):
                return True
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, IfStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, WhileStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, ForStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, TryStmt) and (walk(statement.body) or any(walk(handler.body) for handler in statement.handlers)):
                return True
        return False

    return walk(program.body)


def _program_uses_nested_functions(program: Program) -> bool:
    def walk(statements: list[object], in_function: bool = False) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef):
                if in_function:
                    return True
                if walk(statement.body, True):
                    return True
            elif isinstance(statement, IfStmt):
                if walk(statement.body, in_function) or walk(statement.orelse, in_function):
                    return True
            elif isinstance(statement, WhileStmt):
                if walk(statement.body, in_function) or walk(statement.orelse, in_function):
                    return True
            elif isinstance(statement, ForStmt):
                if walk(statement.body, in_function) or walk(statement.orelse, in_function):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body, in_function):
                    return True
                if any(walk(handler.body, in_function) for handler in statement.handlers):
                    return True
        return False

    return walk(program.body, False)


def _program_uses_exceptions(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, (RaiseStmt, TryStmt)):
                return True
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, IfStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, WhileStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, ForStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
        return False

    return walk(program.body)


def _program_uses_for_loops(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, ForStmt):
                return True
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, IfStmt) and (walk(statement.body) or walk(statement.orelse)):
                return True
            if isinstance(statement, WhileStmt) and walk(statement.body):
                return True
            if isinstance(statement, TryStmt) and (walk(statement.body) or any(walk(handler.body) for handler in statement.handlers)):
                return True
        return False

    return walk(program.body)


def _expr_uses_container_features(expr) -> bool:
    if isinstance(expr, (ListExpr, TupleExpr, DictExpr, SetExpr, IndexExpr, ListCompExpr, SetCompExpr, DictCompExpr)):
        return True
    if isinstance(expr, CallExpr):
        if expr.func_name in {"len", "dict", "set", "list", "tuple"}:
            return True
        return any(_expr_uses_container_features(arg) for arg in expr.args) or any(
            _expr_uses_container_features(arg) for arg in expr.kwargs.values()
        )
    if isinstance(expr, BinaryExpr):
        return _expr_uses_container_features(expr.left) or _expr_uses_container_features(expr.right)
    if isinstance(expr, CompareExpr):
        return _expr_uses_container_features(expr.left) or _expr_uses_container_features(expr.right)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_container_features(expr.left) or _expr_uses_container_features(expr.right)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_container_features(expr.operand)
    if isinstance(expr, AttributeExpr):
        return _expr_uses_container_features(expr.object)
    if isinstance(expr, MethodCallExpr):
        return (
            _expr_uses_container_features(expr.object)
            or any(_expr_uses_container_features(arg) for arg in expr.args)
            or any(_expr_uses_container_features(arg) for arg in expr.kwargs.values())
        )
    return False


def _program_uses_container_features(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, IfStmt):
                if _expr_uses_container_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_container_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_container_features(statement.iterator) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers):
                    return True
            else:
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_container_features(value):
                    return True
                if expr is not None and _expr_uses_container_features(expr):
                    return True
        return False

    return walk(program.body)


def _expr_uses_object_features(expr) -> bool:
    if isinstance(expr, (AttributeExpr, MethodCallExpr)):
        return True
    if isinstance(expr, CallExpr):
        return any(_expr_uses_object_features(arg) for arg in expr.args)
    if isinstance(expr, BinaryExpr):
        return _expr_uses_object_features(expr.left) or _expr_uses_object_features(expr.right)
    if isinstance(expr, CompareExpr):
        return _expr_uses_object_features(expr.left) or _expr_uses_object_features(expr.right)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_object_features(expr.left) or _expr_uses_object_features(expr.right)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_object_features(expr.operand)
    if isinstance(expr, IndexExpr):
        return _expr_uses_object_features(expr.collection) or _expr_uses_object_features(expr.index)
    if isinstance(expr, ListExpr):
        return any(_expr_uses_object_features(element) for element in expr.elements)
    if isinstance(expr, TupleExpr):
        return any(_expr_uses_object_features(element) for element in expr.elements)
    if isinstance(expr, ListCompExpr):
        return _expr_uses_object_features(expr.element) or any(
            _expr_uses_object_features(generator.iterator) or any(_expr_uses_object_features(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, SetCompExpr):
        return _expr_uses_object_features(expr.element) or any(
            _expr_uses_object_features(generator.iterator) or any(_expr_uses_object_features(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, DictCompExpr):
        return (
            _expr_uses_object_features(expr.key)
            or _expr_uses_object_features(expr.value)
            or any(
                _expr_uses_object_features(generator.iterator) or any(_expr_uses_object_features(condition) for condition in generator.ifs)
                for generator in expr.generators
            )
        )
    return False


def _program_uses_object_features(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, ClassDef):
                return True
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, IfStmt):
                if _expr_uses_object_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_object_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_object_features(statement.iterator) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers):
                    return True
            else:
                if isinstance(statement, AttributeAssignStmt):
                    if _expr_uses_object_features(statement.object) or _expr_uses_object_features(statement.value):
                        return True
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_object_features(value):
                    return True
                if expr is not None and _expr_uses_object_features(expr):
                    return True
        return False

    return walk(program.body)


def _expr_uses_call_signature_features(expr) -> bool:
    if isinstance(expr, CallExpr):
        return bool(expr.kwargs) or any(_expr_uses_call_signature_features(arg) for arg in expr.args) or any(
            _expr_uses_call_signature_features(arg) for arg in expr.kwargs.values()
        )
    if isinstance(expr, MethodCallExpr):
        return (
            bool(expr.kwargs)
            or _expr_uses_call_signature_features(expr.object)
            or any(_expr_uses_call_signature_features(arg) for arg in expr.args)
            or any(_expr_uses_call_signature_features(arg) for arg in expr.kwargs.values())
        )
    if isinstance(expr, BinaryExpr):
        return _expr_uses_call_signature_features(expr.left) or _expr_uses_call_signature_features(expr.right)
    if isinstance(expr, CompareExpr):
        return _expr_uses_call_signature_features(expr.left) or _expr_uses_call_signature_features(expr.right)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_call_signature_features(expr.left) or _expr_uses_call_signature_features(expr.right)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_call_signature_features(expr.operand)
    if isinstance(expr, IndexExpr):
        return _expr_uses_call_signature_features(expr.collection) or _expr_uses_call_signature_features(expr.index)
    if isinstance(expr, ListExpr):
        return any(_expr_uses_call_signature_features(element) for element in expr.elements)
    if isinstance(expr, TupleExpr):
        return any(_expr_uses_call_signature_features(element) for element in expr.elements)
    if isinstance(expr, DictExpr):
        return any(_expr_uses_call_signature_features(key) for key in expr.keys) or any(
            _expr_uses_call_signature_features(value) for value in expr.values
        )
    if isinstance(expr, SetExpr):
        return any(_expr_uses_call_signature_features(element) for element in expr.elements)
    if isinstance(expr, AttributeExpr):
        return _expr_uses_call_signature_features(expr.object)
    if isinstance(expr, ListCompExpr):
        return _expr_uses_call_signature_features(expr.element) or any(
            _expr_uses_call_signature_features(generator.iterator) or any(_expr_uses_call_signature_features(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, SetCompExpr):
        return _expr_uses_call_signature_features(expr.element) or any(
            _expr_uses_call_signature_features(generator.iterator) or any(_expr_uses_call_signature_features(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, DictCompExpr):
        return (
            _expr_uses_call_signature_features(expr.key)
            or _expr_uses_call_signature_features(expr.value)
            or any(
                _expr_uses_call_signature_features(generator.iterator) or any(_expr_uses_call_signature_features(condition) for condition in generator.ifs)
                for generator in expr.generators
            )
        )
    return False


def _program_uses_call_signature_features(program: Program) -> bool:
    def function_uses_defaults(function: FunctionDef) -> bool:
        return (
            bool(function.defaults)
            or bool(function.kwonly_params)
            or function.vararg is not None
            or function.kwarg is not None
            or any(_expr_uses_call_signature_features(default) for default in function.defaults)
            or any(_expr_uses_call_signature_features(default) for default in function.kwonly_defaults.values())
        )

    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef):
                if function_uses_defaults(statement) or walk(statement.body):
                    return True
            elif isinstance(statement, ClassDef):
                for method in statement.methods:
                    if function_uses_defaults(method) or walk(method.body):
                        return True
            elif isinstance(statement, IfStmt):
                if _expr_uses_call_signature_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_call_signature_features(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_call_signature_features(statement.iterator) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers) or walk(statement.finalbody):
                    return True
            elif isinstance(statement, PrintStmt):
                if any(_expr_uses_call_signature_features(value) for value in statement.values):
                    return True
                if statement.sep is not None and _expr_uses_call_signature_features(statement.sep):
                    return True
                if statement.end is not None and _expr_uses_call_signature_features(statement.end):
                    return True
            else:
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_call_signature_features(value):
                    return True
                if expr is not None and _expr_uses_call_signature_features(expr):
                    return True
        return False

    return walk(program.body)


def _expr_uses_slicing(expr) -> bool:
    if isinstance(expr, SliceExpr):
        return True
    if isinstance(expr, IndexExpr):
        return _expr_uses_slicing(expr.collection) or _expr_uses_slicing(expr.index)
    if isinstance(expr, CallExpr):
        return any(_expr_uses_slicing(arg) for arg in expr.args) or any(_expr_uses_slicing(arg) for arg in expr.kwargs.values())
    if isinstance(expr, MethodCallExpr):
        return (
            _expr_uses_slicing(expr.object)
            or any(_expr_uses_slicing(arg) for arg in expr.args)
            or any(_expr_uses_slicing(arg) for arg in expr.kwargs.values())
        )
    if isinstance(expr, BinaryExpr):
        return _expr_uses_slicing(expr.left) or _expr_uses_slicing(expr.right)
    if isinstance(expr, CompareExpr):
        return _expr_uses_slicing(expr.left) or _expr_uses_slicing(expr.right)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_slicing(expr.left) or _expr_uses_slicing(expr.right)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_slicing(expr.operand)
    if isinstance(expr, ListExpr):
        return any(_expr_uses_slicing(element) for element in expr.elements)
    if isinstance(expr, TupleExpr):
        return any(_expr_uses_slicing(element) for element in expr.elements)
    if isinstance(expr, DictExpr):
        return any(_expr_uses_slicing(key) for key in expr.keys) or any(_expr_uses_slicing(value) for value in expr.values)
    if isinstance(expr, SetExpr):
        return any(_expr_uses_slicing(element) for element in expr.elements)
    if isinstance(expr, AttributeExpr):
        return _expr_uses_slicing(expr.object)
    if isinstance(expr, ListCompExpr):
        return _expr_uses_slicing(expr.element) or any(
            _expr_uses_slicing(generator.iterator) or any(_expr_uses_slicing(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, SetCompExpr):
        return _expr_uses_slicing(expr.element) or any(
            _expr_uses_slicing(generator.iterator) or any(_expr_uses_slicing(condition) for condition in generator.ifs)
            for generator in expr.generators
        )
    if isinstance(expr, DictCompExpr):
        return (
            _expr_uses_slicing(expr.key)
            or _expr_uses_slicing(expr.value)
            or any(
                _expr_uses_slicing(generator.iterator) or any(_expr_uses_slicing(condition) for condition in generator.ifs)
                for generator in expr.generators
            )
        )
    return False


def _program_uses_core_vm_only_features(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, (UnpackAssignStmt, DeleteStmt, GlobalStmt, NonlocalStmt, WithStmt)):
                return True
            if isinstance(statement, FunctionDef):
                if any(_expr_uses_slicing(default) for default in statement.defaults) or walk(statement.body):
                    return True
            elif isinstance(statement, ClassDef):
                for method in statement.methods:
                    if any(_expr_uses_slicing(default) for default in method.defaults) or walk(method.body):
                        return True
            elif isinstance(statement, IfStmt):
                if _expr_uses_slicing(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_slicing(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_slicing(statement.iterator) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers) or walk(statement.finalbody):
                    return True
            elif isinstance(statement, WithStmt):
                if _expr_uses_slicing(statement.context_expr) or walk(statement.body):
                    return True
            elif isinstance(statement, PrintStmt):
                if any(_expr_uses_slicing(value) for value in statement.values):
                    return True
                if statement.sep is not None and _expr_uses_slicing(statement.sep):
                    return True
                if statement.end is not None and _expr_uses_slicing(statement.end):
                    return True
            else:
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_slicing(value):
                    return True
                if expr is not None and _expr_uses_slicing(expr):
                    return True
        return False

    return walk(program.body)


VM_ONLY_BUILTIN_CALLS = {
    "repr", "ascii", "int", "float", "bool", "list", "dict", "set", "tuple", "bytes", "bytearray",
    "frozenset", "complex", "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "callable", "id", "enumerate", "zip", "map", "filter", "reversed", "sorted", "iter", "next", "abs",
    "round", "min", "max", "sum", "pow", "divmod", "hash", "hex", "oct", "bin", "chr", "ord", "format",
    "input", "open", "any", "all", "object", "super", "property", "staticmethod", "classmethod", "vars",
    "dir",
}


def _expr_uses_vm_only_builtin_calls(expr) -> bool:
    if isinstance(expr, CallExpr):
        if expr.func_name in VM_ONLY_BUILTIN_CALLS:
            return True
        return any(_expr_uses_vm_only_builtin_calls(arg) for arg in expr.args) or any(
            _expr_uses_vm_only_builtin_calls(arg) for arg in expr.kwargs.values()
        )
    if isinstance(expr, BinaryExpr):
        return _expr_uses_vm_only_builtin_calls(expr.left) or _expr_uses_vm_only_builtin_calls(expr.right)
    if isinstance(expr, CompareExpr):
        return _expr_uses_vm_only_builtin_calls(expr.left) or _expr_uses_vm_only_builtin_calls(expr.right)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_vm_only_builtin_calls(expr.left) or _expr_uses_vm_only_builtin_calls(expr.right)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_vm_only_builtin_calls(expr.operand)
    if isinstance(expr, IndexExpr):
        return _expr_uses_vm_only_builtin_calls(expr.collection) or _expr_uses_vm_only_builtin_calls(expr.index)
    if isinstance(expr, ListExpr):
        return any(_expr_uses_vm_only_builtin_calls(element) for element in expr.elements)
    if isinstance(expr, TupleExpr):
        return any(_expr_uses_vm_only_builtin_calls(element) for element in expr.elements)
    if isinstance(expr, AttributeExpr):
        return _expr_uses_vm_only_builtin_calls(expr.object)
    if isinstance(expr, MethodCallExpr):
        return (
            _expr_uses_vm_only_builtin_calls(expr.object)
            or any(_expr_uses_vm_only_builtin_calls(arg) for arg in expr.args)
            or any(_expr_uses_vm_only_builtin_calls(arg) for arg in expr.kwargs.values())
        )
    return False


def _program_uses_vm_only_builtin_calls(program: Program) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, ClassDef):
                for method in statement.methods:
                    if walk(method.body):
                        return True
            if isinstance(statement, IfStmt):
                if _expr_uses_vm_only_builtin_calls(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_vm_only_builtin_calls(statement.condition) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_vm_only_builtin_calls(statement.iterator) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers) or walk(statement.finalbody):
                    return True
            elif isinstance(statement, PrintStmt):
                if any(_expr_uses_vm_only_builtin_calls(value) for value in statement.values):
                    return True
                if statement.sep is not None and _expr_uses_vm_only_builtin_calls(statement.sep):
                    return True
                if statement.end is not None and _expr_uses_vm_only_builtin_calls(statement.end):
                    return True
            else:
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_vm_only_builtin_calls(value):
                    return True
                if expr is not None and _expr_uses_vm_only_builtin_calls(expr):
                    return True
        return False

    return walk(program.body)


def _expr_uses_vm_only_string_features(expr, semantic: SemanticModel) -> bool:
    if isinstance(expr, BinaryExpr):
        if expr.op == "+" and semantic.expr_type(expr) == ValueType.STRING:
            return True
        return _expr_uses_vm_only_string_features(expr.left, semantic) or _expr_uses_vm_only_string_features(expr.right, semantic)
    if isinstance(expr, CallExpr):
        return any(_expr_uses_vm_only_string_features(arg, semantic) for arg in expr.args) or any(
            _expr_uses_vm_only_string_features(arg, semantic) for arg in expr.kwargs.values()
        )
    if isinstance(expr, CompareExpr):
        return _expr_uses_vm_only_string_features(expr.left, semantic) or _expr_uses_vm_only_string_features(expr.right, semantic)
    if isinstance(expr, BoolOpExpr):
        return _expr_uses_vm_only_string_features(expr.left, semantic) or _expr_uses_vm_only_string_features(expr.right, semantic)
    if isinstance(expr, UnaryExpr):
        return _expr_uses_vm_only_string_features(expr.operand, semantic)
    if isinstance(expr, IndexExpr):
        return _expr_uses_vm_only_string_features(expr.collection, semantic) or _expr_uses_vm_only_string_features(expr.index, semantic)
    if isinstance(expr, ListExpr):
        return any(_expr_uses_vm_only_string_features(element, semantic) for element in expr.elements)
    if isinstance(expr, TupleExpr):
        return any(_expr_uses_vm_only_string_features(element, semantic) for element in expr.elements)
    if isinstance(expr, AttributeExpr):
        return _expr_uses_vm_only_string_features(expr.object, semantic)
    if isinstance(expr, MethodCallExpr):
        return (
            _expr_uses_vm_only_string_features(expr.object, semantic)
            or any(_expr_uses_vm_only_string_features(arg, semantic) for arg in expr.args)
            or any(_expr_uses_vm_only_string_features(arg, semantic) for arg in expr.kwargs.values())
        )
    return False


def _program_uses_vm_only_print_or_string_features(program: Program, semantic: SemanticModel) -> bool:
    def walk(statements: list[object]) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef) and walk(statement.body):
                return True
            if isinstance(statement, ClassDef):
                for method in statement.methods:
                    if walk(method.body):
                        return True
            if isinstance(statement, IfStmt):
                if _expr_uses_vm_only_string_features(statement.condition, semantic) or walk(statement.body) or walk(statement.orelse):
                    return True
            elif isinstance(statement, WhileStmt):
                if _expr_uses_vm_only_string_features(statement.condition, semantic) or walk(statement.body):
                    return True
            elif isinstance(statement, ForStmt):
                if _expr_uses_vm_only_string_features(statement.iterator, semantic) or walk(statement.body):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body) or any(walk(handler.body) for handler in statement.handlers) or walk(statement.finalbody):
                    return True
            elif isinstance(statement, PrintStmt):
                if len(statement.values) != 1 or statement.sep is not None or statement.end is not None:
                    return True
                if semantic.expr_type(statement.values[0]) not in {ValueType.INT, ValueType.FLOAT, ValueType.BOOL, ValueType.STRING}:
                    return True
                if any(_expr_uses_vm_only_string_features(value, semantic) for value in statement.values):
                    return True
            else:
                value = getattr(statement, "value", None)
                expr = getattr(statement, "expr", None)
                if value is not None and _expr_uses_vm_only_string_features(value, semantic):
                    return True
                if expr is not None and _expr_uses_vm_only_string_features(expr, semantic):
                    return True
        return False

    return walk(program.body)


def _module_name_for_filename(filename: str) -> str:
    if filename == "<stdin>":
        return "__main__"
    return os.path.splitext(os.path.basename(filename))[0]


def _resolve_import_path(module_name: str, requester_filename: str) -> str:
    requester_dir = os.path.dirname(os.path.abspath(requester_filename)) or os.getcwd()
    module_parts = module_name.split(".")
    search_roots = [requester_dir]

    for root in search_roots:
        module_file = os.path.join(root, *module_parts) + ".py"
        package_init = os.path.join(root, *module_parts, "__init__.py")
        if os.path.exists(module_file):
            return os.path.abspath(module_file)
        if os.path.exists(package_init):
            return os.path.abspath(package_init)

    raise VMError(f"cannot resolve local module {module_name!r}")


def _load_bytecode_module(module_name: str, requester_filename: str) -> BytecodeModule:
    module_path = _resolve_import_path(module_name, requester_filename)
    with open(module_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    result = _analyze_source(source, filename=module_path)
    if not result.success or result.program is None:
        rendered = result.errors.render() or f"failed to analyze module {module_name!r}"
        raise VMError(rendered)
    return BytecodeLowerer().lower(
        result.program,
        module_name=module_name,
        filename=os.path.abspath(module_path),
    )


def _analyze_source(
    source: str,
    *,
    filename: str = "<stdin>",
) -> CompilationResult:
    errors = ErrorHandler(source=source, filename=filename)
    lexed = lex_source(source, filename, errors)
    if lexed is None or errors.has_errors():
        return CompilationResult(success=False, errors=errors, lexed=lexed)

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


def check_source(
    source: str,
    *,
    filename: str = "<stdin>",
) -> CompilationResult:
    return _analyze_source(source, filename=filename)


def execute_source(
    source: str,
    *,
    filename: str = "<stdin>",
) -> CompilationResult:
    result = _analyze_source(source, filename=filename)
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


def compile_source(
    source: str,
    *,
    filename: str = "<stdin>",
    output: str = "output.c",
    run: bool = False,
) -> CompilationResult:
    result = _analyze_source(source, filename=filename)
    if not result.success or result.program is None or result.semantic is None:
        return result
    if _program_uses_imports(result.program):
        result.errors.error("Codegen", "native compilation does not support imports yet")
        result.success = False
        return result
    if _program_uses_nested_functions(result.program):
        result.errors.error("Codegen", "native compilation does not support nested functions yet")
        result.success = False
        return result
    if _program_uses_exceptions(result.program):
        result.errors.error("Codegen", "native compilation does not support exceptions yet")
        result.success = False
        return result
    if _program_uses_core_vm_only_features(result.program):
        result.errors.error("Codegen", "native compilation does not support slicing, unpacking assignment, delete, global/nonlocal, or with statements yet")
        result.success = False
        return result
    if _program_uses_container_features(result.program):
        result.errors.error("Codegen", "native compilation does not support lists, tuples, indexing, or len() yet")
        result.success = False
        return result
    if _program_uses_object_features(result.program):
        result.errors.error("Codegen", "native compilation does not support classes, attributes, or methods yet")
        result.success = False
        return result
    if _program_uses_call_signature_features(result.program):
        result.errors.error("Codegen", "native compilation does not support default or keyword arguments yet")
        result.success = False
        return result
    if _program_uses_vm_only_builtin_calls(result.program):
        result.errors.error("Codegen", "native compilation does not support these builtin calls yet")
        result.success = False
        return result

    cfg_module = IRGenerator(result.semantic).generate(result.program)
    cfg_module = CFGConstantPropagation().optimize(cfg_module)
    ssa_module = SSATransformer().transform(copy.deepcopy(cfg_module))
    ssa_module = SSAConstantPropagation().optimize(ssa_module)
    ssa_module = SSAValuePropagation().optimize(ssa_module)
    ssa_module = SSACopyPropagation().optimize(ssa_module)
    ssa_module = SSADeadCodeEliminator().optimize(ssa_module)
    ir_module = SSADestructor().lower(ssa_module)
    runtime = CRuntimeSupport()
    c_code = CCodeGenerator().generate(ir_module)
    output_path = os.path.abspath(output)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(c_code)
    runtime_header_path, runtime_source_path = runtime.emit_files(output_path)

    result.ir = ir_module
    result.ssa = ssa_module
    result.c_code = c_code
    result.output_path = output_path
    result.runtime_header_path = runtime_header_path
    result.runtime_source_path = runtime_source_path

    if run:
        executable_path = os.path.abspath(os.path.splitext(output_path)[0] or "output")
        compile_proc = subprocess.run(
            ["gcc", output_path, runtime_source_path, "-o", executable_path],
            capture_output=True,
            text=True,
        )
        if compile_proc.returncode != 0:
            result.errors.error("Codegen", compile_proc.stderr.strip() or "gcc failed")
            result.success = False
            result.executable_path = executable_path
            result.run_error = compile_proc.stderr
            return result
        run_proc = subprocess.run([executable_path], capture_output=True, text=True)
        result.executable_path = executable_path
        result.run_output = run_proc.stdout
        result.run_error = run_proc.stderr
        if run_proc.returncode != 0:
            result.errors.error("Runtime", f"program exited with status {run_proc.returncode}")
            result.success = False

    return result
