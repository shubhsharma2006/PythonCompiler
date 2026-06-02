import json
import tempfile
import unittest
from pathlib import Path

from compiler import execute_source
from compiler.differential import ExecutionOutcome, ProgramCase
from compiler.differential.generator import DifferentialProgramGenerator
from compiler.differential.normalize import compare_outcomes, normalize_result
from compiler.differential.reporting import write_mismatch_bundle
from compiler.differential.runner import run_curated_cases


class DifferentialTests(unittest.TestCase):
    def test_normalize_result_vm_success(self):
        result = execute_source("print(1)\n", filename="inline.py")
        outcome = normalize_result(result, "vm")
        self.assertEqual(outcome.status, "success")
        self.assertEqual(outcome.stdout.strip(), "1")
        self.assertIsNone(outcome.error_message)

    def test_compare_outcomes_ignores_workspace_specific_paths(self):
        vm = ExecutionOutcome(
            lane="vm",
            status="compile_error",
            stdout="",
            error_stage="compile",
            error_type="Codegen",
            error_message="program.c: gcc failed",
        )
        native = ExecutionOutcome(
            lane="native",
            status="compile_error",
            stdout="",
            error_stage="compile",
            error_type="Codegen",
            error_message="program.c: gcc failed",
        )
        matches, reasons = compare_outcomes(vm, native)
        self.assertTrue(matches)
        self.assertEqual(reasons, ())

    def test_generator_is_deterministic_by_seed(self):
        first = DifferentialProgramGenerator(7).generate_cases(5)
        second = DifferentialProgramGenerator(7).generate_cases(5)
        self.assertEqual([case.source for case in first], [case.source for case in second])
        self.assertEqual([case.case_id for case in first], [case.case_id for case in second])

    def test_write_mismatch_bundle_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case = ProgramCase(case_id="sample", name="Sample", source="print(1)\n")
            vm = ExecutionOutcome(lane="vm", status="success", stdout="1\n")
            native = ExecutionOutcome(lane="native", status="runtime_error", stdout="", error_stage="runtime", error_type="Runtime", error_message="boom")
            vm_result = execute_source("print(1)\n", filename="inline.py")
            native_result = execute_source("print(2)\n", filename="inline.py")
            bundle = write_mismatch_bundle(
                case=case,
                vm_outcome=vm,
                native_outcome=native,
                vm_result=vm_result,
                native_result=native_result,
                run_dir=Path(temp_dir),
                command="python3 -m compiler.differential run",
            )
            bundle_dir = Path(bundle.bundle_dir)
            self.assertTrue((bundle_dir / "source.py").exists())
            self.assertTrue((bundle_dir / "vm.json").exists())
            self.assertTrue((bundle_dir / "native.json").exists())
            self.assertTrue((bundle_dir / "meta.json").exists())

    def test_run_curated_cases_writes_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary, results = run_curated_cases(
                case_ids={"arithmetic_scalars", "container_truthiness"},
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="python3 -m compiler.differential run --case arithmetic_scalars --case container_truthiness",
            )
            self.assertEqual(summary.total_cases, 2)
            self.assertEqual(len(results), 2)
            summary_dir = Path(temp_dir) / summary.run_id
            self.assertTrue((summary_dir / "summary.json").exists())
            payload = json.loads((summary_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertIn("summary", payload)
            self.assertIn("cases", payload)


if __name__ == "__main__":
    unittest.main()
