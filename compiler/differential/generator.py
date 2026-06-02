from __future__ import annotations

import random

from .model import ProgramCase
from .profile import (
    FEATURE_BASIC_EXCEPTIONS,
    FEATURE_CONTAINER_DISPLAY,
    FEATURE_EQUALITY,
    FEATURE_FOR_RANGE,
    FEATURE_FUNCTION_CALLS,
    FEATURE_IF_WHILE,
    FEATURE_INDEXING,
    FEATURE_LEN,
    FEATURE_LIST_LITERAL,
    FEATURE_MEMBERSHIP,
    FEATURE_SCALAR_ARITHMETIC,
    FEATURE_SLICING,
    FEATURE_TRUTHINESS,
    FEATURE_TRY_FINALLY,
    FEATURE_TUPLE_LITERAL,
)


class DifferentialProgramGenerator:
    def __init__(self, seed: int):
        self._seed = seed
        self._rng = random.Random(seed)

    def generate_cases(self, count: int) -> list[ProgramCase]:
        return [self.generate_case(index) for index in range(count)]

    def generate_case(self, index: int) -> ProgramCase:
        strategy = self._rng.choice(
            [
                self._arithmetic_program,
                self._if_while_program,
                self._for_range_program,
                self._function_program,
                self._container_index_program,
                self._container_slice_program,
                self._truthiness_program,
                self._equality_program,
                self._membership_program,
                self._display_program,
                self._basic_exception_program,
                self._try_finally_program,
            ]
        )
        source, tags = strategy()
        return ProgramCase(
            case_id=f"generated_{self._seed}_{index:04d}",
            name=f"generated_{index}",
            source=source,
            tags=tags,
            filename=f"generated_{index}.py",
            origin="generated",
            seed=self._seed,
        )

    def _int_literal(self) -> int:
        return self._rng.randint(0, 9)

    def _bool_literal(self) -> str:
        return "True" if self._rng.choice([True, False]) else "False"

    def _string_literal(self) -> str:
        return repr(self._rng.choice(["a", "b", "hi", "vm", "native"]))

    def _scalar_expr(self, depth: int = 0) -> str:
        if depth >= 2:
            return str(self._int_literal())
        choice = self._rng.choice(["int", "bool", "arith", "compare"])
        if choice == "int":
            return str(self._int_literal())
        if choice == "bool":
            return self._bool_literal()
        if choice == "compare":
            left = str(self._int_literal())
            right = str(self._int_literal())
            op = self._rng.choice(["<", "<=", ">", ">=", "==", "!="])
            return f"({left} {op} {right})"
        left = self._scalar_expr(depth + 1)
        right = self._scalar_expr(depth + 1)
        op = self._rng.choice(["+", "-", "*", "%"])
        return f"({left} {op} {right})"

    def _container_literal(self, kind: str) -> tuple[str, str]:
        elem_kind = self._rng.choice(["int", "bool", "str"])
        count = self._rng.randint(2, 4)
        values: list[str] = []
        for _ in range(count):
            if elem_kind == "int":
                values.append(str(self._int_literal()))
            elif elem_kind == "bool":
                values.append(self._bool_literal())
            else:
                values.append(self._string_literal())
        body = ", ".join(values)
        if kind == "list":
            return f"[{body}]", elem_kind
        return f"({body})", elem_kind

    def _nonzero_step(self) -> int:
        return self._rng.choice([-3, -2, -1, 1, 2, 3])

    def _arithmetic_program(self) -> tuple[str, tuple[str, ...]]:
        source = "\n".join(
            [
                f"x = {self._scalar_expr()}",
                f"y = {self._scalar_expr()}",
                "print(x)",
                "print(y)",
                "print(x == y)",
            ]
        )
        return source + "\n", (FEATURE_SCALAR_ARITHMETIC,)

    def _if_while_program(self) -> tuple[str, tuple[str, ...]]:
        limit = self._rng.randint(2, 5)
        source = "\n".join(
            [
                "count = 0",
                "total = 0",
                f"while count < {limit}:",
                "    if count % 2 == 0:",
                "        total = total + count",
                "    else:",
                "        total = total + 1",
                "    count = count + 1",
                "print(total)",
            ]
        )
        return source + "\n", (FEATURE_IF_WHILE,)

    def _for_range_program(self) -> tuple[str, tuple[str, ...]]:
        start = self._rng.randint(0, 3)
        stop = start + self._rng.randint(2, 5)
        source = "\n".join(
            [
                "total = 0",
                f"for i in range({start}, {stop}):",
                "    total = total + i",
                "print(total)",
            ]
        )
        return source + "\n", (FEATURE_FOR_RANGE,)

    def _function_program(self) -> tuple[str, tuple[str, ...]]:
        a = self._int_literal()
        b = self._int_literal()
        c = self._int_literal() or 1
        source = "\n".join(
            [
                "def blend(a, b, c):",
                "    return a + b * c",
                f"print(blend({a}, {b}, {c}))",
            ]
        )
        return source + "\n", (FEATURE_FUNCTION_CALLS, FEATURE_SCALAR_ARITHMETIC)

    def _container_index_program(self) -> tuple[str, tuple[str, ...]]:
        container_kind = self._rng.choice(["list", "tuple"])
        literal, _ = self._container_literal(container_kind)
        index = self._rng.randint(0, max(0, literal.count(",") + 1 - 1))
        name = "items" if container_kind == "list" else "pair"
        source = "\n".join(
            [
                f"{name} = {literal}",
                f"print(len({name}))",
                f"print({name}[{index}])",
            ]
        )
        tags = (
            FEATURE_LIST_LITERAL if container_kind == "list" else FEATURE_TUPLE_LITERAL,
            FEATURE_LEN,
            FEATURE_INDEXING,
        )
        return source + "\n", tags

    def _container_slice_program(self) -> tuple[str, tuple[str, ...]]:
        container_kind = self._rng.choice(["list", "tuple"])
        literal, _ = self._container_literal(container_kind)
        name = "items" if container_kind == "list" else "pair"
        step = self._nonzero_step()
        source = "\n".join(
            [
                f"{name} = {literal}",
                f"print({name}[1:])",
                f"print({name}[::{step}])",
            ]
        )
        tags = (
            FEATURE_LIST_LITERAL if container_kind == "list" else FEATURE_TUPLE_LITERAL,
            FEATURE_SLICING,
            FEATURE_CONTAINER_DISPLAY,
        )
        return source + "\n", tags

    def _truthiness_program(self) -> tuple[str, tuple[str, ...]]:
        literal, _ = self._container_literal("list")
        source = "\n".join(
            [
                f"items = {literal}",
                "empty = items[:0]",
                "if items:",
                '    print("items")',
                "if not empty:",
                '    print("empty")',
            ]
        )
        return source + "\n", (FEATURE_LIST_LITERAL, FEATURE_TRUTHINESS, FEATURE_SLICING)

    def _equality_program(self) -> tuple[str, tuple[str, ...]]:
        literal, _ = self._container_literal(self._rng.choice(["list", "tuple"]))
        source = "\n".join(
            [
                f"a = {literal}",
                f"b = {literal}",
                "print(a == b)",
                "print(a != b[:0])",
            ]
        )
        return source + "\n", (FEATURE_EQUALITY, FEATURE_SLICING, FEATURE_CONTAINER_DISPLAY)

    def _membership_program(self) -> tuple[str, tuple[str, ...]]:
        literal, elem_kind = self._container_literal("list")
        needle = {
            "int": str(self._int_literal()),
            "bool": self._bool_literal(),
            "str": self._string_literal(),
        }[elem_kind]
        source = "\n".join(
            [
                f"items = {literal}",
                f"print({needle} in items)",
                f"print({needle} not in items[:0])",
            ]
        )
        return source + "\n", (FEATURE_LIST_LITERAL, FEATURE_MEMBERSHIP, FEATURE_SLICING)

    def _display_program(self) -> tuple[str, tuple[str, ...]]:
        pair, _ = self._container_literal("tuple")
        items, _ = self._container_literal("list")
        source = "\n".join(
            [
                f"items = {items}",
                f"pair = {pair}",
                "print(items)",
                "print(str(items))",
                "print(repr(pair))",
            ]
        )
        return source + "\n", (FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_CONTAINER_DISPLAY)

    def _basic_exception_program(self) -> tuple[str, tuple[str, ...]]:
        source = "\n".join(
            [
                "try:",
                '    raise "boom"',
                "except:",
                '    print("handled")',
            ]
        )
        return source + "\n", (FEATURE_BASIC_EXCEPTIONS,)

    def _try_finally_program(self) -> tuple[str, tuple[str, ...]]:
        value = self._int_literal()
        source = "\n".join(
            [
                "def compute():",
                "    try:",
                f"        return {value}",
                "    finally:",
                '        print("cleanup")',
                "print(compute())",
            ]
        )
        return source + "\n", (FEATURE_TRY_FINALLY,)
