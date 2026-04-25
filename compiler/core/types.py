from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValueType(str, Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "str"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    SET = "set"
    VOID = "void"
    UNKNOWN = "unknown"


@dataclass
class FunctionType:
    name: str
    param_names: list[str]
    param_types: list[ValueType]
    defaults_count: int = 0
    kwonly_names: list[str] = field(default_factory=list)
    kwonly_types: dict[str, ValueType] = field(default_factory=dict)
    kwonly_defaults: set[str] = field(default_factory=set)
    vararg_name: str | None = None
    kwarg_name: str | None = None
    return_type: ValueType = ValueType.UNKNOWN
    state: str = "unvisited"
    reachable: bool = False
    has_value_return: bool = False
    node: object | None = None
    local_types: dict[str, ValueType] = field(default_factory=dict)


def is_numeric(value_type: ValueType) -> bool:
    return value_type in (ValueType.INT, ValueType.FLOAT)


def can_truth_test(value_type: ValueType) -> bool:
    return value_type in (
        ValueType.BOOL,
        ValueType.INT,
        ValueType.FLOAT,
        ValueType.STRING,
        ValueType.LIST,
        ValueType.TUPLE,
        ValueType.DICT,
        ValueType.SET,
    )


def merge_types(left: ValueType, right: ValueType) -> ValueType | None:
    if left == ValueType.UNKNOWN:
        return right
    if right == ValueType.UNKNOWN:
        return left
    if left == right:
        return left
    if is_numeric(left) and is_numeric(right):
        if ValueType.FLOAT in (left, right):
            return ValueType.FLOAT
        return ValueType.INT
    return None


def c_type_name(value_type: ValueType) -> str:
    if value_type == ValueType.FLOAT:
        return "double"
    if value_type in (ValueType.INT, ValueType.BOOL):
        return "int"
    if value_type == ValueType.STRING:
        return "const char *"
    if value_type == ValueType.VOID:
        return "void"
    return "double"
