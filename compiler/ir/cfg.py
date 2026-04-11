from __future__ import annotations

from dataclasses import dataclass, field

from compiler.core.types import FunctionType, ValueType


@dataclass
class IRInstruction:
    pass


@dataclass
class LoadConst(IRInstruction):
    target: str
    value: object
    value_type: ValueType


@dataclass
class Assign(IRInstruction):
    target: str
    source: str


@dataclass
class BinaryOp(IRInstruction):
    target: str
    op: str
    left: str
    right: str
    value_type: ValueType


@dataclass
class UnaryOp(IRInstruction):
    target: str
    op: str
    operand: str
    value_type: ValueType


@dataclass
class Call(IRInstruction):
    target: str | None
    func_name: str
    args: list[str]
    value_type: ValueType


@dataclass
class Print(IRInstruction):
    value: str
    value_type: ValueType
    newline: bool = True


@dataclass
class Phi(IRInstruction):
    target: str
    variable: str
    inputs: dict[str, str]
    value_type: ValueType


@dataclass
class Terminator:
    pass


@dataclass
class JumpTerminator(Terminator):
    target: str


@dataclass
class BranchTerminator(Terminator):
    condition: str
    true_target: str
    false_target: str


@dataclass
class ReturnTerminator(Terminator):
    value: str | None


@dataclass
class BasicBlock:
    name: str
    phis: list[Phi] = field(default_factory=list)
    instructions: list[IRInstruction] = field(default_factory=list)
    terminator: Terminator | None = None
    predecessors: set[str] = field(default_factory=set)
    successors: set[str] = field(default_factory=set)


@dataclass
class CFGFunction:
    name: str
    params: list[tuple[str, ValueType]]
    return_type: ValueType
    blocks: list[BasicBlock] = field(default_factory=list)
    entry_block: str = ""
    locals: dict[str, ValueType] = field(default_factory=dict)
    globals_read: set[str] = field(default_factory=set)


@dataclass
class CFGModule:
    globals: dict[str, ValueType]
    functions: list[CFGFunction]
    main: CFGFunction
    function_types: dict[str, FunctionType]
