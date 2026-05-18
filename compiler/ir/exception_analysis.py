from __future__ import annotations

from collections import defaultdict

from compiler.ir.analysis import rebuild_edges
from compiler.ir.cfg import (
    Assign,
    BinaryOp,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    LoadConst,
    Print,
    UnaryOp,
)
from compiler.ir.ownership import OwnerKind


class ExceptionalLivenessAnalysis:
    def apply(self, module: CFGModule) -> CFGModule:
        self._apply_function(module.main)
        for function in module.functions:
            self._apply_function(function)
        return module

    def _apply_function(self, function: CFGFunction) -> None:
        rebuild_edges(function)
        owned_refcounted = {
            name
            for name, info in function.ownership.items()
            if info.owner_kind == OwnerKind.OWNED and info.refcounted
        }

        alive_in: dict[str, set[str]] = {block.name: set() for block in function.blocks}
        alive_out: dict[str, set[str]] = {block.name: set() for block in function.blocks}

        changed = True
        while changed:
            changed = False
            for block in function.blocks:
                incoming = set()
                for pred in block.predecessors:
                    incoming |= alive_out.get(pred, set())
                if incoming != alive_in[block.name]:
                    alive_in[block.name] = incoming
                    changed = True

                current = set(incoming)
                for instruction in block.instructions:
                    current = _update_alive_set(current, instruction, owned_refcounted)

                if current != alive_out[block.name]:
                    alive_out[block.name] = current
                    changed = True

        for block in function.blocks:
            current = set(alive_in[block.name])
            for instruction in block.instructions:
                if isinstance(instruction, Call) and instruction.can_raise:
                    instruction.exception_live = sorted(current)
                current = _update_alive_set(current, instruction, owned_refcounted)


def _instruction_defines(instruction) -> set[str]:
    if isinstance(instruction, (LoadConst, Assign, BinaryOp, UnaryOp)):
        return {instruction.target}
    if isinstance(instruction, Call) and instruction.target is not None:
        return {instruction.target}
    if isinstance(instruction, DecRef):
        return {instruction.target}
    return set()


def _instruction_uses(instruction) -> set[str]:
    if isinstance(instruction, Assign):
        return {instruction.source}
    if isinstance(instruction, BinaryOp):
        return {instruction.left, instruction.right}
    if isinstance(instruction, UnaryOp):
        return {instruction.operand}
    if isinstance(instruction, Call):
        return set(instruction.args)
    if isinstance(instruction, Print):
        return {instruction.value}
    if isinstance(instruction, DecRef):
        return {instruction.target}
    return set()


def _update_alive_set(current: set[str], instruction, owned_refcounted: set[str]) -> set[str]:
    next_alive = set(current)
    if isinstance(instruction, DecRef):
        if instruction.target in next_alive:
            next_alive.remove(instruction.target)
        return next_alive

    defs = _instruction_defines(instruction)
    for name in defs:
        if name in owned_refcounted:
            next_alive.add(name)
    return next_alive