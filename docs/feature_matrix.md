# Feature Matrix

This file is the current capability contract for the compiler project.

Legend:

- `✅` supported
- `⚠️` partial or restricted support
- `❌` unsupported

Scope notes:

- `Parser` means the feature is accepted by the active frontend pipeline.
- The project currently has two frontend lanes:
  - `cpython` frontend: default for VM execution and native compilation
  - `owned` frontend: default for `--check`; parity is improving but should not be assumed for every feature unless tested
- `Native` means `compile_source(...)` / `--compile-native` / `--run-native`
- `Tested` means there is automated coverage in the current test suite

## Core Control Flow

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Assignments | ✅ | ✅ | ✅ | ✅ | Basic variable assignment works in both lanes |
| Augmented assignment | ✅ | ✅ | ✅ | ✅ | Covered in existing arithmetic/control-flow tests |
| `if` / `elif` / `else` | ✅ | ✅ | ✅ | ✅ | Core control flow is supported in both lanes |
| `while` | ✅ | ✅ | ✅ | ✅ | Supported in both lanes |
| `for` over `range(...)` | ✅ | ✅ | ⚠️ | ✅ | Native lane supports `range(...)` lowering, not general iterator-based `for` |
| `break` | ✅ | ✅ | ✅ | ✅ | Native `try/finally` + `break` is now covered |
| `continue` | ✅ | ✅ | ✅ | ✅ | Native `try/finally` + `continue` is now covered |
| `pass` | ✅ | ✅ | ✅ | ✅ | Supported in both lanes |
| Forward references | ✅ | ✅ | ✅ | ✅ | Function forward references covered |
| Recursion | ✅ | ✅ | ✅ | ✅ | Covered by VM and integration tests |

## Functions And Calls

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Function definitions | ✅ | ✅ | ✅ | ✅ | Core feature in both lanes |
| Function calls | ✅ | ✅ | ✅ | ✅ | Positional calls supported in both lanes |
| Returns | ✅ | ✅ | ✅ | ✅ | Native return behavior is tested, including `try/finally` override |
| Default arguments | ✅ | ✅ | ❌ | ✅ | Native path rejects default/keyword arguments |
| Keyword arguments | ✅ | ✅ | ❌ | ✅ | Explicit native guard |
| Keyword-only parameters | ✅ | ✅ | ❌ | ✅ | VM supports; native rejects |
| `*args` | ✅ | ✅ | ❌ | ✅ | VM supports; native rejects |
| `**kwargs` | ✅ | ✅ | ❌ | ✅ | VM supports; native rejects, including call-site `**kwargs` splats |
| Nested functions | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects nested functions |
| Closures / captured variables | ✅ | ✅ | ❌ | ✅ | VM supports closure capture; native does not |
| `global` / `nonlocal` | ✅ | ✅ | ❌ | ✅ | Native rejects global/nonlocal mutation |
| Lambda | ✅ | ✅ | ❌ | ✅ | VM tier-2 support exists; native is not a supported target |

## Data And Containers

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Integers / floats / bools / strings | ✅ | ✅ | ✅ | ✅ | Shared core literal support |
| Lists | ✅ | ✅ | ⚠️ | ✅ | Native supports homogeneous primitive-element literals, indexing, slicing, truthiness, equality, membership, and display |
| Tuples | ✅ | ✅ | ⚠️ | ✅ | Native supports homogeneous primitive-element literals, indexing, slicing, truthiness, equality, membership, and display |
| Dicts | ✅ | ✅ | ❌ | ✅ | VM supported; native unsupported |
| Sets | ✅ | ✅ | ❌ | ✅ | VM supported; native unsupported |
| Indexing | ✅ | ✅ | ⚠️ | ✅ | Native supports strings and homogeneous primitive list/tuple indexing |
| Slicing | ✅ | ✅ | ⚠️ | ✅ | Native supports strings plus homogeneous primitive list/tuple slicing with constant non-zero step |
| `len(...)` | ✅ | ✅ | ⚠️ | ✅ | Native supports `len()` on strings, lists, and tuples |
| Flat unpack assignment | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects unpacking |
| Starred unpack assignment | ✅ | ✅ | ❌ | ✅ | VM supported; native unsupported |
| `del` on names/subscripts | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects delete |
| Comprehensions | ✅ | ✅ | ❌ | ✅ | VM supported; native unsupported |
| Generator expressions | ✅ | ✅ | ❌ | ✅ | VM supported; native rejects generators |

## Operators And Expressions

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Arithmetic `+ - * / %` | ✅ | ✅ | ✅ | ✅ | Core support in both lanes |
| Floor division `//` | ✅ | ✅ | ⚠️ | ✅ | Native supports but rejects mixed int/float edge cases |
| Power `**` | ✅ | ✅ | ⚠️ | ✅ | Native supports but rejects negative integer exponents and mixed int/float edge cases |
| Boolean `and/or/not` | ✅ | ✅ | ✅ | ✅ | Short-circuit behavior tested |
| Comparisons `== != < <= > >=` | ✅ | ✅ | ✅ | ✅ | Core comparison support works |
| Comparison chaining | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects chained comparisons |
| Membership `in` / `not in` | ✅ | ✅ | ⚠️ | ✅ | Native supports homogeneous primitive-element list/tuple membership; other cases remain restricted |
| Identity `is` / `is not` | ✅ | ✅ | ⚠️ | ✅ | VM supports; native should be treated as limited unless proven beyond current subset |
| Ternary `a if cond else b` | ✅ | ✅ | ✅ | ✅ | Tier-2 and lowering support exist |
| Walrus `:=` | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects walrus |
| f-strings | ✅ | ✅ | ⚠️ | ✅ | VM supports; native depends on lowered string/runtime subset and should be treated as limited |

## Exceptions And Control Transfer

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| `raise` | ✅ | ✅ | ✅ | ✅ | Native runtime/error path exists |
| Bare `raise` in `except` | ✅ | ✅ | ✅ | ✅ | Invalid usage also has rejection tests |
| Basic `try/except` | ✅ | ✅ | ✅ | ✅ | Native support is covered |
| Typed `except SomeError` | ✅ | ✅ | ✅ | ✅ | Native typed handlers are covered |
| `except ... as err` binding | ✅ | ✅ | ✅ | ✅ | Covered in VM and native path tests |
| `try/finally` | ✅ | ✅ | ⚠️ | ✅ | Native supports key cases, but treat as restricted while feature surface is still narrow |
| `try/except/else` | ✅ | ✅ | ✅ | ✅ | VM supports |
| `try/except/else/finally` | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects this combined form |
| `raise ... from ...` | ✅ | ✅ | ❌ | ✅ | VM supports; native should be treated as unsupported |

## Objects And Classes

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Class definitions | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects classes/attributes/methods |
| Instance attributes | ✅ | ✅ | ❌ | ✅ | VM supported |
| Methods | ✅ | ✅ | ❌ | ✅ | VM supported |
| `__init__` | ✅ | ✅ | ❌ | ✅ | VM supported |
| Inheritance | ✅ | ✅ | ❌ | ✅ | VM supported |
| `super()` | ✅ | ✅ | ❌ | ✅ | VM supported |
| Decorators | ✅ | ✅ | ❌ | ✅ | VM supports function/class decorators; native should be treated as unsupported |

## Modules And Context Management

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| Local `import` | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects imports |
| `from ... import ...` | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects imports |
| Relative imports | ✅ | ✅ | ❌ | ✅ | VM supported |
| Star imports | ✅ | ✅ | ❌ | ✅ | VM supported |
| Stdlib import fallback | ✅ | ✅ | ❌ | ✅ | VM uses host `importlib` fallback |
| `with` statement | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects `with` |
| Multiple context managers in one `with` | ✅ | ✅ | ❌ | ✅ | VM lowering currently handles chained items; native unsupported through `with` rejection |

## Builtins And Output

| Feature | Parser | VM | Native | Tested | Notes |
|---|---|---:|---:|---:|---|
| `print(x)` | ✅ | ✅ | ✅ | ✅ | Native now prints supported homogeneous primitive list/tuple values too |
| Multi-argument `print(...)` | ✅ | ✅ | ❌ | ✅ | Native explicitly rejects VM-only builtin behavior |
| `print(sep=..., end=...)` | ✅ | ✅ | ❌ | ✅ | VM supported; native unsupported |
| `range(...)` | ✅ | ✅ | ⚠️ | ✅ | Native support is tied to `for range(...)` lowering, not full iterator parity |
| `sorted`, `abs`, `str`, `repr`, `ascii` | ✅ | ✅ | ⚠️ | ✅ | Native supports `str()` on scalars plus `str()`/`repr()` on supported homogeneous list/tuple values; `ascii()` stays unsupported |

## Native Lane Summary

### Native is currently strong at

- arithmetic
- simple control flow
- direct function calls
- basic `try/except`
- typed handlers
- important `try/finally` control-transfer cases
- homogeneous primitive list/tuple literals, indexing, slicing, `len()`, truthiness, equality, membership, and display
- CFG / SSA / cleanup infrastructure

### Native is currently missing or intentionally restricted for

- imports and multi-file execution
- closures and nested functions
- generators
- dicts, sets, and general container parity
- dynamic-step slicing and unpacking
- delete / global / nonlocal / `with`
- classes and object model features
- default/keyword/variadic call signatures
- combined `try/except/else/finally`

## Recommended Update Discipline

Whenever a feature changes:

1. update this matrix
2. update the README
3. add or adjust tests in `tests/`
4. if native support changes, update the feature gates in `compiler/pipeline/feature_gates.py`
