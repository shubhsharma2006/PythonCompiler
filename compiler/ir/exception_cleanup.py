from __future__ import annotations

from typing import List

from compiler.ir.analysis import rebuild_edges
from compiler.ir.cfg import (
    BasicBlock,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    JumpTerminator,
    ReturnTerminator,
)


class ExceptionCleanupLowering:
    """Lower exception_live metadata into specialized cleanup blocks.

    For each Call that can raise and has an exception_live set, create a
    dedicated cleanup basic block named <caller_block>_exc_cleanup_<n> that
    emits DecRef instructions for the listed names in reverse order and then
    jumps to the unified "cleanup" epilogue. Mark each value's ownership
    cleanup_required = False so the unified epilogue won't double-cleanup.
    """

    def apply(self, module: CFGModule) -> CFGModule:
        self._apply_function(module.main)
        for function in module.functions:
            self._apply_function(function)
        return module

    def _apply_function(self, function: CFGFunction) -> None:
        rebuild_edges(function)

        new_blocks: List[BasicBlock] = []
        counter = 0
        cleanup_cache: dict[tuple[str, ...], str] = {}
        block_names = {block.name for block in function.blocks}

        # We'll build a new blocks list by inserting generated cleanup blocks
        # immediately after the block that contains the raising call to keep
        # block ordering simple and predictable.
        for block in list(function.blocks):
            new_blocks.append(block)
            for instr in list(block.instructions):
                if isinstance(instr, Call) and instr.can_raise and instr.exception_live:
                    # Only synthesize a specialized cleanup block when we have
                    # owned/refcounted values to destroy.
                    if not instr.exception_live:
                        continue

                    original_target = instr.exception_target
                    key = tuple(instr.exception_live)
                    existing = cleanup_cache.get(key)
                    if existing is not None:
                        instr.exception_target = existing
                        for name in key:
                            info = function.ownership.get(name)
                            if info is not None:
                                info.cleanup_required = False
                        continue

                    new_name = f"{block.name}_exc_cleanup_{counter}"
                    counter += 1

                    cleanup_block = BasicBlock(name=new_name)

                    # Emit DecRef in reverse order to follow reverse construction
                    # semantics (destroy last-created first).
                    for name in reversed(instr.exception_live):
                        cleanup_block.instructions.append(DecRef(name))
                        # Mark ownership as cleaned up so unified epilogue skips it.
                        info = function.ownership.get(name)
                        if info is not None:
                            info.cleanup_required = False

                    if original_target and original_target in block_names:
                        cleanup_block.terminator = JumpTerminator(target=original_target)
                    else:
                        cleanup_block.terminator = ReturnTerminator(None)

                    new_blocks.append(cleanup_block)

                    # Point the call's exception target to the specialized block.
                    instr.exception_target = new_name
                    cleanup_cache[key] = new_name

        function.blocks = new_blocks
        rebuild_edges(function)
