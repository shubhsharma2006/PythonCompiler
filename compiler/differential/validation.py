from __future__ import annotations

from dataclasses import dataclass

from compiler.core.ast import (
    AttributeAssignStmt,
    AttributeExpr,
    CallExpr,
    CallValueExpr,
    ClassDef,
    CompareChainExpr,
    ConstantExpr,
    DeleteStmt,
    DictCompExpr,
    DictExpr,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GeneratorExpr,
    GlobalStmt,
    ImportStmt,
    IndexExpr,
    KwStarredExpr,
    LambdaExpr,
    ListCompExpr,
    MethodCallExpr,
    NamedExpr,
    NonlocalStmt,
    RaiseStmt,
    SetCompExpr,
    SetExpr,
    SliceExpr,
    StarUnpackAssignStmt,
    StarredExpr,
    TryStmt,
    UnpackAssignStmt,
    WithStmt,
    YieldExpr,
    YieldFromExpr,
)
from compiler.pipeline.analyze import _analyze_source
from compiler.pipeline.feature_gates import _iter_nodes

from .corpus import iter_curated_cases
from .model import ProgramCase
from .profile import DifferentialProfile, current_native_profile


@dataclass(frozen=True)
class ProfileValidation:
    status: str
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "comparable"


def validate_curated_cases(profile: DifferentialProfile | None = None) -> list[tuple[ProgramCase, ProfileValidation]]:
    active_profile = profile or current_native_profile()
    return [(case, validate_case(case, active_profile)) for case in iter_curated_cases()]


def validate_case(case: ProgramCase, profile: DifferentialProfile | None = None) -> ProfileValidation:
    active_profile = profile or current_native_profile()
    errors: list[str] = []

    unknown_tags = sorted(set(case.tags) - set(active_profile.features))
    if unknown_tags:
        errors.append(f"unknown feature tags: {', '.join(unknown_tags)}")

    result = _analyze_source(case.source, filename=case.filename)
    if not result.success or result.program is None:
        rendered = result.errors.render().strip()
        errors.append(f"source does not analyze cleanly: {rendered or 'unknown analysis failure'}")
        return _validation(errors)

    for message in _profile_violations(result.program):
        if message not in errors:
            errors.append(message)

    return _validation(errors)


def _validation(errors: list[str]) -> ProfileValidation:
    if errors:
        return ProfileValidation(status="profile_violation", errors=tuple(errors))
    return ProfileValidation(status="comparable")


def _profile_violations(program) -> list[str]:
    errors: list[str] = []
    function_depth = 0

    def add(message: str) -> None:
        if message not in errors:
            errors.append(message)

    for node in _iter_nodes(program):
        if isinstance(node, (ImportStmt, FromImportStmt)):
            add("imports are outside the native differential profile")
        elif isinstance(node, (ClassDef, AttributeExpr, AttributeAssignStmt, MethodCallExpr)):
            add("classes and object features are outside the native differential profile")
        elif isinstance(node, (YieldExpr, YieldFromExpr, GeneratorExpr)):
            add("generators are outside the native differential profile")
        elif isinstance(node, (DictExpr, DictCompExpr)):
            add("dicts are outside the native differential profile")
        elif isinstance(node, (SetExpr, SetCompExpr)):
            add("sets are outside the native differential profile")
        elif isinstance(node, (ListCompExpr,)):
            add("comprehensions are outside the native differential profile")
        elif isinstance(node, (LambdaExpr,)):
            add("lambda expressions are outside the native differential profile")
        elif isinstance(node, (UnpackAssignStmt, StarUnpackAssignStmt)):
            add("unpacking assignment is outside the native differential profile")
        elif isinstance(node, DeleteStmt):
            add("delete statements are outside the native differential profile")
        elif isinstance(node, (GlobalStmt, NonlocalStmt)):
            add("global/nonlocal statements are outside the native differential profile")
        elif isinstance(node, WithStmt):
            add("with statements are outside the native differential profile")
        elif isinstance(node, NamedExpr):
            add("walrus expressions are outside the native differential profile")
        elif isinstance(node, CompareChainExpr):
            add("comparison chaining is outside the native differential profile")
        elif isinstance(node, TryStmt) and node.orelse:
            add("try/except else is outside the native differential profile")
        elif isinstance(node, RaiseStmt) and node.cause is not None:
            add("raise from is outside the native differential profile")
        elif isinstance(node, ForStmt) and not _is_range_call(node.iterator):
            add("only for loops over range(...) are inside the native differential profile")
        elif isinstance(node, FunctionDef):
            if function_depth:
                add("nested functions are outside the native differential profile")
            if node.defaults or node.kwonly_params or node.vararg is not None or node.kwarg is not None:
                add("default, keyword-only, varargs, and kwargs function signatures are outside the native differential profile")
            function_depth += 1
            function_depth -= 1
        elif isinstance(node, (CallExpr, CallValueExpr, MethodCallExpr)):
            if getattr(node, "kwargs", {}):
                add("keyword arguments are outside the native differential profile")
            if getattr(node, "kw_starred", []):
                add("**kwargs splats are outside the native differential profile")
            if any(isinstance(arg, StarredExpr) for arg in getattr(node, "args", [])):
                add("*args splats are outside the native differential profile")
            if isinstance(node, CallExpr) and node.func_name in {"list", "tuple", "dict", "set", "ascii"}:
                add(f"{node.func_name}() is outside the native differential profile")
        elif isinstance(node, KwStarredExpr):
            add("**kwargs splats are outside the native differential profile")
        elif isinstance(node, StarredExpr):
            add("*args splats are outside the native differential profile")
        elif isinstance(node, IndexExpr) and isinstance(node.index, SliceExpr):
            if not _slice_step_is_supported(node.index):
                add("dynamic or zero slice steps are outside the native differential profile")

    if _has_nested_function(program.body):
        add("nested functions are outside the native differential profile")
    return errors


def _has_nested_function(statements: list[object], depth: int = 0) -> bool:
    for statement in statements:
        if isinstance(statement, FunctionDef):
            if depth:
                return True
            if _has_nested_function(statement.body, depth + 1):
                return True
        for attr in ("body", "orelse", "finalbody"):
            child = getattr(statement, attr, None)
            if isinstance(child, list) and _has_nested_function(child, depth):
                return True
        handlers = getattr(statement, "handlers", None)
        if handlers and any(_has_nested_function(handler.body, depth) for handler in handlers):
            return True
    return False


def _is_range_call(expr) -> bool:
    return isinstance(expr, CallExpr) and expr.func_name == "range"


def _slice_step_is_supported(slice_expr: SliceExpr) -> bool:
    if slice_expr.step is None:
        return True
    step = slice_expr.step
    if isinstance(step, ConstantExpr) and isinstance(step.value, int):
        return step.value != 0
    return False
