from __future__ import annotations

import argparse
import ast
import os
import sys

from compiler.pipeline import check_source, compile_source, execute_source
from compiler.utils.logger import CompilerLogger


DEMO_SOURCE = """x = 10
y = 3

def add(a, b):
    return a + b

if x > y and y > 0:
    print(add(x, y))
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python-subset-compiler",
        description="Run or compile the current Python implementation pipeline",
    )
    parser.add_argument("file", nargs="?", default=None, help="Source file to compile")
    parser.add_argument("-o", "--output", default="output.c", help="Output C filename")
    parser.add_argument("--check", action="store_true", help="Parse and analyze only")
    parser.add_argument("--compile-native", action="store_true", help="Compile the program to C and runtime artifacts")
    parser.add_argument("--run-native", action="store_true", help="Compile the generated C with GCC and execute it")
    parser.add_argument("--run", action="store_true", help="Legacy alias for --run-native")
    parser.add_argument("--dump", choices=["tokens", "ast", "bytecode", "ir"], help="Print an internal representation")
    parser.add_argument("--viz-ast", nargs="?", const="ast_output", default=None, help="Render a PNG of the legacy AST to the given basename (default: ast_output)")
    parser.add_argument("--no-viz", action="store_true", help="Accepted for compatibility; does nothing")
    parser.add_argument("-q", "--quiet", action="store_true", help="Reduce CLI output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable additional compiler logs")
    parser.add_argument("--frontend", choices=["cpython", "owned"], default="owned", help="Parser frontend to use (default: owned)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = CompilerLogger(verbose=args.verbose, quiet=args.quiet)

    if args.file is None:
        source = DEMO_SOURCE
        filename = "<demo>"
    else:
        if not os.path.exists(args.file):
            logger.error(f"File not found: {args.file}")
            return 1
        with open(args.file, "r", encoding="utf-8") as handle:
            source = handle.read()
        filename = args.file

    if args.check:
        mode = "check"
    elif args.compile_native:
        mode = "compile-native"
    elif args.run_native or args.run:
        mode = "run-native"
    else:
        mode = "run"

    logger.stage(mode.title())
    if mode == "check":
        result = check_source(source, filename=filename)
    elif mode == "compile-native":
        result = compile_source(source, filename=filename, output=args.output, run=False, frontend=args.frontend)
    elif mode == "run-native":
        result = compile_source(source, filename=filename, output=args.output, run=True, frontend=args.frontend)
    else:
        result = execute_source(source, filename=filename, frontend=args.frontend)

    if result.success:
        _emit_dump(result, args.dump, logger)
        _maybe_emit_ast_viz(result, args.viz_ast, logger)
        if mode in {"compile-native", "run-native"}:
            logger.ok(f"C output written to {result.output_path}")
        else:
            logger.ok("Program analyzed successfully" if mode == "check" else "VM execution completed")
        if mode == "run" and result.run_output is not None:
            if not args.quiet:
                logger.stage("Program Output")
            sys.stdout.write(result.run_output)
            if result.run_output and not result.run_output.endswith("\n"):
                sys.stdout.write("\n")
        if mode == "run-native" and result.run_output is not None and not args.quiet:
            logger.stage("Program Output")
            sys.stdout.write(result.run_output)
            if result.run_output and not result.run_output.endswith("\n"):
                sys.stdout.write("\n")
        return 0

    result.errors.report()
    return 1


def _maybe_emit_ast_viz(result, viz_ast_basename: str | None, logger: CompilerLogger) -> None:
    if viz_ast_basename is None:
        return
    if result.program is None:
        logger.warn("AST visualization requested, but lowered AST is missing")
        return

    try:
        from ast_viz import visualise_ast  # type: ignore

        path = visualise_ast(result.program, filename=viz_ast_basename, fmt="png")
        if path:
            logger.ok(f"AST image written to {path}")
        else:
            logger.warn(
                "AST visualization requested, but graphviz is not available (optional). "
                "Install with: pip install graphviz && brew install graphviz"
            )
    except Exception as exc:
        # Production rule: visualization must never break compilation.
        logger.warn(f"Failed to render AST (optional): {exc}")


def _emit_dump(result, dump_kind: str | None, logger: CompilerLogger) -> None:
    if dump_kind is None:
        return
    if dump_kind == "tokens" and result.lexed is not None:
        logger.emit("\n".join(f"{token.kind} {token.text!r} @ {token.line}:{token.column}" for token in result.lexed.tokens))
        return
    if dump_kind == "ast" and result.parsed is not None:
        logger.emit(ast.dump(result.parsed.syntax_tree, indent=2))
        return
    if dump_kind == "bytecode" and result.bytecode is not None:
        logger.emit(str(result.bytecode))
        return
    if dump_kind == "ir" and result.ir is not None:
        logger.emit(repr(result.ir))
