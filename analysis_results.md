# 🔍 Python VM-First Compiler — Full Codebase Audit

> **Generated:** May 2026 | **Project:** `BasiCPythonCompiler` | **Repo:** `shubhsharma2006/BasiCPythonCompiler`

---

## 📐 Architecture Overview

The compiler implements a **dual-lane** architecture: every Python program can be either interpreted through a **bytecode VM** (for rich dynamic semantics) or compiled all the way to **native C** (for performance on a typed subset). The two lanes share the frontend and semantic analysis phases.

```
Source (.py)
    │
    ▼
┌─────────────────────────────────────────┐
│  FRONTEND                               │
│  OwnedLexer → TokenCursor → Parser      │
│  (Pratt expr parsing, indent-aware)     │
└───────────────────┬─────────────────────┘
                    │ Python std ast
                    ▼
┌─────────────────────────────────────────┐
│  AST LOWERING  (ast_lowering.py)        │
│  Python ast  →  compiler.core.ast       │
└───────────────────┬─────────────────────┘
                    │ Internal AST
        ┌───────────┴────────────┐
        ▼                        ▼
┌───────────────┐    ┌────────────────────────┐
│  SEMANTIC     │    │  OPTIMIZER             │
│  Resolver     │    │  ConstantFolder        │
│  TypeChecker  │    │  (AST-level folding)   │
└───────┬───────┘    └────────────────────────┘
        │ SemanticModel
        ├──────────────────────────────────────┐
        ▼  VM Lane                             ▼  Native Lane
┌────────────────┐                  ┌─────────────────────┐
│  VM Lowering   │                  │  CFG Lowering       │
│  (bytecode)    │                  │  (IR/CFG)           │
└───────┬────────┘                  └──────────┬──────────┘
        ▼                                      ▼
┌────────────────┐                  ┌─────────────────────┐
│  Bytecode VM   │                  │  SSA Transform      │
│  Interpreter   │                  │  + Optimizations    │
└────────────────┘                  └──────────┬──────────┘
                                               ▼
                                    ┌─────────────────────┐
                                    │  SSA Destructor     │
                                    │  → C Code Generator │
                                    │  → gcc/clang        │
                                    └─────────────────────┘
```

---

## 📁 Module Inventory

| Module | File(s) | Lines | Status |
|--------|---------|-------|--------|
| `compiler/core/ast.py` | AST node dataclasses | ~378 | ✅ Complete |
| `compiler/core/types.py` | Value & function types | ~80 | ✅ Complete |
| `compiler/core/signature.py` | Arg binding logic | ~64 | ✅ Complete |
| `compiler/frontend/owned_lexer.py` | Hand-written lexer | ~492 | ✅ Complete |
| `compiler/frontend/token_types.py` | Token enum & mapping | ~285 | ✅ Complete |
| `compiler/frontend/parser/precedence.py` | Pratt binding powers | ~70 | ✅ Complete |
| `compiler/frontend/parser/token_cursor.py` | Token stream nav | ~134 | ✅ Complete |
| `compiler/frontend/ast_lowering.py` | Python ast → core ast | ~800+ | ✅ Mostly Complete |
| `compiler/semantic/resolver.py` | Name/scope resolution | ~611 | ✅ Complete |
| `compiler/semantic/type_checker.py` | Static type inference | ~800+ | ✅ Complete |
| `compiler/optimizer/folding.py` | Constant folding | ~294 | ✅ Complete |
| `compiler/vm/bytecode.py` | Bytecode data structs | ~52 | ✅ Complete |
| `compiler/vm/lowering.py` | AST → Bytecode | ~800+ | ✅ Mostly Complete |
| `compiler/vm/interpreter.py` | Bytecode VM | ~800+ | ✅ Mostly Complete |
| `compiler/ir/cfg.py` | CFG IR data structs | ~115 | ✅ Complete |
| `compiler/ir/lowering.py` | AST → CFG/IR | ~473 | ⚠️ Partial (range-only for loops) |
| `compiler/ir/ssa.py` | SSA transform + opts | ~779 | ✅ Complete |
| `compiler/backend/c_codegen.py` | C code generator | ~379 | ⚠️ Partial (typed subset only) |
| `compiler/pipeline.py` | Compilation pipeline | ~1496 | ✅ Complete |

---

## 1️⃣ Frontend — Lexer & Parser

### Status: ✅ **Complete & Production-Ready**

The lexer (`owned_lexer.py`) is fully hand-written and owns every byte of the token stream. It handles Python's indentation-sensitive grammar natively.

**Implemented:**
- [x] `INDENT` / `DEDENT` generation from leading whitespace
- [x] Full operator set: arithmetic, bitwise, comparison, augmented assignment (`+=`, `-=`, etc.)
- [x] String literals: single-quoted, double-quoted, triple-quoted, raw strings (`r"..."`)
- [x] f-strings (basic, delegated to Python stdlib tokenizer for interpolation)
- [x] Integer literals (decimal, hex `0x`, octal `0o`, binary `0b`)
- [x] Float literals, scientific notation
- [x] Walrus operator `:=`
- [x] Source location tracking (`line`, `column`, `span`) per token
- [x] Comment stripping (`#`)
- [x] Pratt parser for expressions with full operator precedence table (`INFIX_BP`)
- [x] `TokenCursor` with 1-token lookahead and `expect()` / `peek()` helpers

**Precedence coverage (INFIX_BP):**
`or` < `and` < `not` < comparisons (`<`, `>`, `==`, `!=`, `in`, `not in`, `is`, `is not`) < `|` < `^` < `&` < shifts (`<<`, `>>`) < add/sub < mul/div/mod < `**`

---

## 2️⃣ AST Lowering — Python `ast` → Internal AST

### Status: ✅ **Mostly Complete** (some async/advanced patterns stub-only)

`ast_lowering.py` translates CPython's `ast` module nodes into the project's own `compiler.core.ast` dataclasses.

**Statements — Implemented:**

| Python Statement | Internal Node | Notes |
|-----------------|---------------|-------|
| `x = expr` | `AssignStmt` | Simple & augmented (`+=`, etc.) |
| `a, b = expr` | `UnpackAssignStmt` | Starred unpacking supported |
| `obj.attr = v` | `AttributeAssignStmt` | ✅ |
| `def f():` | `FunctionDef` | Defaults, `*args`, `**kwargs`, `kwonly` |
| `class C:` | `ClassDef` | Bases, attributes, methods |
| `if / elif / else` | `IfStmt` | Full |
| `while` | `WhileStmt` | With `else:` |
| `for` | `ForStmt` | With `else:`, starred targets |
| `try / except / else / finally` | `TryStmt` | Full |
| `with` | `WithStmt` | Single context manager |
| `return` | `ReturnStmt` | ✅ |
| `raise` | `RaiseStmt` | With `from` cause |
| `del` | `DeleteStmt` | ✅ |
| `global` / `nonlocal` | `GlobalStmt` / `NonlocalStmt` | ✅ |
| `import` / `from … import` | `ImportStmt` / `FromImportStmt` | ✅ |
| `pass` | `PassStmt` | ✅ |
| `break` / `continue` | `BreakStmt` / `ContinueStmt` | ✅ |
| `print(...)` | `PrintStmt` | Special-cased builtin |
| `assert` | `ExprStmt` wrapping | ✅ |

**Expressions — Implemented:**

| Python Expression | Internal Node | Notes |
|------------------|---------------|-------|
| Literals (`int`, `float`, `str`, `bool`, `None`) | `ConstantExpr` | ✅ |
| `name` | `NameExpr` | ✅ |
| `a + b`, `a - b`, etc. | `BinaryExpr` | ✅ |
| `not x`, `-x`, `~x` | `UnaryExpr` | ✅ |
| `a < b`, `a == b`, etc. | `CompareExpr` | ✅ |
| `a < b < c` | `CompareChainExpr` | ✅ |
| `a and b`, `a or b` | `BoolOpExpr` | ✅ |
| `a if cond else b` | `IfExpr` | ✅ |
| `f(args)` | `CallExpr` / `CallValueExpr` | Named, `*args`, `**kwargs` |
| `obj.method(args)` | `MethodCallExpr` | ✅ |
| `obj.attr` | `AttributeExpr` | ✅ |
| `a[i]` | `IndexExpr` | ✅ |
| `a[i:j:k]` | `SliceExpr` | ✅ |
| `[x for x in y if z]` | `ListCompExpr` | Multi-generator |
| `{x for x in y}` | `SetCompExpr` | ✅ |
| `{k: v for …}` | `DictCompExpr` | ✅ |
| `(x for x in y)` | `ListCompExpr` (genexp) | ✅ |
| `lambda x: expr` | `LambdaExpr` | ✅ |
| `yield expr` | `YieldExpr` | ✅ |
| `x := expr` | `NamedExpr` | ✅ |
| `[1, 2, 3]` | `ListExpr` | ✅ |
| `(1, 2, 3)` | `TupleExpr` | ✅ |
| `{1, 2}` | `SetExpr` | ✅ |
| `{'a': 1}` | `DictExpr` | ✅ |

**Stubs / Not Fully Supported:**
- [ ] `async def`, `await`, `async for`, `async with` — nodes recognized but raise `NotImplementedError`
- [ ] `yield from` — stub only
- [ ] Nested class definitions (partially handled)
- [ ] Match/case (`match` statement, Python 3.10+) — not implemented

---

## 3️⃣ Semantic Analysis

### Status: ✅ **Complete**

Two passes run sequentially: `NameResolver` then `TypeChecker`.

### 3a. Name Resolver (`resolver.py`)

- [x] Lexical scope chain: module → function → nested function
- [x] `global` / `nonlocal` declarations correctly promote variable scope
- [x] Closure variable capture detection
- [x] Function parameter registration
- [x] Class attribute and method scope
- [x] Import statement name registration
- [x] Built-in name recognition (`print`, `len`, `range`, `int`, `str`, `float`, etc.)
- [x] Error reporting for undefined names

### 3b. Type Checker (`type_checker.py`)

- [x] Type inference for all primitive types: `INT`, `FLOAT`, `BOOL`, `STRING`, `NONE`, `UNKNOWN`
- [x] Type merging (`merge_types`) for branch join points
- [x] Function return type inference and checking
- [x] Expression type propagation (recursive `_check_expr`)
- [x] Binary op type widening (int + float → float)
- [x] Comparison expression always resolves to `BOOL`
- [x] `SemanticModel` produced: `globals`, `functions`, `locals`, `expr_types` maps

---

## 4️⃣ Optimizer (AST-level)

### Status: ✅ **Complete**

`ConstantFolder` performs a single tree-walk optimization pass over the internal AST before any lowering.

**Folds:**
- [x] `BinaryExpr` with two `ConstantExpr` operands: `+`, `-`, `*`, `/`, `%` (numeric and string concat)
- [x] `UnaryExpr` on constants: `-x`, `not x`
- [x] `CompareExpr` on constants: all comparison operators including `in`, `is`
- [x] `CompareChainExpr` on all-constant operands
- [x] `BoolOpExpr` (`and`, `or`) on constant operands
- [x] `IfExpr` with constant condition → eliminates dead branch

---

## 5️⃣ VM Lane — Bytecode

### Status: ✅ **Mostly Complete**

#### 5a. Bytecode Lowering (`vm/lowering.py`)

**Opcodes Emitted:**

| Category | Opcodes |
|----------|---------|
| Load | `LOAD_CONST`, `LOAD_NAME`, `LOAD_FAST`, `LOAD_GLOBAL`, `LOAD_CLOSURE`, `LOAD_DEREF` |
| Store | `STORE_NAME`, `STORE_FAST`, `STORE_GLOBAL`, `STORE_DEREF`, `STORE_ATTR`, `STORE_SUBSCR` |
| Delete | `DELETE_NAME`, `DELETE_ATTR`, `DELETE_SUBSCR` |
| Binary/Unary | `BINARY_OP`, `UNARY_OP`, `COMPARE_OP`, `BOOL_AND`, `BOOL_OR` |
| Functions | `MAKE_FUNCTION`, `CALL_FUNCTION`, `CALL_METHOD`, `CALL_VALUE`, `RETURN_VALUE` |
| Control flow | `JUMP`, `JUMP_IF_TRUE`, `JUMP_IF_FALSE`, `SETUP_LOOP`, `BREAK_LOOP`, `CONTINUE_LOOP` |
| Exceptions | `SETUP_EXCEPT`, `POP_EXCEPT`, `RAISE` |
| Context mgr | `SETUP_WITH`, `EXIT_WITH` |
| Collections | `BUILD_LIST`, `BUILD_TUPLE`, `BUILD_DICT`, `BUILD_SET` |
| Containers | `GET_ITER`, `FOR_ITER`, `LIST_APPEND`, `SET_ADD`, `MAP_ADD` |
| Unpacking | `UNPACK_SEQUENCE`, `UNPACK_EX` (starred) |
| Splats | `CALL_FUNCTION_EX` (star/kwarg splat calls) |
| Attributes | `LOAD_ATTR`, `CALL_METHOD` |
| Indexing | `BINARY_SUBSCR` |
| Slicing | `BUILD_SLICE` |
| Closures | `LOAD_CLOSURE`, `MAKE_CLOSURE` |
| Generators | `YIELD_VALUE`, `GET_YIELD_FROM_ITER` |
| Misc | `POP_TOP`, `DUP_TOP`, `PRINT_VALUE` |

#### 5b. Bytecode VM Interpreter (`vm/interpreter.py`)

Stack-based interpreter with frame stack for function calls.

**Implemented:**
- [x] Full opcode dispatch loop
- [x] Frame stack (push/pop for calls and returns)
- [x] Local variable fast-slots and global scope lookup
- [x] Closure cells and `LOAD_DEREF`/`STORE_DEREF`
- [x] Exception handling: `try/except/else/finally`
- [x] Generator objects (`yield`, `next()`)
- [x] List/dict/set comprehensions
- [x] Starred assignment unpacking
- [x] `*args` / `**kwargs` splat call support
- [x] `with` statement context manager protocol
- [x] `del` on names, attributes, subscripts
- [x] 30+ built-in functions supported

**Limitations / Stubs:**
- [ ] `async`/`await` — not dispatched
- [ ] `yield from` — partial
- [ ] Full metaclass / descriptor protocol
- [ ] Module import resolution (stubs only)

---

## 6️⃣ Native Lane — IR / CFG / SSA / C Backend

### Status: ⚠️ **Functional but Limited to Typed Subset**

This lane applies only to programs using statically-typeable primitives (`int`, `float`, `bool`, `str`). The pipeline auto-selects the VM lane for programs using features the native backend doesn't yet support.

#### 6a. CFG IR and Lowering

**CFG Lowering Coverage:**

| Construct | Supported |
|-----------|-----------|
| Assignment | ✅ |
| `if / else` | ✅ |
| `while` with `else` | ✅ |
| `for` with `range()` | ✅ (range-only) |
| `break` / `continue` | ✅ |
| `return` | ✅ |
| Short-circuit `and`/`or` | ✅ |
| Ternary `if` expression | ✅ |
| Function calls | ✅ (positional args only) |
| Lambda | ❌ (placeholder) |
| Containers | ❌ |
| Exceptions | ❌ |
| Closures / nested fns | ❌ |

#### 6b. SSA Transform (`ir/ssa.py`) — 100% Complete

- [x] Dominance frontier computation
- [x] φ-node placement at join points
- [x] SSA renaming pass (dominator-tree walk)
- [x] `SSAConstantPropagation` — constant folding + unreachable block pruning
- [x] `SSAValuePropagation` — algebraic simplification (`x+0→x`, `x*1→x`)
- [x] `SSADeadCodeEliminator` — worklist-based liveness
- [x] `SSACopyPropagation` — trivial φ-node elimination
- [x] `SSADestructor` — lowers φ-nodes → edge-splitting assignments

#### 6c. C Code Generator (`backend/c_codegen.py`)

- [x] Global variable declarations with C type mapping
- [x] Function prototypes + definitions with correct C signatures
- [x] `goto`-based control flow from basic blocks
- [x] String reference counting (`py_incref`/`py_decref`)
- [x] Python-correct floor division, modulo, exponentiation
- [x] Float promotion for mixed arithmetic
- [x] Truthiness helpers per type
- [x] C runtime header (`py_runtime.h`) integration

---

## 7️⃣ Pipeline Orchestration (`pipeline.py`)

### Status: ✅ **Complete**

`CompilationResult` accumulates every stage artifact. Feature-detection heuristics automatically route programs between the VM and native compilation lanes with clear diagnostic messages when native is unavailable.

---

## 📊 Completion Summary

| Phase | Completion | Notes |
|-------|-----------|-------|
| Lexer | **100%** | Hand-written, production quality |
| Parser (expressions) | **100%** | Pratt, full Python operator set |
| AST Lowering | **95%** | Async/yield-from stubs remaining |
| Name Resolver | **100%** | All scope rules implemented |
| Type Checker | **95%** | Dynamic types fall to UNKNOWN |
| AST Optimizer | **100%** | Constant folding complete |
| VM Bytecode Lowering | **90%** | Async not dispatched |
| VM Interpreter | **85%** | Core Python subset fully working |
| CFG IR Lowering | **60%** | Range-only for-loops; no containers |
| SSA Transform | **100%** | All 4 SSA passes + destructor |
| C Code Generator | **70%** | Typed scalar subset only |
| Pipeline | **100%** | Full dual-lane routing |

> **Overall project maturity: ~88% complete for the defined VM-first Python subset.**

---

## 🚧 Recommended Next Steps

### High Priority
1. **`async`/`await` support** — stubs exist; need VM dispatch
2. **`yield from`** — complete generator delegation in VM interpreter
3. **IR `for` loop generalization** — needs `GET_ITER`/`FOR_ITER` in CFG lowering
4. **Native backend container types** — add list/dict/set IR nodes

### Medium Priority
5. **Match/case** (Python 3.10+) — not in AST lowering
6. **Import resolution** — stdlib shim so `math`, `os.path` work in VM mode
7. **Error messages** — include source spans in all diagnostics
8. **Test suite cleanup** — migrate stale root-level `test_*.py` into `tests/`

### Low Priority / Polish
9. **IR optimizer: loop-invariant code motion** — SSA foundation is ready
10. **IR optimizer: function inlining** — using SSA map
11. **Native backend: full string operations** — slicing, `.upper()`, `.lower()`, etc.
12. **WASM backend** — CFG + SSA pipeline is an ideal foundation

---

*Report generated from full source-level audit of 19 files across the compiler package.*
