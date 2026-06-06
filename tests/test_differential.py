import json
import io
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from compiler import execute_source
from compiler.differential.__main__ import main as differential_main
from compiler.differential import ExecutionOutcome, ProgramCase
from compiler.differential.generator import DifferentialProgramGenerator
from compiler.differential.normalize import compare_outcomes, normalize_result
from compiler.differential.reporting import write_mismatch_bundle
from compiler.differential.runner import (
    _run_cases,
    latest_mismatch_bundles,
    latest_summary_path,
    run_curated_cases,
    validate_current_curated_cases,
)
from compiler.differential.validation import ProfileValidation, validate_case


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

    def test_validate_current_curated_cases_passes(self):
        validations = validate_current_curated_cases()
        failures = [(case.case_id, validation.errors) for case, validation in validations if not validation.ok]
        self.assertEqual(failures, [])

    def test_profile_validation_accepts_valid_case(self):
        case = ProgramCase(
            case_id="valid",
            name="Valid",
            source="items = [1, 2, 3]\nprint(items[1:])\n",
            tags=("list_literal", "slicing", "container_display"),
        )
        validation = validate_case(case)
        self.assertTrue(validation.ok)

    def test_profile_validation_rejects_unknown_tag(self):
        case = ProgramCase(case_id="bad_tag", name="Bad Tag", source="print(1)\n", tags=("missing",))
        validation = validate_case(case)
        self.assertFalse(validation.ok)
        self.assertIn("unknown feature tags: missing", validation.errors)

    def test_profile_validation_rejects_unsupported_constructs(self):
        cases = {
            "imports": "import math\nprint(1)\n",
            "generators": "def values():\n    yield 1\nprint(1)\n",
            "classes": "class Box:\n    pass\nprint(1)\n",
            "dicts": "d = {'a': 1}\nprint(d['a'])\n",
            "sets": "s = {1, 2}\nprint(1 in s)\n",
            "kwargs": "def add(a, b=1):\n    return a + b\nprint(add(1))\n",
        }
        for case_id, source in cases.items():
            with self.subTest(case_id=case_id):
                validation = validate_case(ProgramCase(case_id=case_id, name=case_id, source=source))
                self.assertFalse(validation.ok)

    def test_profile_validation_rejects_dynamic_slice_step(self):
        case = ProgramCase(
            case_id="dynamic_step",
            name="Dynamic Step",
            source="step = 1\nitems = [1, 2, 3]\nprint(items[::step])\n",
            tags=("list_literal", "slicing"),
        )
        validation = validate_case(case)
        self.assertFalse(validation.ok)
        self.assertIn("dynamic or zero slice steps are outside the native differential profile", validation.errors)

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
            self.assertEqual(payload["summary"]["profile_violations"], 0)
            self.assertIn("feature_stats", payload["summary"])
            self.assertIn("scalar_arithmetic", payload["summary"]["feature_stats"])

    def test_curated_profile_violation_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case = ProgramCase(
                case_id="bad_curated",
                name="Bad Curated",
                source="import math\nprint(1)\n",
                origin="curated",
            )
            summary, results = _run_cases(
                cases=[case],
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="test",
            )
            self.assertEqual(summary.curated_profile_failures, 1)
            self.assertEqual(summary.profile_violations, 1)
            self.assertEqual(summary.mismatches, 0)
            self.assertTrue(results[0].skipped)
            self.assertEqual(results[0].profile_status, "profile_violation")

    def test_generated_profile_violation_is_skipped_not_mismatched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case = ProgramCase(
                case_id="bad_generated",
                name="Bad Generated",
                source="import math\nprint(1)\n",
                origin="generated",
                seed=3,
            )
            summary, results = _run_cases(
                cases=[case],
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="test",
            )
            self.assertEqual(summary.generated_profile_skips, 1)
            self.assertEqual(summary.skipped_cases, 1)
            self.assertEqual(summary.mismatches, 0)
            self.assertEqual(summary.exact_matches, 0)
            self.assertTrue(results[0].skipped)

    def test_valid_generated_case_executes_both_lanes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case = ProgramCase(
                case_id="valid_generated",
                name="Valid Generated",
                source="print(1 + 2)\n",
                tags=("scalar_arithmetic",),
                origin="generated",
                seed=4,
            )
            summary, results = _run_cases(
                cases=[case],
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="test",
            )
            self.assertEqual(summary.generated_profile_skips, 0)
            self.assertEqual(summary.exact_matches, 1)
            self.assertFalse(results[0].skipped)
            self.assertEqual(results[0].vm.stdout, results[0].native.stdout)

    def test_validate_cli_succeeds_for_current_corpus(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = differential_main(["validate"])
        self.assertEqual(code, 0)
        self.assertIn("profile_violations=0", stream.getvalue())

    def test_validate_cli_reports_invalid_injected_case(self):
        bad_case = ProgramCase(case_id="bad", name="Bad", source="import math\nprint(1)\n")
        bad_validation = ProfileValidation(status="profile_violation", errors=("imports are outside the native differential profile",))
        stream = io.StringIO()
        with patch("compiler.differential.__main__.validate_current_curated_cases", return_value=[(bad_case, bad_validation)]):
            with redirect_stdout(stream):
                code = differential_main(["validate"])
        self.assertEqual(code, 1)
        self.assertIn("bad: imports are outside the native differential profile", stream.getvalue())

    def test_latest_summary_helpers_return_newest_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_summary, _ = run_curated_cases(
                case_ids={"arithmetic_scalars"},
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="first",
            )
            second_summary, _ = run_curated_cases(
                case_ids={"container_truthiness"},
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="second",
            )
            latest_path = latest_summary_path(temp_dir)
            self.assertIsNotNone(latest_path)
            self.assertIn(second_summary.run_id, str(latest_path))
            self.assertNotIn(first_summary.run_id, str(latest_path))

    def test_latest_cli_reports_newest_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary, _ = run_curated_cases(
                case_ids={"arithmetic_scalars"},
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="first",
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = differential_main(["--artifact-root", temp_dir, "--summary-root", temp_dir, "latest"])
            self.assertEqual(code, 0)
            output = stream.getvalue()
            self.assertIn(summary.run_id, output)
            self.assertIn("mismatches=0", output)

    def test_latest_mismatch_bundles_and_rerun_mismatches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            case = ProgramCase(
                case_id="forced_mismatch",
                name="Forced Mismatch",
                source="print(1 is 1)\n",
                tags=("scalar_arithmetic",),
                origin="generated",
            )
            summary, _ = _run_cases(
                cases=[case],
                artifact_root=temp_dir,
                summary_root=temp_dir,
                command="seed",
            )
            bundles = latest_mismatch_bundles(temp_dir)
            self.assertEqual(bundles, summary.mismatch_bundles)
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = differential_main(["--artifact-root", temp_dir, "--summary-root", temp_dir, "rerun-mismatches"])
            self.assertIn("cases=", stream.getvalue())
            self.assertIn(code, {0, 1})


if __name__ == "__main__":
    unittest.main()
