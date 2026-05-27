from __future__ import annotations

from dataclasses import fields, is_dataclass

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    CallValueExpr,
    ClassDef,
    CompareChainExpr,
    DeleteStmt,
    DictCompExpr,
    DictExpr,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    ImportStmt,
    IndexAssignStmt,
    IndexExpr,
    ListCompExpr,
    ListExpr,
    LambdaExpr,
    MethodCallExpr,
    NonlocalStmt,
    PrintStmt,
    Program,
    SetCompExpr,
    SetExpr,
    SliceExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WithStmt,
    YieldExpr,
    YieldFromExpr,
    GeneratorExpr,
)


VM_ONLY_BUILTIN_CALLS = {
    "repr", "ascii", "int", "float", "bool", "list", "dict", "set", "tuple", "bytes", "bytearray",
    "frozenset", "complex", "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "callable", "id", "enumerate", "zip", "map", "filter", "reversed", "sorted", "iter", "next", "abs",
    "round", "min", "max", "sum", "pow", "divmod", "hash", "hex", "oct", "bin", "chr", "ord", "format",
    "input", "open", "any", "all", "object", "super", "property", "staticmethod", "classmethod", "vars",
    "dir",
}


def _iter_nodes(value):
    if is_dataclass(value):
        yield value
        for field in fields(value):
            if not field.init:
                continue
            if field.name in {"span"}:
                continue
            yield from _iter_nodes(getattr(value, field.name))
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_nodes(item)


def _contains_node(value, predicate) -> bool:
    return any(predicate(node) for node in _iter_nodes(value))


def _negative_int_expr(expr) -> bool:
    return (
        isinstance(expr, UnaryExpr)
        and expr.op == "-"
        and hasattr(expr.operand, "value")
        and isinstance(expr.operand.value, int)
    ) or (
        hasattr(expr, "value")
        and isinstance(expr.value, int)
        and expr.value < 0
    )


def _is_float_literal(expr) -> bool:
    return hasattr(expr, "value") and isinstance(getattr(expr, "value"), float)


def _is_int_literal(expr) -> bool:
    return hasattr(expr, "value") and isinstance(getattr(expr, "value"), int)


def _has_call_kwargs(node) -> bool:
    return isinstance(node, (CallExpr, CallValueExpr, MethodCallExpr)) and bool(getattr(node, "kwargs", {}))


def _has_kw_starred(node) -> bool:
    return isinstance(node, (CallExpr, CallValueExpr, MethodCallExpr)) and bool(getattr(node, "kw_starred", []))


def _contains_expr_fields(statement) -> bool:
    return isinstance(statement, (AssignStmt, AttributeAssignStmt, PrintStmt))


def _program_uses_imports(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, (ImportStmt, FromImportStmt)))


def _program_uses_nested_functions(program: Program) -> bool:
    def walk(statements: list[object], depth: int = 0) -> bool:
        for statement in statements:
            if isinstance(statement, FunctionDef):
                if depth:
                    return True
                if walk(statement.body, depth + 1):
                    return True
            elif isinstance(statement, ClassDef):
                for method in statement.methods:
                    if walk(method.body, depth + 1):
                        return True
            elif isinstance(statement, IfStmt):
                if walk(statement.body, depth) or walk(statement.orelse, depth):
                    return True
            elif isinstance(statement, WhileStmt):
                if walk(statement.body, depth) or walk(statement.orelse, depth):
                    return True
            elif isinstance(statement, ForStmt):
                if walk(statement.body, depth) or walk(statement.orelse, depth):
                    return True
            elif isinstance(statement, TryStmt):
                if walk(statement.body, depth) or walk(statement.orelse, depth) or walk(statement.finalbody, depth):
                    return True
                if any(walk(handler.body, depth) for handler in statement.handlers):
                    return True
            elif isinstance(statement, WithStmt):
                if walk(statement.body, depth):
                    return True
        return False

    from compiler.core.ast import IfStmt, WhileStmt  # local import avoids a long top-level import list

    return walk(program.body)


def _program_uses_unsupported_exception_features(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, TryStmt) and bool(node.orelse))


def _program_uses_negative_int_exponent(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, BinaryExpr) and node.op == "**" and _negative_int_expr(node.right),
    )


def _program_uses_mixed_numeric_ops(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, BinaryExpr)
        and node.op in {"//", "**"}
        and ((_is_float_literal(node.left) and _is_int_literal(node.right)) or (_is_int_literal(node.left) and _is_float_literal(node.right))),
    )


def _program_uses_call_kwargs_splats(program: Program) -> bool:
    return _contains_node(program, _has_kw_starred)


def _program_uses_walrus(program: Program) -> bool:
    return _contains_node(program, lambda node: type(node).__name__ == "NamedExpr")


def _program_uses_container_features(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(
            node,
            (
                ListExpr,
                TupleExpr,
                DictExpr,
                SetExpr,
                IndexExpr,
                IndexAssignStmt,
                ListCompExpr,
                SetCompExpr,
                DictCompExpr,
            ),
        )
        or (isinstance(node, CallExpr) and node.func_name in {"dict", "set", "list", "tuple"}),
    )


def _program_uses_container_literals(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, (ListExpr, TupleExpr, DictExpr, SetExpr)))


def _program_uses_container_indexing(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, IndexExpr))


def _program_uses_container_index_assign(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, IndexAssignStmt))


def _program_uses_container_comprehensions(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, (ListCompExpr, SetCompExpr, DictCompExpr)))


def _program_uses_container_builtin_calls(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, CallExpr) and node.func_name in {"dict", "set", "list", "tuple"},
    )


def _program_uses_lambdas(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, LambdaExpr))


def _program_uses_compare_chains(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, CompareChainExpr))


def _program_uses_object_features(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, (ClassDef, AttributeExpr, MethodCallExpr, AttributeAssignStmt)),
    )


def _program_uses_call_signature_features(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: (
            isinstance(node, FunctionDef)
            and (bool(node.defaults) or bool(node.kwonly_params) or node.vararg is not None or node.kwarg is not None)
        ) or _has_call_kwargs(node),
    )


def _program_uses_generators(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, (YieldExpr, YieldFromExpr, GeneratorExpr)))


def _program_uses_core_vm_only_features(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, (UnpackAssignStmt, DeleteStmt, GlobalStmt, NonlocalStmt, WithStmt)),
    )


def _program_uses_slicing(program: Program) -> bool:
    return _contains_node(program, lambda node: isinstance(node, SliceExpr))


def _program_uses_vm_only_builtin_calls(program: Program) -> bool:
    return _contains_node(
        program,
        lambda node: isinstance(node, CallExpr) and node.func_name in VM_ONLY_BUILTIN_CALLS,
    )
