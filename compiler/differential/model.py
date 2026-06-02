from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ProgramCase:
    case_id: str
    name: str
    source: str
    tags: tuple[str, ...] = ()
    filename: str = "case.py"
    origin: str = "curated"
    seed: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionOutcome:
    lane: str
    status: str
    stdout: str
    error_stage: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    rendered_errors: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MismatchBundle:
    bundle_dir: str
    case_id: str
    name: str
    origin: str
    tags: tuple[str, ...] = ()
    seed: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class CaseResult:
    case: ProgramCase
    vm: ExecutionOutcome
    native: ExecutionOutcome
    matches: bool
    mismatch_reasons: tuple[str, ...] = ()
    bundle: MismatchBundle | None = None
    skipped: bool = False

    def to_dict(self) -> dict[str, object]:
        payload = {
            "case": self.case.to_dict(),
            "vm": self.vm.to_dict(),
            "native": self.native.to_dict(),
            "matches": self.matches,
            "mismatch_reasons": list(self.mismatch_reasons),
            "skipped": self.skipped,
        }
        if self.bundle is not None:
            payload["bundle"] = self.bundle.to_dict()
        return payload


@dataclass
class ParitySummary:
    profile_name: str
    run_id: str
    command: str
    total_cases: int
    curated_cases: int
    generated_cases: int
    skipped_cases: int
    comparable_runs: int
    exact_matches: int
    mismatches: int
    compile_failures: int
    runtime_failures: int
    agreement_rate: float
    vm_features: int
    native_features: int
    parity_features: int
    mismatch_bundles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
