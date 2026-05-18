import os
import tempfile
import unittest

from compiler import compile_source
from compiler.core.types import ValueType
from compiler.ir import (
    BasicBlock,
    Call,
    CFGFunction,
    CFGModule,
    DecRef,
    JumpTerminator,
    LoadConst,
    Print,
    ReturnTerminator,
    rebuild_edges,
)
from compiler.ir.exception_analysis import ExceptionalLivenessAnalysis
from compiler.ir.exception_cleanup import ExceptionCleanupLowering
from compiler.ir.exception_cleanup_validation import ExceptionCleanupValidation
from compiler.ir.ownership import OwnerKind, default_value_info


class ExceptionCleanupTests(unittest.TestCase):
    def compile_program(self, source: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(source, filename="inline.py", output=output_path)
            self.assertTrue(result.success, result.errors.render())
            return result.c_code

    def _make_module(self, blocks, ownership, locals_map=None):
        function = CFGFunction(
            name="main",
            params=[],
            return_type=ValueType.VOID,
            blocks=blocks,
            entry_block=blocks[0].name,
            locals=locals_map or {},
            ownership=ownership,
        )
        return CFGModule(globals={}, functions=[], main=function, function_types={})

    def test_exception_cleanup_lowering_creates_cleanup_block(self):
        ownership = {
            "a": default_value_info("a", ValueType.STRING, OwnerKind.OWNED),
            "b": default_value_info("b", ValueType.STRING, OwnerKind.OWNED),
        }

        entry = BasicBlock(name="entry")
        entry.instructions = [
            LoadConst("a", "hello", ValueType.STRING),
            LoadConst("b", "world", ValueType.STRING),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["a"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
                exception_live=["a", "b"],
            ),
        ]
        entry.terminator = ReturnTerminator(None)

        module = self._make_module(
            [entry],
            ownership,
            locals_map={"a": ValueType.STRING, "b": ValueType.STRING},
        )

        module = ExceptionCleanupLowering().apply(module)
        module = ExceptionCleanupValidation().apply(module)

        blocks = {block.name: block for block in module.main.blocks}
        cleanup_block = blocks.get("entry_exc_cleanup_0")
        self.assertIsNotNone(cleanup_block)

        dec_targets = [
            instr.target for instr in cleanup_block.instructions if isinstance(instr, DecRef)
        ]
        self.assertEqual(dec_targets, ["b", "a"])

        self.assertIsNotNone(cleanup_block.terminator)

        self.assertFalse(module.main.ownership["a"].cleanup_required)
        self.assertFalse(module.main.ownership["b"].cleanup_required)

    def test_exception_liveness_includes_values_used_after_call(self):
        ownership = {
            "first": default_value_info("first", ValueType.STRING, OwnerKind.OWNED),
            "second": default_value_info("second", ValueType.STRING, OwnerKind.OWNED),
        }

        entry = BasicBlock(name="entry")
        entry.instructions = [
            LoadConst("first", "alpha", ValueType.STRING),
            LoadConst("second", "beta", ValueType.STRING),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["second"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
            ),
            Print("first", ValueType.STRING),
            Print("second", ValueType.STRING),
        ]
        entry.terminator = ReturnTerminator(None)

        module = self._make_module(
            [entry],
            ownership,
            locals_map={"first": ValueType.STRING, "second": ValueType.STRING},
        )

        module = ExceptionalLivenessAnalysis().apply(module)
        call = next(instr for instr in module.main.blocks[0].instructions if isinstance(instr, Call))
        self.assertEqual(set(call.exception_live), {"first", "second"})

        module = ExceptionCleanupLowering().apply(module)
        module = ExceptionCleanupValidation().apply(module)

    def test_exception_liveness_captures_unread_values_before_raise(self):
        ownership = {
            "temp": default_value_info("temp", ValueType.STRING, OwnerKind.OWNED),
        }

        entry = BasicBlock(name="entry")
        entry.instructions = [
            LoadConst("temp", "omega", ValueType.STRING),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["temp"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
            ),
            LoadConst("unused", 1, ValueType.INT),
        ]
        entry.terminator = ReturnTerminator(None)

        module = self._make_module(
            [entry],
            ownership,
            locals_map={"temp": ValueType.STRING, "unused": ValueType.INT},
        )

        module = ExceptionalLivenessAnalysis().apply(module)
        call = next(instr for instr in module.main.blocks[0].instructions if isinstance(instr, Call))
        self.assertEqual(call.exception_live, ["temp"])

        module = ExceptionCleanupLowering().apply(module)
        module = ExceptionCleanupValidation().apply(module)

    def test_exception_cleanup_merges_identical_live_sets(self):
        ownership = {
            "x": default_value_info("x", ValueType.STRING, OwnerKind.OWNED),
        }

        entry = BasicBlock(name="entry")
        entry.instructions = [
            LoadConst("x", "merge", ValueType.STRING),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["x"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
                exception_live=["x"],
            ),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["x"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
                exception_live=["x"],
            ),
        ]
        entry.terminator = ReturnTerminator(None)

        module = self._make_module(
            [entry],
            ownership,
            locals_map={"x": ValueType.STRING},
        )

        module = ExceptionCleanupLowering().apply(module)
        module = ExceptionCleanupValidation().apply(module)

        cleanup_blocks = [
            block for block in module.main.blocks if block.name.endswith("_exc_cleanup_0")
        ]
        self.assertEqual(len(cleanup_blocks), 1)
        calls = [instr for instr in entry.instructions if isinstance(instr, Call)]
        self.assertTrue(calls[0].exception_target)
        self.assertEqual(calls[0].exception_target, calls[1].exception_target)

    def test_native_division_by_zero_emits_error_check(self):
        c_code = self.compile_program(
            "x = 1\n"
            "y = 0\n"
            "z = x // y\n"
            "print(z)\n"
        )
        self.assertIn("py_floor_div_int", c_code)
        self.assertIn("if (py_error_occurred()) goto cleanup;", c_code)

    def test_exceptional_successor_added_for_raising_call(self):
        ownership = {
            "msg": default_value_info("msg", ValueType.STRING, OwnerKind.OWNED),
        }
        entry = BasicBlock(name="entry")
        entry.instructions = [
            LoadConst("msg", "boom", ValueType.STRING),
            Call(
                target=None,
                func_name="maybe_raise",
                args=["msg"],
                value_type=ValueType.VOID,
                can_raise=True,
                exception_target="cleanup",
                exception_live=["msg"],
            ),
        ]
        entry.terminator = ReturnTerminator(None)

        cleanup = BasicBlock(name="cleanup")
        cleanup.terminator = ReturnTerminator(None)

        module = self._make_module(
            [entry, cleanup],
            ownership,
            locals_map={"msg": ValueType.STRING},
        )

        rebuild_edges(module.main)
        self.assertIn("cleanup", entry.exceptional_successors)
        self.assertIn("entry", cleanup.exceptional_predecessors)


if __name__ == "__main__":
    unittest.main()