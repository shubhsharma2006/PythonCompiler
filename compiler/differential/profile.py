from __future__ import annotations

from dataclasses import dataclass


FEATURE_SCALAR_ARITHMETIC = "scalar_arithmetic"
FEATURE_IF_WHILE = "if_while"
FEATURE_FOR_RANGE = "for_range"
FEATURE_FUNCTION_CALLS = "function_calls"
FEATURE_BASIC_EXCEPTIONS = "basic_exceptions"
FEATURE_TRY_FINALLY = "try_finally"
FEATURE_LIST_LITERAL = "list_literal"
FEATURE_TUPLE_LITERAL = "tuple_literal"
FEATURE_INDEXING = "indexing"
FEATURE_SLICING = "slicing"
FEATURE_LEN = "len"
FEATURE_TRUTHINESS = "truthiness"
FEATURE_EQUALITY = "equality"
FEATURE_MEMBERSHIP = "membership"
FEATURE_CONTAINER_DISPLAY = "container_display"

PROFILE_FEATURES = (
    FEATURE_SCALAR_ARITHMETIC,
    FEATURE_IF_WHILE,
    FEATURE_FOR_RANGE,
    FEATURE_FUNCTION_CALLS,
    FEATURE_BASIC_EXCEPTIONS,
    FEATURE_TRY_FINALLY,
    FEATURE_LIST_LITERAL,
    FEATURE_TUPLE_LITERAL,
    FEATURE_INDEXING,
    FEATURE_SLICING,
    FEATURE_LEN,
    FEATURE_TRUTHINESS,
    FEATURE_EQUALITY,
    FEATURE_MEMBERSHIP,
    FEATURE_CONTAINER_DISPLAY,
)

PROFILE_EXCLUSIONS = (
    "imports",
    "closures",
    "nested_functions",
    "generators",
    "dicts",
    "sets",
    "classes",
    "keyword_default_variadic_calls",
    "with",
    "unpacking",
    "del",
    "global_nonlocal",
)


@dataclass(frozen=True)
class DifferentialProfile:
    name: str
    description: str
    features: tuple[str, ...]
    exclusions: tuple[str, ...]


def current_native_profile() -> DifferentialProfile:
    return DifferentialProfile(
        name="native_subset_v1",
        description=(
            "Initial VM/native differential subset for the current native lane: "
            "scalars, control flow, positional functions, basic exceptions, "
            "and homogeneous primitive list/tuple semantics."
        ),
        features=PROFILE_FEATURES,
        exclusions=PROFILE_EXCLUSIONS,
    )
