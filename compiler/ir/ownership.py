from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from compiler.core.types import ValueType


class OwnerKind(str, Enum):
    OWNED = "owned"
    BORROWED = "borrowed"


@dataclass
class SSAValueInfo:
    name: str
    value_type: ValueType
    owner_kind: OwnerKind = OwnerKind.OWNED
    refcounted: bool = False
    cleanup_required: bool = False
    last_use: str | None = None


def default_value_info(name: str, value_type: ValueType, owner_kind: OwnerKind) -> SSAValueInfo:
    refcounted = value_type == ValueType.STRING
    return SSAValueInfo(
        name=name,
        value_type=value_type,
        owner_kind=owner_kind,
        refcounted=refcounted,
        cleanup_required=refcounted and owner_kind == OwnerKind.OWNED,
    )