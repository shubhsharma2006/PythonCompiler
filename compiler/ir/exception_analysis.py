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
        blocks = {block.name: block for block in function.blocks}
        live_in: dict[str, set[str]] = {name: set() for name in blocks}
        live_out: dict[str, set[str]] = {name: set() for name in blocks}

        changed = True
        while changed:
            changed = False
            for block in reversed(function.blocks):
                out = set()
                for succ in block.successors:
                    out |= live_in.get(succ, set())
                if out != live_out[block.name]:
                    live_out[block.name] = out
                    changed = True

                current = set(out)
                for instruction in reversed(block.instructions):
                    defs = _instruction_defines(instruction)
                    uses = _instruction_uses(instruction)
                    current -= defs
                    current |= uses
                if current != live_in[block.name]:
                    live_in[block.name] = current
                    changed = True

        owned_refcounted = {
            name
            for name, info in function.ownership.items()
            if info.owner_kind == OwnerKind.OWNED and info.refcounted
        }

        for block in function.blocks:
            current = set(live_out[block.name])
            for instruction in reversed(block.instructions):
                if isinstance(instruction, Call) and instruction.can_raise:
                    instruction.exception_live = sorted(current & owned_refcounted)
                defs = _instruction_defines(instruction)
                uses = _instruction_uses(instruction)
                current -= defs
                current |= uses


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
    if isinstance(instruction, DecRef):
        return {instruction.target}
    return set()