from __future__ import annotations

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


CURATED_CASES: tuple[ProgramCase, ...] = (
    ProgramCase(
        case_id="arithmetic_scalars",
        name="Scalar arithmetic",
        tags=(FEATURE_SCALAR_ARITHMETIC,),
        source="""x = 7
y = 3
print(x + y)
print(x * y)
print(x // y)
print((x - y) == 4)
""",
    ),
    ProgramCase(
        case_id="if_while_control",
        name="If and while control flow",
        tags=(FEATURE_IF_WHILE,),
        source="""count = 0
total = 0
while count < 4:
    if count % 2 == 0:
        total = total + count
    else:
        total = total + 1
    count = count + 1
print(total)
""",
    ),
    ProgramCase(
        case_id="for_range_sum",
        name="For loop over range",
        tags=(FEATURE_FOR_RANGE,),
        source="""total = 0
for i in range(1, 5):
    total = total + i
print(total)
""",
    ),
    ProgramCase(
        case_id="positional_function_calls",
        name="Direct positional function calls",
        tags=(FEATURE_FUNCTION_CALLS, FEATURE_SCALAR_ARITHMETIC),
        source="""def combine(a, b, c):
    return a + b * c

print(combine(2, 3, 4))
""",
    ),
    ProgramCase(
        case_id="basic_try_except",
        name="Basic try except",
        tags=(FEATURE_BASIC_EXCEPTIONS,),
        source="""try:
    raise "boom"
except:
    print("handled")
""",
    ),
    ProgramCase(
        case_id="try_finally_return",
        name="Try finally return override semantics",
        tags=(FEATURE_TRY_FINALLY,),
        source="""def compute():
    try:
        return 4
    finally:
        print("cleanup")

print(compute())
""",
    ),
    ProgramCase(
        case_id="list_tuple_len_index",
        name="List tuple len and indexing",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_LEN, FEATURE_INDEXING),
        source="""items = [10, 20, 30]
pair = (4, 5, 6)
print(len(items))
print(items[1])
print(pair[2])
""",
    ),
    ProgramCase(
        case_id="container_slicing",
        name="List and tuple slicing",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_SLICING, FEATURE_CONTAINER_DISPLAY),
        source="""items = [0, 1, 2, 3, 4]
pair = (5, 6, 7, 8)
print(items[1:4])
print(items[::-1])
print(pair[:3])
""",
    ),
    ProgramCase(
        case_id="container_truthiness",
        name="Container truthiness",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_TRUTHINESS),
        source="""items = [1, 2]
pair = (3, 4)
empty_tail = items[:0]
if items:
    print("items")
if pair:
    print("pair")
if not empty_tail:
    print("empty")
""",
    ),
    ProgramCase(
        case_id="container_equality",
        name="Container equality",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_EQUALITY),
        source="""items = [1, 2, 3]
same = [1, 2, 3]
pair = (4, 5)
other = (4, 6)
print(items == same)
print(pair != other)
""",
    ),
    ProgramCase(
        case_id="container_membership",
        name="Container membership",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_MEMBERSHIP),
        source="""items = [2, 4, 6]
pair = (1, 3, 5)
print(4 in items)
print(2 not in pair)
""",
    ),
    ProgramCase(
        case_id="container_display",
        name="Container display and conversions",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_CONTAINER_DISPLAY),
        source="""items = [1, 2]
pair = ("a", "b")
print(items)
print(str(items))
print(repr(pair))
""",
    ),
)


def iter_curated_cases(case_ids: set[str] | None = None) -> list[ProgramCase]:
    if not case_ids:
        return list(CURATED_CASES)
    return [case for case in CURATED_CASES if case.case_id in case_ids]
