# Mini Python Compiler

A complete **7-stage compiler pipeline** that translates a Python-like language
into runnable C code, with an optimizer and AST visualisation.

```
Source (.py)  →  Tokens  →  AST  →  Semantic Check  →  Optimize  →  IR  →  output.c  →  executable
```

---

## Quick Start

```bash
# 1. Install dependencies
pip3 install ply graphviz
brew install graphviz          # macOS (for AST diagram PNG)

# 2. Run the built-in demo
python3 main.py

# 3. Compile a source file
python3 main.py test_input.py

# 4. Compile AND auto-run via GCC
python3 main.py test_input.py --run

# 5. Skip the AST diagram
python3 main.py test_input.py --no-viz --run

# 6. Manually compile the generated C
gcc output.c -o output -lm && ./output
```

---

## Project Structure

```
compiler project/
├── lexer.py            Stage 1 — Tokenizer (PLY lex + token filter)
├── parser.py           Stage 2 — LALR(1) Parser → AST (PLY yacc)
├── ast_nodes.py        Stage 3 — AST node class definitions
├── semantic.py         Stage 4 — Scoped symbol table + validation
├── optimizer.py        Stage 5 — Constant folding + dead code removal
├── ir.py               Stage 6 — Three-address code (3AC) generator
├── codegen.py          Stage 7 — C code emitter
├── ast_viz.py          Bonus  — Graphviz AST diagram generator
├── main.py             Entry point — runs the full pipeline
├── test_input.py       Test: all features combined
├── test_functions.py   Test: function definitions & calls
├── test_control_flow.py Test: if/else, while, comparisons
├── test_optimizer.py   Test: constant folding & dead code
├── output.c            Generated C code (auto-created)
├── ast_output.png      AST diagram (auto-created)
└── README.md
```

---

## Language Features

| Feature                  | Syntax                           | Example                        |
|--------------------------|----------------------------------|--------------------------------|
| Variable assignment      | `name = expr`                    | `x = 10`                      |
| Arithmetic               | `+ - * / %`                      | `result = a + b * 2`          |
| Operator precedence      | Standard math rules              | `2 + 3 * 4 → 14`             |
| Parenthesised grouping   | `(expr)`                         | `(2 + 3) * 4 → 20`           |
| Comparisons              | `== != < > <= >=`                | `if x > 5 { ... }`           |
| Unary minus              | `-expr`                          | `y = -x`                      |
| If / else                | `if cond { ... } else { ... }`   | See below                     |
| While loops              | `while cond { ... }`             | See below                     |
| Function definitions     | `def name(params) { ... }`       | `def add(a, b) { return a+b }`|
| Function calls           | `name(args)`                     | `result = add(1, 2)`          |
| Return                   | `return expr`                    | `return x * 2`                |
| Print (numbers)          | `print(expr)`                    | `print(total)`                |
| Print (strings)          | `print("text")`                  | `print("hello world")`        |
| Float literals           | `3.14`                           | `pi = 3.14`                   |
| Comments                 | `# comment`                      | `# this is ignored`           |

### Example Program

```python
# Factorial using a while loop
def factorial(n) {
    result = 1
    while n > 1 {
        result = result * n
        n = n - 1
    }
    return result
}

x = factorial(5)
print(x)
print("done!")
```

---

## Pipeline Overview

### Stage 1 — Lexer (PLY lex)
Reads source character by character → flat token stream.
Includes a **token filter** that cleans up newlines around braces
and `else` keywords so the parser grammar stays simple.

### Stage 2 — Parser (PLY yacc / LALR)
Consumes tokens → builds a hierarchical AST.
Operator precedence handled by PLY's precedence table.

### Stage 3 — Semantic Analysis
Walks the AST with a **scoped symbol table** (stack of scopes).
Checks: undefined variables, undefined functions, parameter count mismatches.

### Stage 4 — Optimizer
**Constant folding**: `2 + 3 * 4` → `14` at compile time.
**Dead code elimination**: statements after `return` are dropped.

### Stage 5 — IR Generation (Three-Address Code)
Converts AST into flat instructions with structured markers for
control flow. Example:
```
t1 = a + b
total = t1
t2 = x > 10
IF t2 {
  PRINT x
} ELSE {
  PRINT 0.0
}
```

### Stage 6 — C Code Generation
Translates IR → valid C source file with:
- `#include <stdio.h>` / `<math.h>`
- Forward declarations for user functions
- All variables declared as `double`
- `print()` → `printf("%g\n", ...)`
- Structured `if/else`, `while` blocks

### Bonus — AST Visualisation (Graphviz)
Renders a colour-coded PNG diagram of the AST tree.
Node types get distinct shapes and colours:
- **Diamond** = if/while, **Box3D** = function, **Ellipse** = operators
- **Circle** = literals/variables, **Note** = strings

---

## Output Files

| File             | Description                              |
|------------------|------------------------------------------|
| `output.c`       | Generated C source (always produced)     |
| `ast_output.png` | AST tree diagram (when graphviz present) |

---

## Note on VS Code Warnings

The test files (`.py`) use our **mini-language syntax** (brace-delimited blocks),
not standard Python. VS Code's Python linter will flag them as syntax errors —
**this is expected and harmless**. The files compile correctly through our compiler.

---

## Test Suite

Run all tests with `--run` to auto-compile and execute:

```bash
python3 main.py test_input.py --run --no-viz
python3 main.py test_functions.py --run --no-viz
python3 main.py test_control_flow.py --run --no-viz
python3 main.py test_optimizer.py --run --no-viz
```
