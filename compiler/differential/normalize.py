from __future__ import annotations

import os
import re
import tempfile

from compiler.pipeline import CompilationResult

from .model import ExecutionOutcome


_ABSOLUTE_PATH_RE = re.compile(r"(/[^:\s]+)+")


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(os.getcwd(), "<workspace>")
    temp_root = tempfile.gettempdir()
    normalized = normalized.replace(temp_root, "<tmp>")
    normalized = _ABSOLUTE_PATH_RE.sub(_replace_path, normalized)
    return normalized.strip()


def _replace_path(match: re.Match[str]) -> str:
    candidate = match.group(0)
    basename = os.path.basename(candidate)
    if not basename:
        return candidate
    if basename.endswith((".py", ".c", ".h")) or basename in {"output", "program"}:
        return basename
    if candidate.startswith("<"):
        return candidate
    return candidate


def normalize_result(result: CompilationResult, lane: str) -> ExecutionOutcome:
    primary_issue = result.errors.errors[0] if result.errors.errors else None
    stdout = result.run_output or ""
    rendered_errors = result.errors.render() or None

    if result.success:
        return ExecutionOutcome(
            lane=lane,
            status="success",
            stdout=stdout,
            rendered_errors=normalize_text(rendered_errors),
        )

    status = "runtime_error" if primary_issue is not None and primary_issue.kind == "Runtime" else "compile_error"
    return ExecutionOutcome(
        lane=lane,
        status=status,
        stdout=stdout,
        error_stage="runtime" if status == "runtime_error" else "compile",
        error_type=primary_issue.kind if primary_issue is not None else None,
        error_message=normalize_text(primary_issue.message if primary_issue is not None else None),
        rendered_errors=normalize_text(rendered_errors),
    )


def compare_outcomes(vm: ExecutionOutcome, native: ExecutionOutcome) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if vm.status != native.status:
        reasons.append(f"status: vm={vm.status} native={native.status}")
    if vm.stdout != native.stdout:
        reasons.append("stdout")
    if vm.status != "success" or native.status != "success":
        if vm.error_stage != native.error_stage:
            reasons.append(f"error_stage: vm={vm.error_stage} native={native.error_stage}")
        if vm.error_type != native.error_type:
            reasons.append(f"error_type: vm={vm.error_type} native={native.error_type}")
        if vm.error_message != native.error_message:
            reasons.append("error_message")
    return not reasons, tuple(reasons)
