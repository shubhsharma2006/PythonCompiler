from __future__ import annotations

import json
from pathlib import Path

from compiler.pipeline import CompilationResult

from .model import CaseResult, ExecutionOutcome, MismatchBundle, ParitySummary, ProgramCase


def write_mismatch_bundle(
    *,
    case: ProgramCase,
    vm_outcome: ExecutionOutcome,
    native_outcome: ExecutionOutcome,
    vm_result: CompilationResult,
    native_result: CompilationResult,
    run_dir: Path,
    command: str,
) -> MismatchBundle:
    bundle_dir = run_dir / case.case_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    (bundle_dir / "source.py").write_text(case.source, encoding="utf-8")
    (bundle_dir / "vm.json").write_text(json.dumps(vm_outcome.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    (bundle_dir / "native.json").write_text(json.dumps(native_outcome.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    (bundle_dir / "program_ast.txt").write_text(repr(native_result.program or vm_result.program), encoding="utf-8")
    (bundle_dir / "ir.txt").write_text(repr(native_result.ir) if native_result.ir is not None else "", encoding="utf-8")
    (bundle_dir / "ssa.txt").write_text(repr(native_result.ssa) if native_result.ssa is not None else "", encoding="utf-8")
    (bundle_dir / "program.c").write_text(native_result.c_code or "", encoding="utf-8")
    meta = {
        "case": case.to_dict(),
        "command": command,
        "vm_success": vm_result.success,
        "native_success": native_result.success,
    }
    (bundle_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")

    return MismatchBundle(
        bundle_dir=str(bundle_dir),
        case_id=case.case_id,
        name=case.name,
        origin=case.origin,
        tags=case.tags,
        seed=case.seed,
    )


def write_summary(summary: ParitySummary, results: list[CaseResult], summary_root: Path) -> tuple[Path, Path]:
    summary_root.mkdir(parents=True, exist_ok=True)
    json_path = summary_root / "summary.json"
    md_path = summary_root / "summary.md"

    cases_payload = [result.to_dict() for result in results]
    json_path.write_text(
        json.dumps(
            {
                "summary": summary.to_dict(),
                "cases": cases_payload,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Differential Summary",
        "",
        f"- Profile: `{summary.profile_name}`",
        f"- Run ID: `{summary.run_id}`",
        f"- Command: `{summary.command}`",
        f"- Total cases: `{summary.total_cases}`",
        f"- Curated cases: `{summary.curated_cases}`",
        f"- Generated cases: `{summary.generated_cases}`",
        f"- Skipped cases: `{summary.skipped_cases}`",
        f"- Comparable runs: `{summary.comparable_runs}`",
        f"- Exact matches: `{summary.exact_matches}`",
        f"- Mismatches: `{summary.mismatches}`",
        f"- Compile failures: `{summary.compile_failures}`",
        f"- Runtime failures: `{summary.runtime_failures}`",
        f"- Agreement rate: `{summary.agreement_rate:.4f}`",
        f"- Profile-scoped VM features: `{summary.vm_features}`",
        f"- Profile-scoped native features: `{summary.native_features}`",
        f"- Features with zero observed mismatches: `{summary.parity_features}`",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        status = "match" if result.matches else "mismatch"
        lines.append(f"- `{result.case.case_id}`: {status}")
        if result.bundle is not None:
            lines.append(f"  - bundle: `{result.bundle.bundle_dir}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
