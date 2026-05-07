"""Owned parser package — public API.

Usage::

    from compiler.frontend.parser import parse_to_program
    program = parse_to_program(lexed, errors)
"""
from compiler.frontend.parser.stmt_parser import parse_to_program

__all__ = ["parse_to_program"]
