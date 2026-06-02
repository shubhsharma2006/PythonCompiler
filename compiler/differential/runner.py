from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from compiler import compile_source, execute_source

from .corpus import iter_curated_cases
from .generator import DifferentialProgramGenerator
from .model import CaseResult, ParitySummary, ProgramCase
from .normalize import compare_outcomes, normalize_result
from .profile import current_native_profile
from .reporting import write_mismatch_bundle, write_summary


def run_curated_cases(
    *,
    case_ids: set[str] | None,
    artifact_root: str,
    summary_root: str,
    command: str,
) -> tuple[ParitySummary, list[CaseResult]]:
    return _run_cases(
        cases=iter_curated_cases(case_ids),
        artifact_root=artifact_root,
        summary_root=summary_root,
        command=command,
    )


def run_generated_cases(
    *,
    seed: int,
    count: int,
    artifact_root: str,
    summary_root: str,
    command: str,
) -> tuple[ParitySummary, list[CaseResult]]:
    generator = DifferentialProgramGenerator(seed)
    cases = generator.generate_cases(count)
    return _run_cases(
        cases=cases,
        artifact_root=artifact_root,
        summary_root=summary_root,
        command=command,
    )


def rerun_bundle(
    *,
    bundle_dir: str,
    artifact_root: str,
    summary_root: str,
    command: str,
) -> tuple[ParitySummary, list[CaseResult]]:
    bundle_path = Path(bundle_dir)
    source = (bundle_path / "source.py").read_text(encoding="utf-8")
    case = ProgramCase(
        case_id=bundle_path.name,
        name=bundle_path.name,
        source=source,
        filename="repro.py",
        origin="repro",
    )
    return _run_cases(
        cases=[case],
        artifact_root=artifact_root,
        summary_root=summary_root,
        command=command,
    )


def _run_cases(
    *,
    cases: list[ProgramCase],
    artifact_root: str,
    summary_root: str,
    command: str,
) -> tuple[ParitySummary, list[CaseResult]]:
    profile = current_native_profile()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mismatch_root = Path(artifact_root) / run_id
    summary_dir = Path(summary_root) / run_id

    results: list[CaseResult] = []
    for case in cases:
        results.append(_run_case(case=case, mismatch_root=mismatch_root, command=command))

    summary = _build_summary(profile_name=profile.name, run_id=run_id, command=command, results=results, feature_count=len(profile.features))
    write_summary(summary, results, summary_dir)
    return summary, results


def _run_case(*, case: ProgramCase, mismatch_root: Path, command: str) -> CaseResult:
    with TemporaryDirectory(prefix="compiler-diff-") as temp_dir:
        filename = str(Path(temp_dir) / case.filename)
        native_output = str(Path(temp_dir) / f"{case.case_id}.c")

        vm_result = execute_source(case.source, filename=filename)
        native_result = compile_source(case.source, filename=filename, output=native_output, run=True)

        vm_outcome = normalize_result(vm_result, "vm")
        native_outcome = normalize_result(native_result, "native")
        matches, mismatch_reasons = compare_outcomes(vm_outcome, native_outcome)

        bundle = None
        if not matches:
            bundle = write_mismatch_bundle(
                case=case,
                vm_outcome=vm_outcome,
                native_outcome=native_outcome,
                vm_result=vm_result,
                native_result=native_result,
                run_dir=mismatch_root,
                command=command,
            )
        return CaseResult(
            case=case,
            vm=vm_outcome,
            native=native_outcome,
            matches=matches,
            mismatch_reasons=mismatch_reasons,
            bundle=bundle,
        )


def _build_summary(
    *,
    profile_name: str,
    run_id: str,
    command: str,
    results: list[CaseResult],
    feature_count: int,
) -> ParitySummary:
    total_cases = len(results)
    curated_cases = sum(1 for result in results if result.case.origin == "curated")
    generated_cases = sum(1 for result in results if result.case.origin == "generated")
    skipped_cases = sum(1 for result in results if result.skipped)
    comparable_runs = total_cases - skipped_cases
    exact_matches = sum(1 for result in results if result.matches and not result.skipped)
    mismatches = sum(1 for result in results if not result.matches and not result.skipped)
    compile_failures = sum(
        1
        for result in results
        if "compile_error" in {result.vm.status, result.native.status}
    )
    runtime_failures = sum(
        1
        for result in results
        if "runtime_error" in {result.vm.status, result.native.status}
    )
    agreement_rate = (exact_matches / comparable_runs) if comparable_runs else 0.0

    feature_results: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        for tag in result.case.tags:
            feature_results[tag].append(result.matches)
    parity_features = sum(
        1 for matches in feature_results.values() if matches and all(matches)
    )

    mismatch_bundles = [
        result.bundle.bundle_dir
        for result in results
        if result.bundle is not None
    ]

    return ParitySummary(
        profile_name=profile_name,
        run_id=run_id,
        command=command,
        total_cases=total_cases,
        curated_cases=curated_cases,
        generated_cases=generated_cases,
        skipped_cases=skipped_cases,
        comparable_runs=comparable_runs,
        exact_matches=exact_matches,
        mismatches=mismatches,
        compile_failures=compile_failures,
        runtime_failures=runtime_failures,
        agreement_rate=agreement_rate,
        vm_features=feature_count,
        native_features=feature_count,
        parity_features=parity_features,
        mismatch_bundles=mismatch_bundles,
    )
