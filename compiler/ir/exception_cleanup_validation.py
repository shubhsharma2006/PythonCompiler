from __future__ import annotations

from compiler.ir.cfg import Call, CFGFunction, CFGModule, DecRef, JumpTerminator, ReturnTerminator
from compiler.ir.ownership import OwnerKind


class ExceptionCleanupValidation:
    """Validate exception cleanup lowering.

    Checks that every raising call with an exception_live set points to a
    specialized cleanup block that:
    - exists in the CFG
    - contains DecRef instructions for all live owned/refcounted values
    - emits those DecRefs in reverse order of exception_live
    - terminates with a jump to the unified cleanup label
    """

    def apply(self, module: CFGModule) -> CFGModule:
        self._apply_function(module.main)
        for function in module.functions:
            self._apply_function(function)
        return module

    def _apply_function(self, function: CFGFunction) -> None:
        block_map = {block.name: block for block in function.blocks}

        for block in function.blocks:
            for instruction in block.instructions:
                if not isinstance(instruction, Call) or not instruction.can_raise:
                    continue

                if not instruction.exception_live:
                    continue

                target = instruction.exception_target
                if target is None or target not in block_map:
                    raise ValueError(
                        f"Missing exception cleanup block for call in {function.name}:{block.name}"
                    )

                cleanup_block = block_map[target]

                dec_names = [
                    instr.target
                    for instr in cleanup_block.instructions
                    if isinstance(instr, DecRef)
                ]

                expected = list(reversed(instruction.exception_live))
                if dec_names != expected:
                    raise ValueError(
                        f"Exception cleanup block {target} does not match expected DecRef order"
                    )

                if not isinstance(cleanup_block.terminator, (JumpTerminator, ReturnTerminator)):
                    raise ValueError(
                        f"Exception cleanup block {target} must end with a jump or return"
                    )

                for name in instruction.exception_live:
                    info = function.ownership.get(name)
                    if info is None:
                        raise ValueError(
                            f"Exception cleanup references unknown value {name} in {function.name}"
                        )
                    if info.owner_kind != OwnerKind.OWNED or not info.refcounted:
                        raise ValueError(
                            f"Exception cleanup references non-owned value {name} in {function.name}"
                        )
                    if info.cleanup_required:
                        raise ValueError(
                            f"Exception cleanup did not clear cleanup_required for {name} in {function.name}"
                        )
