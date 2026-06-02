from __future__ import annotations

import argparse
import sys

from .runner import rerun_bundle, run_curated_cases, run_generated_cases


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = "python3 -m compiler.differential " + " ".join(argv or sys.argv[1:])

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
    print(f"agreement_rate={summary.agreement_rate:.4f}")
    if summary.mismatch_bundles:
        print("mismatch_bundles=")
        for bundle in summary.mismatch_bundles:
            print(bundle)
    return 0 if summary.mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
