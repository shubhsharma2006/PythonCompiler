from __future__ import annotations

from .model import ProgramCase
from .profile import (
    FEATURE_BASIC_EXCEPTIONS,
    FEATURE_CONTAINER_DISPLAY,
    FEATURE_EQUALITY,
    FEATURE_FOR_RANGE,
    FEATURE_FUNCTION_CALLS,
    FEATURE_IDENTITY,
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
        case_id="for_range_empty",
        name="For loop over empty range",
        tags=(FEATURE_FOR_RANGE,),
        source="""total = 0
for i in range(3, 3):
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
        case_id="try_finally_exception_path",
        name="Try finally exception path",
        tags=(FEATURE_BASIC_EXCEPTIONS, FEATURE_TRY_FINALLY),
        source="""try:
    try:
        raise "boom"
    finally:
        print("cleanup")
except:
    print("handled")
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
        case_id="container_slice_boundaries",
        name="Slice boundary behavior",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_SLICING, FEATURE_CONTAINER_DISPLAY),
        source="""items = [0, 1, 2, 3]
pair = (4, 5, 6, 7)
print(items[:])
print(items[2:2])
print(pair[-3:-1])
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
    # --- Phase 4.1: intentionally difficult parity cases ---
    ProgramCase(
        case_id="identity_same_object",
        name="Identity: same-reference list",
        tags=(FEATURE_IDENTITY, FEATURE_LIST_LITERAL),
        source="""a = []
b = a
print(a is b)
""",
    ),
    ProgramCase(
        case_id="identity_distinct_equal",
        name="Identity: distinct but equal lists",
        tags=(FEATURE_IDENTITY, FEATURE_LIST_LITERAL),
        source="""x = [1]
y = [1]
print(x is y)
""",
    ),
    ProgramCase(
        case_id="slice_out_of_bounds",
        name="Slice with out-of-bounds indices",
        tags=(FEATURE_LIST_LITERAL, FEATURE_SLICING, FEATURE_CONTAINER_DISPLAY),
        source="""a = [1, 2, 3]
print(a[:])
print(a[10:])
print(a[:-10])
""",
    ),
    ProgramCase(
        case_id="range_empty_single",
        name="For loop over range(0): body never executes",
        tags=(FEATURE_FOR_RANGE,),
        source="""total = 0
for i in range(0):
    total = total + i
print(total)
""",
    ),
    ProgramCase(
        case_id="range_empty_equal_bounds",
        name="For loop over range(n, n): empty range",
        tags=(FEATURE_FOR_RANGE,),
        source="""total = 0
for i in range(5, 5):
    total = total + i
print(total)
""",
    ),
    ProgramCase(
        case_id="range_reverse_step",
        name="For loop with reverse step range(5, 0, -1)",
        tags=(FEATURE_FOR_RANGE,),
        source="""for i in range(5, 0, -1):
    print(i)
""",
    ),
    ProgramCase(
        case_id="str_empty_containers",
        name="str() on empty list and tuple",
        tags=(FEATURE_LIST_LITERAL, FEATURE_TUPLE_LITERAL, FEATURE_CONTAINER_DISPLAY),
        source="""print(str([]))
print(str(()))
""",
    ),
    ProgramCase(
        case_id="fstring_scalars",
        name="f-string interpolation of int and bool",
        tags=(FEATURE_SCALAR_ARITHMETIC,),
        source="""x = 123
y = True
print(f"{x}")
print(f"{y}")
""",
    ),
    ProgramCase(
        case_id="finally_clean_exit",
        name="Try/finally with no exception raised",
        tags=(FEATURE_TRY_FINALLY,),
        source="""try:
    print("body")
finally:
    print("cleanup")
""",
    ),
    ProgramCase(
        case_id="except_exception_instance",
        name="Exception propagates through function call, caught by bare except",
        tags=(FEATURE_BASIC_EXCEPTIONS, FEATURE_FUNCTION_CALLS),
        source="""def inner():
    raise "oops"

try:
    inner()
except:
    print("caught")
""",
    ),
)


def iter_curated_cases(case_ids: set[str] | None = None) -> list[ProgramCase]:
    if not case_ids:
        return list(CURATED_CASES)
    return [case for case in CURATED_CASES if case.case_id in case_ids]
