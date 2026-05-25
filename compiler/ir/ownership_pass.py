from __future__ import annotations

from collections import defaultdict

from compiler.core.types import ValueType
from compiler.ir.analysis import compute_post_dominators, immediate_post_dominators, rebuild_edges
from compiler.ir.cfg import (
    Assign,
    BasicBlock,
    BinaryOp,
    BranchTerminator,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    JumpTerminator,
    LoadConst,
    Print,
    ReturnTerminator,
    UnaryOp,
)
from compiler.ir.ownership import OwnerKind


class OwnershipDecrefPlacement:
    def apply(self, module: CFGModule) -> CFGModule:
        self._apply_function(module.main)
        for function in module.functions:
            self._apply_function(function)
        return module

    def _apply_function(self, function: CFGFunction) -> None:
        rebuild_edges(function)
        postdoms = compute_post_dominators(function)
        idoms = immediate_post_dominators(function)
        depths = self._compute_postdom_depths(idoms)
        uses = self._collect_uses(function)

        for name, info in function.ownership.items():
            if info.owner_kind != OwnerKind.OWNED or not info.refcounted:
                continue
            if not info.cleanup_required:
                continue

            use_blocks = uses.get(name)
            if not use_blocks:
                continue

            placement = self._common_postdom(use_blocks, postdoms, depths)
            if placement is None:
                continue

            block = next((b for b in function.blocks if b.name == placement), None)
            if block is None:
                continue

            if any(isinstance(instr, DecRef) and instr.target == name for instr in block.instructions):
                continue

            block.instructions.append(DecRef(name))
            info.cleanup_required = False
            info.last_use = placement

    @staticmethod
    def _collect_uses(function: CFGFunction) -> dict[str, set[str]]:
        uses: dict[str, set[str]] = defaultdict(set)
        for block in function.blocks:
            for instruction in block.instructions:
                for operand in _instruction_uses(instruction):
                    uses[operand].add(block.name)
            terminator = block.terminator
            if isinstance(terminator, BranchTerminator):
                uses[terminator.condition].add(block.name)
            elif isinstance(terminator, ReturnTerminator) and terminator.value is not None:
                uses[terminator.value].add(block.name)
        return uses

    @staticmethod
    def _common_postdom(use_blocks: set[str], postdoms: dict[str, set[str]], depths: dict[str, int]) -> str | None:
        if not use_blocks:
            return None
        common = None
        for block in use_blocks:
            doms = postdoms.get(block)
            if doms is None:
                continue
            common = doms if common is None else common & doms
        if not common:
            return None
        return max(common, key=lambda name: depths.get(name, 0))

    @staticmethod
    def _compute_postdom_depths(idoms: dict[str, str | None]) -> dict[str, int]:
        depth: dict[str, int] = {}
        visiting: set[str] = set()

        def walk(node: str) -> int:
            if node in depth:
                return depth[node]
            if node in visiting:
                depth[node] = 0
                return depth[node]
            visiting.add(node)
            parent = idoms.get(node)
            depth[node] = 0 if parent is None else walk(parent) + 1
            visiting.discard(node)
            return depth[node]

        for node in idoms:
            walk(node)
        return depth


def _instruction_uses(instruction) -> list[str]:
    if isinstance(instruction, Assign):
        return [instruction.source]
    if isinstance(instruction, BinaryOp):
        return [instruction.left, instruction.right]
    if isinstance(instruction, UnaryOp):
        return [instruction.operand]
    if isinstance(instruction, Call):
        return list(instruction.args)
    if isinstance(instruction, Print):
        return [instruction.value]
    if isinstance(instruction, DecRef):
        return [instruction.target]
    return []
