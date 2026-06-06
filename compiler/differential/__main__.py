from __future__ import annotations

import argparse
import json
import sys

from .runner import (
    latest_mismatch_bundles,
    latest_summary_path,
    rerun_bundle,
    rerun_bundles,
    run_curated_cases,
    run_generated_cases,
    validate_current_curated_cases,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m compiler.differential",
        description="Run VM/native differential checks for the current native subset",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/differential",
        help="Directory for mismatch bundles",
    )
    parser.add_argument(
        "--summary-root",
        default="artifacts/parity",
        help="Directory for parity summaries",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run curated differential corpus")
    run_parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Optional curated case id filter; may be repeated",
    )

    fuzz_parser = subparsers.add_parser("fuzz", help="Run deterministic generated programs")
    fuzz_parser.add_argument("--seed", type=int, default=0, help="Deterministic generator seed")
    fuzz_parser.add_argument("--count", type=int, default=25, help="Number of generated programs")

    repro_parser = subparsers.add_parser("repro", help="Re-run a saved mismatch bundle")
    repro_parser.add_argument("bundle_dir", help="Mismatch bundle directory containing source.py")

    subparsers.add_parser("latest", help="Show the newest parity summary")
    subparsers.add_parser("rerun-mismatches", help="Re-run mismatch bundles from the latest parity run")
    subparsers.add_parser("validate", help="Validate curated corpus against the native differential profile")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = "python3 -m compiler.differential " + " ".join(argv or sys.argv[1:])

    if args.command == "latest":
        summary_path = latest_summary_path(args.summary_root)
        if summary_path is None:
            print("no parity summaries found")
            return 1
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        summary = payload["summary"]
        print(f"summary={summary_path}")
        print(f"profile={summary['profile_name']}")
        print(f"run_id={summary['run_id']}")
        print(f"cases={summary['total_cases']}")
        print(f"matches={summary['exact_matches']}")
        print(f"mismatches={summary['mismatches']}")
        print(f"skipped={summary['skipped_cases']}")
        print(f"profile_violations={summary['profile_violations']}")
        bundles = summary.get("mismatch_bundles", [])
        if bundles:
            print("mismatch_bundles=")
            for bundle in bundles:
                print(bundle)
        return 0

    if args.command == "rerun-mismatches":
        bundle_dirs = latest_mismatch_bundles(args.summary_root)
        if not bundle_dirs:
            print("mismatch_bundles=0")
            return 0
        summary, _ = rerun_bundles(
            bundle_dirs=bundle_dirs,
            artifact_root=args.artifact_root,
            summary_root=args.summary_root,
            command=command,
        )
        print(f"profile={summary.profile_name}")
        print(f"run_id={summary.run_id}")
        print(f"cases={summary.total_cases}")
        print(f"matches={summary.exact_matches}")
        print(f"mismatches={summary.mismatches}")
        print(f"skipped={summary.skipped_cases}")
        return 0 if summary.mismatches == 0 and summary.curated_profile_failures == 0 else 1

    if args.command == "validate":
        validations = validate_current_curated_cases()
        failures = [(case, validation) for case, validation in validations if not validation.ok]
        print(f"cases={len(validations)}")
        print(f"profile_violations={len(failures)}")
        for case, validation in failures:
            print(f"{case.case_id}: {'; '.join(validation.errors)}")
        return 0 if not failures else 1

    if args.command == "run":
        summary, _ = run_curated_cases(
            case_ids=set(args.case) or None,
            artifact_root=args.artifact_root,
            summary_root=args.summary_root,
            command=command,
        )
    elif args.command == "fuzz":
        summary, _ = run_generated_cases(
            seed=args.seed,
            count=args.count,
            artifact_root=args.artifact_root,
            summary_root=args.summary_root,
            command=command,
        )
    else:
        summary, _ = rerun_bundle(
            bundle_dir=args.bundle_dir,
            artifact_root=args.artifact_root,
            summary_root=args.summary_root,
            command=command,
        )

    print(f"profile={summary.profile_name}")
    print(f"run_id={summary.run_id}")
    print(f"cases={summary.total_cases}")
    print(f"matches={summary.exact_matches}")
    print(f"mismatches={summary.mismatches}")
    print(f"skipped={summary.skipped_cases}")
    print(f"profile_violations={summary.profile_violations}")
    print(f"generated_profile_skips={summary.generated_profile_skips}")
    print(f"curated_profile_failures={summary.curated_profile_failures}")
    print(f"agreement_rate={summary.agreement_rate:.4f}")
    if summary.mismatch_bundles:
        print("mismatch_bundles=")
        for bundle in summary.mismatch_bundles:
            print(bundle)
    return 0 if summary.mismatches == 0 and summary.curated_profile_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
