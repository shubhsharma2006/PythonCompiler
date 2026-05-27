from __future__ import annotations

import os

from compiler.vm import BytecodeLowerer, BytecodeModule, VMError

from .analyze import _analyze_source


def _module_name_for_filename(filename: str) -> str:
    if filename == "<stdin>":
        return "__main__"
    abs_filename = os.path.abspath(filename)
    basename = os.path.basename(abs_filename)
    module_name = os.path.splitext(basename)[0]
    if basename == "__init__.py":
        parts: list[str] = []
    else:
        parts = [module_name]
    current_dir = os.path.dirname(abs_filename)
    while os.path.exists(os.path.join(current_dir, "__init__.py")):
        parts.insert(0, os.path.basename(current_dir))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    return ".".join(parts) if parts else "__main__"


def _resolve_import_path(module_name: str, requester_filename: str) -> str:
    requester_dir = os.path.dirname(os.path.abspath(requester_filename)) or os.getcwd()
    module_parts = module_name.split(".")
    search_roots: list[str] = []
    current_root = requester_dir
    while True:
        search_roots.append(current_root)
        parent_root = os.path.dirname(current_root)
        if parent_root == current_root:
            break
        current_root = parent_root

    for root in search_roots:
        module_file = os.path.join(root, *module_parts) + ".py"
        package_init = os.path.join(root, *module_parts, "__init__.py")
        if os.path.exists(module_file):
            return os.path.abspath(module_file)
        if os.path.exists(package_init):
            return os.path.abspath(package_init)

    raise VMError(f"cannot resolve local module {module_name!r}")


def _load_bytecode_module(module_name: str, requester_filename: str) -> BytecodeModule:
    module_path = _resolve_import_path(module_name, requester_filename)
    with open(module_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    result = _analyze_source(source, filename=module_path)
    if not result.success or result.program is None:
        rendered = result.errors.render() or f"failed to analyze module {module_name!r}"
        raise VMError(rendered)
    return BytecodeLowerer().lower(
        result.program,
        module_name=module_name,
        filename=os.path.abspath(module_path),
    )
