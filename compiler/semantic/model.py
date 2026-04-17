from __future__ import annotations

from dataclasses import dataclass, field

from compiler.core.ast import CallExpr
from compiler.core.types import FunctionType, ValueType


class Scope:
    def __init__(self, parent: Scope | None = None):
        self.parent = parent
        self.values: dict[str, ValueType] = {}
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def define(self, name: str, value_type: ValueType) -> None:
        self.values[name] = value_type

    def declare_global(self, name: str) -> None:
        self.global_names.add(name)

    def declare_nonlocal(self, name: str) -> None:
        self.nonlocal_names.add(name)

    def lookup(self, name: str) -> ValueType | None:
        if name in self.global_names:
            root = self
            while root.parent is not None:
                root = root.parent
            return root.values.get(name)
        if name in self.nonlocal_names:
            scope = self.parent
            while scope is not None and scope.parent is not None:
                if name in scope.values:
                    return scope.values[name]
                scope = scope.parent
            return None
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None

    def lookup_enclosing(self, name: str) -> ValueType | None:
        scope = self.parent
        while scope is not None and scope.parent is not None:
            if name in scope.values:
                return scope.values[name]
            scope = scope.parent
        return None

    def root(self) -> Scope:
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope


@dataclass
class SymbolTable:
    global_scope: Scope = field(default_factory=Scope)
    functions: dict[str, FunctionType] = field(default_factory=dict)


@dataclass
class SemanticModel:
    globals: dict[str, ValueType]
    functions: dict[str, FunctionType]
    expr_types: dict[int, ValueType]

    def expr_type(self, expr) -> ValueType:
        if isinstance(expr, CallExpr) and expr.func_name in self.functions:
            value_type = self.expr_types.get(id(expr), ValueType.UNKNOWN)
            if value_type == ValueType.UNKNOWN:
                return self.functions[expr.func_name].return_type
            return value_type
        return self.expr_types.get(id(expr), ValueType.UNKNOWN)
