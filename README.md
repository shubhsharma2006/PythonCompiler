# Python VM-First Compiler

This repository currently has two execution lanes:

- a VM-first execution path that is the semantic source of truth for the supported language surface
- a narrower native path that lowers to C and links against a runtime library

The active pipeline is rooted in `compiler/`.

```text
Python source -> lexer -> parser -> CST -> AST lowering -> semantic analysis -> bytecode VM
                                                      \-> optimization -> IR -> C -> executable
```

The project is no longer best described as "compile-to-C only". The supported language grows on the VM path first; the native path is intentionally conservative until runtime semantics are broader and more stable.

## Current VM-supported surface

- Integer, float, bool, and string literals
- Variable assignment and augmented assignment
- Arithmetic: `+`, `-`, `*`, `/`, `%`
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`, `is`, `is not`
- Boolean expressions: `and`, `or`, `not`
- `if` / `elif` / `else`
- `while`
- `for` loops over `range(...)`
- `pass`, `break`, and `continue`
- Top-level function definitions, calls, returns, recursion, and forward references
- Function default arguments and keyword calls on the VM path
- Nested functions with closure capture and `nonlocal` mutation
- `global` declarations for module-scope mutation from functions
- List, tuple, dict, and set literals
- Indexing for lists, tuples, strings, and dicts
- Slicing for lists, tuples, and strings
- Flat tuple/list unpacking assignment like `a, b = value`
- `del` for names and subscript targets
- `len(...)` for lists, tuples, strings, dicts, and sets
- Top-level classes with instance fields, attributes, methods, and `__init__`
- Local module imports via `import name` and `from name import symbol`
- Standard-library import fallback through host `importlib` on the VM path
- Dotted imports such as `import os.path`
- Single-item `with` statements and context managers
- `raise`, `try/except`, `try/finally`, and named typed handlers like `except MyError as err`
- Multi-argument `print(...)` with `sep=` and `end=`
- f-strings lowered through the frontend
- A growing builtin registry including `print`, `len`, `range`, `str`, `repr`, `ascii`, `sorted`, `abs`, and common Python builtins

## Current native path

- Single-file compilation only
- Primitive arithmetic / control-flow subset
- CFG + SSA optimization passes
- Separate emitted runtime artifacts: generated C plus `py_runtime.h` / `py_runtime.c`

The native path still rejects:
- imports and multi-file execution
- closures and nested functions
- exceptions
- `for` loops
- list/tuple/dict/set runtime features
- slicing, unpacking assignment, delete, and global/nonlocal mutation
- `with` statements
- classes, attributes, and methods
- default arguments and keyword calls
- VM-only builtin behaviors like multi-argument `print(...)`

## Explicitly unsupported today

- decorators
- positional-only parameters, keyword-only parameters, `*args`, and `**kwargs`
- comprehensions
- generators / `yield`
- multiple context managers in one `with` statement
- starred unpacking assignment
- attribute deletion
- full Python runtime semantics

Unsupported features fail compilation with structured diagnostics.

## Usage

```bash
# Install in editable mode
pip install -e .

# Run through the VM (default)
python3 main.py test_input.py

# Check only
python3 main.py test_input.py --check

# Compile to native C artifacts
python3 main.py test_input.py --compile-native

# Compile and run natively
python3 main.py test_booleans.py --run --no-viz

# Quiet mode for automation
python3 main.py test_input.py --compile-native --no-viz -q

# Debug dumps
python3 main.py test_input.py --dump tokens
python3 main.py test_input.py --dump bytecode
python3 main.py test_input.py --compile-native --dump ir

# Module / installed entrypoint
python3 -m compiler test_input.py
python-subset-compiler test_input.py
```

The `--no-viz` flag is kept for CLI compatibility but AST visualization is no longer part of the active architecture.

Generated artifacts like `output.c`, `py_runtime.c`, and `py_runtime.h` are build outputs, not source-of-truth files.

## Project shape

- `main.py`: compatibility entrypoint
- `compiler/frontend`: source handling, lexer, parser, CST, and AST lowering
- `compiler/semantic`: symbol collection, binding resolution, type checking, and control-flow checks
- `compiler/vm`: bytecode lowering and VM execution
- `compiler/vm/objects.py`: runtime-facing VM object/value helpers
- `compiler/vm/builtins.py`: builtin registry for the VM path
- `compiler/vm/errors.py`: VM runtime error and unwind signals
- `compiler/optimizer`: safe AST-level folding
- `compiler/ir`: CFG-based lowering with explicit basic blocks and branch terminators
- `compiler/backend`: native C code generation
- `compiler/runtime`: emitted native runtime support files
- `compiler/cli`: command-line entrypoint
- `run_tests.py`: integration and negative test suite

## Test suite

Run unit and integration coverage with:

```bash
python3 -m unittest discover -s tests -v
python3 run_tests.py
```

The suite covers:

- successful compilation and execution for valid subset programs
- VM execution for the current language surface
- direct VM runtime helper coverage
- VM execution for `for` loops over `range(...)`
- VM execution for list/tuple/dict/set literals, indexing, slicing, unpacking, deletion, and `len(...)`
- VM execution for top-level classes, attributes, and methods
- VM execution for local imports, stdlib import fallback, closures, `global`/`nonlocal`, `with`, typed/untyped exceptions, `try/finally`, and multi-argument print
- short-circuit correctness
- forward references and recursion
- compile-time rejection of unsupported syntax and mixed invalid operations
- CLI VM and native modes

GitHub Actions CI is defined in `.github/workflows/ci.yml` and runs both suites on Python 3.10 and 3.11.
