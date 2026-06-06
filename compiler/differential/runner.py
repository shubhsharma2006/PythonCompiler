from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from compiler import compile_source, execute_source

from .corpus import iter_curated_cases
from .generator import DifferentialProgramGenerator
import json

from .model import CaseResult, FeatureParity, ParitySummary, ProgramCase
from .normalize import compare_outcomes, normalize_result
from .profile import current_native_profile
from .reporting import write_mismatch_bundle, write_summary
from .validation import ProfileValidation, validate_case, validate_curated_cases


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


def validate_current_curated_cases() -> list[tuple[ProgramCase, ProfileValidation]]:
    return validate_curated_cases()


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


def rerun_bundles(
    *,
    bundle_dirs: list[str],
    artifact_root: str,
    summary_root: str,
    command: str,
) -> tuple[ParitySummary, list[CaseResult]]:
    cases: list[ProgramCase] = []
    for bundle_dir in bundle_dirs:
        bundle_path = Path(bundle_dir)
        source = (bundle_path / "source.py").read_text(encoding="utf-8")
        meta = json.loads((bundle_path / "meta.json").read_text(encoding="utf-8"))
        case_meta = meta.get("case", {})
        cases.append(
            ProgramCase(
                case_id=str(case_meta.get("case_id", bundle_path.name)),
                name=str(case_meta.get("name", bundle_path.name)),
                source=source,
                tags=tuple(case_meta.get("tags", [])),
                filename=str(case_meta.get("filename", "repro.py")),
                origin="repro",
                seed=case_meta.get("seed"),
            )
        )
    return _run_cases(
        cases=cases,
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
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    mismatch_root = Path(artifact_root) / run_id
    summary_dir = Path(summary_root) / run_id

    results: list[CaseResult] = []
    for case in cases:
        results.append(_run_case(case=case, mismatch_root=mismatch_root, command=command))

    summary = _build_summary(profile_name=profile.name, run_id=run_id, command=command, results=results, feature_count=len(profile.features))
    write_summary(summary, results, summary_dir)
    return summary, results


def _run_case(*, case: ProgramCase, mismatch_root: Path, command: str) -> CaseResult:
    validation = validate_case(case)
    if not validation.ok:
        skipped_outcome = _skipped_outcome("profile_violation")
        return CaseResult(
            case=case,
            vm=skipped_outcome,
            native=skipped_outcome,
            matches=False,
            mismatch_reasons=(),
            skipped=True,
            profile_status=validation.status,
            profile_errors=validation.errors,
        )

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
            profile_status=validation.status,
            profile_errors=validation.errors,
        )


def _skipped_outcome(reason: str):
    from .model import ExecutionOutcome

    return ExecutionOutcome(
        lane="profile",
        status="skipped",
        stdout="",
        error_stage="profile",
        error_type="Profile",
        error_message=reason,
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
    profile_violations = sum(1 for result in results if result.profile_status == "profile_violation")
    generated_profile_skips = sum(
        1
        for result in results
        if result.case.origin == "generated" and result.profile_status == "profile_violation"
    )
    curated_profile_failures = sum(
        1
        for result in results
        if result.case.origin == "curated" and result.profile_status == "profile_violation"
    )
    agreement_rate = (exact_matches / comparable_runs) if comparable_runs else 0.0

    feature_results: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        for tag in result.case.tags:
            feature_results[tag].append(result)
    feature_stats: dict[str, FeatureParity] = {}
    for feature_name, tagged_results in feature_results.items():
        total_feature_cases = len(tagged_results)
        feature_exact_matches = sum(1 for result in tagged_results if result.matches and not result.skipped)
        feature_mismatches = sum(1 for result in tagged_results if not result.matches and not result.skipped)
        feature_skipped = sum(1 for result in tagged_results if result.skipped)
        feature_stats[feature_name] = FeatureParity(
            total_cases=total_feature_cases,
            exact_matches=feature_exact_matches,
            mismatches=feature_mismatches,
            skipped_cases=feature_skipped,
            green=feature_mismatches == 0 and feature_skipped == 0,
        )
    parity_features = sum(
        1 for stats in feature_stats.values() if stats.green
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
        profile_violations=profile_violations,
        generated_profile_skips=generated_profile_skips,
        curated_profile_failures=curated_profile_failures,
        agreement_rate=agreement_rate,
        vm_features=feature_count,
        native_features=feature_count,
        parity_features=parity_features,
        feature_stats=feature_stats,
        mismatch_bundles=mismatch_bundles,
    )


def latest_summary_path(summary_root: str) -> Path | None:
    root = Path(summary_root)
    candidates = sorted(root.glob("*/summary.json"))
    if not candidates:
        return None
    return candidates[-1]


def latest_mismatch_bundles(summary_root: str) -> list[str]:
    summary_path = latest_summary_path(summary_root)
    if summary_path is None:
        return []
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    return list(payload.get("summary", {}).get("mismatch_bundles", []))
