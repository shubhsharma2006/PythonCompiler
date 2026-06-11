from __future__ import annotations

import copy
import os
import subprocess

from compiler.backend import CCodeGenerator
from compiler.core.ast import CallExpr, CompareExpr, ConstantExpr, DictExpr, IndexAssignStmt, IndexExpr, ListExpr, NameExpr, PrintStmt, SetExpr, SliceExpr, TupleExpr
from compiler.core.types import ValueType, merge_types
from compiler.ir import (
    CFGConstantPropagation,
    ExceptionalLivenessAnalysis,
    IRGenerator,
    OwnershipDecrefPlacement,
    SSAConstantPropagation,
    SSACopyPropagation,
    SSADeadCodeEliminator,
    SSADestructor,
    SSATransformer,
    SSAValuePropagation,
)
from compiler.ir.exception_cleanup import ExceptionCleanupLowering
from compiler.ir.exception_cleanup_validation import ExceptionCleanupValidation
from compiler.runtime import CRuntimeSupport

from .analyze import _analyze_source
from .feature_gates import (
    _iter_nodes,
    _program_uses_call_kwargs_splats,
    _program_uses_call_signature_features,
    _program_uses_compare_chains,
    _program_uses_container_builtin_calls,
    _program_uses_container_comprehensions,
    _program_uses_container_index_assign,
    _program_uses_container_indexing,
    _program_uses_container_literals,
    _program_uses_core_vm_only_features,
    _program_uses_generators,
    _program_uses_imports,
    _program_uses_lambdas,
    _program_uses_mixed_numeric_ops,
    _program_uses_negative_int_exponent,
    _program_uses_nested_functions,
    _program_uses_object_features,
    _program_uses_unsupported_exception_features,
    _program_uses_slicing,
    _program_uses_vm_only_builtin_calls,
    _program_uses_walrus,
)
from .model import CompilationResult


SUPPORTED_CONTAINER_ELEM_TYPES = {ValueType.INT, ValueType.FLOAT, ValueType.BOOL, ValueType.STRING}


def _program_uses_len_with_non_string(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if isinstance(node, CallExpr) and node.func_name == "len" and node.args:
            arg_type = semantic.expr_type(node.args[0])
            if arg_type not in {ValueType.STRING, ValueType.LIST, ValueType.TUPLE}:
                return True
            if arg_type == ValueType.UNKNOWN:
                return True
    return False


def _container_elem_type_for_expr(expr, semantic) -> ValueType | None:
    if isinstance(expr, NameExpr):
        return semantic.container_var_elem_types.get(expr.name)
    return semantic.container_elem_types.get(id(expr))


def _supports_native_homogeneous_container(expr, semantic) -> bool:
    container_type = semantic.expr_type(expr)
    if container_type not in {ValueType.LIST, ValueType.TUPLE}:
        return False
    # Empty container literals are trivially homogeneous; IR defaults them to the INT suffix
    if isinstance(expr, (ListExpr, TupleExpr)) and not expr.elements:
        return True
    elem_type = _container_elem_type_for_expr(expr, semantic)
    return elem_type in SUPPORTED_CONTAINER_ELEM_TYPES


def _program_uses_unsupported_indexing(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if not isinstance(node, IndexExpr):
            continue
        collection_type = semantic.expr_type(node.collection)
        if collection_type == ValueType.STRING:
            continue
        if collection_type not in {ValueType.LIST, ValueType.TUPLE}:
            return True
        elem_type = _container_elem_type_for_expr(node.collection, semantic)
        if elem_type is None or elem_type == ValueType.UNKNOWN:
            return True
    return False


def _program_uses_unsupported_slicing(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if not isinstance(node, IndexExpr):
            continue
        if not isinstance(node.index, SliceExpr):
            continue
        collection_type = semantic.expr_type(node.collection)
        if collection_type not in {ValueType.STRING, ValueType.LIST, ValueType.TUPLE}:
            return True
        if collection_type in {ValueType.LIST, ValueType.TUPLE}:
            if not _supports_native_homogeneous_container(node.collection, semantic):
                return True
        step = node.index.step
        if step is None:
            continue
        if isinstance(step, ConstantExpr) and isinstance(step.value, int) and step.value != 0:
            continue
        return True
    return False


def _program_uses_unsupported_container_display(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if isinstance(node, PrintStmt):
            for value in node.values:
                if semantic.expr_type(value) in {ValueType.LIST, ValueType.TUPLE} and not _supports_native_homogeneous_container(value, semantic):
                    return True
        if isinstance(node, CallExpr) and node.func_name in {"str", "repr", "ascii"}:
            if node.func_name == "ascii":
                return True
            if len(node.args) != 1 or node.kwargs or getattr(node, "kw_starred", []):
                return True
            arg_type = semantic.expr_type(node.args[0])
            if node.func_name == "repr":
                if arg_type not in {ValueType.LIST, ValueType.TUPLE}:
                    return True
                if not _supports_native_homogeneous_container(node.args[0], semantic):
                    return True
                continue
            if arg_type in {ValueType.INT, ValueType.FLOAT, ValueType.BOOL, ValueType.STRING}:
                continue
            if arg_type in {ValueType.LIST, ValueType.TUPLE}:
                if not _supports_native_homogeneous_container(node.args[0], semantic):
                    return True
                continue
            return True
    return False


def _program_uses_unsupported_container_compare_membership(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if not isinstance(node, CompareExpr):
            continue
        left_type = semantic.expr_type(node.left)
        right_type = semantic.expr_type(node.right)
        if node.op in {"==", "!="} and (left_type in {ValueType.LIST, ValueType.TUPLE} or right_type in {ValueType.LIST, ValueType.TUPLE}):
            if left_type == ValueType.UNKNOWN or right_type == ValueType.UNKNOWN:
                return True
            if left_type in {ValueType.LIST, ValueType.TUPLE} and not _supports_native_homogeneous_container(node.left, semantic):
                return True
            if right_type in {ValueType.LIST, ValueType.TUPLE} and not _supports_native_homogeneous_container(node.right, semantic):
                return True
        if node.op in {"in", "not in"}:
            if right_type not in {ValueType.LIST, ValueType.TUPLE}:
                return True
            if not _supports_native_homogeneous_container(node.right, semantic):
                return True
            if left_type == ValueType.UNKNOWN:
                return True
    return False


def _program_uses_unsupported_index_assign(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if not isinstance(node, IndexAssignStmt):
            continue
        collection_type = semantic.expr_type(node.collection)
        if collection_type != ValueType.LIST:
            return True
        elem_type = _container_elem_type_for_expr(node.collection, semantic)
        if elem_type is None or elem_type == ValueType.UNKNOWN:
            return True
        value_type = semantic.expr_type(node.value)
        if value_type == ValueType.UNKNOWN:
            return True
        merged = merge_types(elem_type, value_type)
        if merged is None or merged != elem_type:
            return True
    return False


def _program_uses_tuple_index_assign(program, semantic) -> bool:
    for node in _iter_nodes(program):
        if not isinstance(node, IndexAssignStmt):
            continue
        collection_type = semantic.expr_type(node.collection)
        if collection_type == ValueType.TUPLE:
            return True
    return False


def _program_uses_unsupported_container_literals(program, semantic) -> bool:
    supported_types = {ValueType.INT, ValueType.FLOAT, ValueType.BOOL, ValueType.STRING}
    for node in _iter_nodes(program):
        if isinstance(node, (DictExpr, SetExpr)):
            return True
        if not isinstance(node, (ListExpr, TupleExpr)):
            continue
        if not node.elements:
            continue  # empty containers are supported — IR defaults to INT suffix with size 0
        element_types = [semantic.expr_type(element) for element in node.elements]
        if any(elem_type == ValueType.UNKNOWN for elem_type in element_types):
            return True
        if any(elem_type not in supported_types for elem_type in element_types):
            return True
        first = element_types[0]
        if any(elem_type != first for elem_type in element_types[1:]):
            return True
    return False


def compile_source(
    source: str,
    *,
    filename: str = "<stdin>",
    output: str = "output.c",
    run: bool = False,
    frontend: str = "cpython",
) -> CompilationResult:
    result = _analyze_source(source, filename=filename, frontend=frontend)
    if not result.success or result.program is None or result.semantic is None:
        return result
    if _program_uses_imports(result.program):
        result.errors.error("Codegen", "native compilation does not support imports yet")
        result.success = False
        return result
    if _program_uses_nested_functions(result.program):
        result.errors.error("Codegen", "native compilation does not support nested functions yet")
        result.success = False
        return result
    if _program_uses_unsupported_exception_features(result.program):
        result.errors.error(
            "Codegen",
            "native compilation only supports try/except or try/finally without else yet",
        )
        result.success = False
        return result
    if _program_uses_generators(result.program):
        result.errors.error("Codegen", "native compilation does not support generators or yield yet")
        result.success = False
        return result
    if _program_uses_lambdas(result.program):
        result.errors.error("Codegen", "native compilation does not support lambda expressions yet")
        result.success = False
        return result
    if _program_uses_core_vm_only_features(result.program):
        result.errors.error("Codegen", "native compilation does not support unpacking assignment, delete, global/nonlocal, or with statements yet")
        result.success = False
        return result
    if _program_uses_slicing(result.program) and _program_uses_unsupported_slicing(result.program, result.semantic):
        result.errors.error(
            "Codegen",
            "native compilation only supports string/list/tuple slicing with homogeneous primitive elements and a constant non-zero step for now",
        )
        result.success = False
        return result
    if _program_uses_container_comprehensions(result.program):
        result.errors.error("Codegen", "native compilation does not support comprehensions yet")
        result.success = False
        return result
    if _program_uses_container_index_assign(result.program):
        if _program_uses_tuple_index_assign(result.program, result.semantic):
            result.errors.error("Codegen", "native compilation does not support tuple index assignment yet")
            result.success = False
            return result
        if _program_uses_unsupported_index_assign(result.program, result.semantic):
            result.errors.error(
                "Codegen",
                "native compilation only supports index assignment into homogeneous list values for now",
            )
            result.success = False
            return result
    if _program_uses_container_indexing(result.program) and _program_uses_unsupported_indexing(result.program, result.semantic):
        result.errors.error(
            "Codegen",
            "native compilation only supports indexing into homogeneous list/tuple values or strings for now",
        )
        result.success = False
        return result
    if _program_uses_unsupported_container_compare_membership(result.program, result.semantic):
        result.errors.error(
            "Codegen",
            "native compilation only supports list/tuple equality, membership, and truthy/display semantics on homogeneous primitive-element containers for now",
        )
        result.success = False
        return result
    if _program_uses_container_builtin_calls(result.program):
        result.errors.error("Codegen", "native compilation does not support list(), tuple(), dict(), or set() calls yet")
        result.success = False
        return result
    if _program_uses_container_literals(result.program):
        if _program_uses_unsupported_container_literals(result.program, result.semantic):
            result.errors.error(
                "Codegen",
                "native compilation only supports non-empty list/tuple literals with homogeneous primitive elements",
            )
            result.success = False
            return result
    if _program_uses_unsupported_container_display(result.program, result.semantic):
        result.errors.error(
            "Codegen",
            "native compilation only supports printing homogeneous primitive-element containers plus str()/repr() on that subset for now",
        )
        result.success = False
        return result
    if _program_uses_object_features(result.program):
        result.errors.error("Codegen", "native compilation does not support classes, attributes, or methods yet")
        result.success = False
        return result
    if _program_uses_call_signature_features(result.program):
        result.errors.error("Codegen", "native compilation does not support default or keyword arguments yet")
        result.success = False
        return result
    if _program_uses_compare_chains(result.program):
        result.errors.error("Codegen", "native compilation does not support comparison chaining yet")
        result.success = False
        return result
    if _program_uses_vm_only_builtin_calls(result.program):
        result.errors.error("Codegen", "native compilation does not support these builtin calls yet")
        result.success = False
        return result
    if _program_uses_len_with_non_string(result.program, result.semantic):
        result.errors.error("Codegen", "native compilation only supports len() on strings, lists, or tuples for now")
        result.success = False
        return result
    if _program_uses_negative_int_exponent(result.program):
        result.errors.error(
            "Codegen",
            "native compilation does not support negative integer exponents for '**' yet",
        )
        result.success = False
        return result
    if _program_uses_mixed_numeric_ops(result.program):
        result.errors.error(
            "Codegen",
            "native compilation does not support mixed int/float operands for '//' or '**' yet",
        )
        result.success = False
        return result
    if _program_uses_call_kwargs_splats(result.program):
        result.errors.error(
            "Codegen",
            "native compilation does not support call-site **kwargs splats yet",
        )
        result.success = False
        return result
    if _program_uses_walrus(result.program):
        result.errors.error(
            "Codegen",
            "native compilation does not support the walrus operator ':=' yet",
        )
        result.success = False
        return result

    cfg_module = IRGenerator(result.semantic).generate(result.program)
    cfg_module = CFGConstantPropagation().optimize(cfg_module)
    ssa_module = SSATransformer().transform(copy.deepcopy(cfg_module))
    ssa_module = SSAConstantPropagation().optimize(ssa_module)
    ssa_module = SSAValuePropagation().optimize(ssa_module)
    ssa_module = SSACopyPropagation().optimize(ssa_module)
    ssa_module = SSADeadCodeEliminator().optimize(ssa_module)
    ir_module = SSADestructor().lower(ssa_module)
    ir_module = OwnershipDecrefPlacement().apply(ir_module)
    ir_module = ExceptionalLivenessAnalysis().apply(ir_module)
    ir_module = ExceptionCleanupLowering().apply(ir_module)
    ir_module = ExceptionCleanupValidation().apply(ir_module)
    runtime = CRuntimeSupport()
    c_code = CCodeGenerator().generate(ir_module)
    output_path = os.path.abspath(output)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(c_code)
    runtime_header_path, runtime_source_path = runtime.emit_files(output_path)

    result.ir = ir_module
    result.ssa = ssa_module
    result.c_code = c_code
    result.output_path = output_path
    result.runtime_header_path = runtime_header_path
    result.runtime_source_path = runtime_source_path

    if run:
        executable_path = os.path.abspath(os.path.splitext(output_path)[0] or "output")
        compile_proc = subprocess.run(
            ["gcc", output_path, runtime_source_path, "-o", executable_path],
            capture_output=True,
            text=True,
        )
        if compile_proc.returncode != 0:
            result.errors.error("Codegen", compile_proc.stderr.strip() or "gcc failed")
            result.success = False
            result.executable_path = executable_path
            result.run_error = compile_proc.stderr
            return result
        run_proc = subprocess.run([executable_path], capture_output=True, text=True)
        result.executable_path = executable_path
        result.run_output = run_proc.stdout
        result.run_error = run_proc.stderr
        if run_proc.returncode != 0:
            result.errors.error("Runtime", f"program exited with status {run_proc.returncode}")
            result.success = False

    return result
