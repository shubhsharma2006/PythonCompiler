"""
main.py — Mini Python Compiler — Full Pipeline Entry Point
============================================================
Pipeline:  Source → Tokens → AST → Semantic → Optimize → IR → C Code

Usage:
    python3 main.py test_input.py            # compile a file
    python3 main.py test_input.py --run       # compile + execute via gcc
    python3 main.py                            # run built-in demo
    python3 main.py test_input.py --no-viz     # skip AST diagram
    python3 main.py test_input.py -o out.c     # custom output filename
    python3 main.py --help                     # show all options
"""

import sys
import os
import argparse
import subprocess

from lexer     import tokenize
from parser    import parse
from semantic  import SemanticAnalyser, SemanticError
from optimizer import Optimizer
from ir        import IRGenerator
from codegen   import CodeGenerator

try:
    from ast_viz import visualise_ast
    GRAPHVIZ_OK = True
except ImportError:
    GRAPHVIZ_OK = False

# ── ANSI helpers ───────────────────────────────────────────────

R  = '\033[0m'
B  = '\033[1m'
CY = '\033[96m'
GR = '\033[92m'
YL = '\033[93m'
RD = '\033[91m'
MG = '\033[95m'
BL = '\033[94m'
DM = '\033[2m'

def hdr(title, quiet=False):
    if quiet:
        return
    bar = '─' * 60
    print(f'\n{B}{CY}┌{bar}┐')
    print(f'│  {title:<58}│')
    print(f'└{bar}┘{R}')

def ok(m, quiet=False):
    if not quiet:
        print(f'  {GR}✔{R} {m}')
def warn(m, quiet=False):
    if not quiet:
        print(f'  {YL}⚠{R} {m}')
def err(m):
    print(f'  {RD}✘{R} {m}')


# ── Demo source ───────────────────────────────────────────────

DEMO = """\
# --- Mini Python Compiler Demo ---

# Arithmetic & variables
x = 10
y = 3
total = x + y
print(total)

# Operator precedence (2 + 3*4 = 14)
result = 2 + 3 * 4
print(result)

# Function definition & call
def add(a, b) {
    return a + b
}

sum = add(x, y)
print(sum)

# If / elif / else
if x > 100 {
    print(0)
} elif x > 5 {
    print(x)
} else {
    print(1)
}

# Augmented assignment
counter = 10
counter += 5
counter -= 2
print(counter)

# While loop
i = 3
while i > 0 {
    print(i)
    i -= 1
}

# Constant folding (optimizer computes at compile time)
folded = 10 + 20 * 3 - 5
print(folded)

print("Compilation complete!")
"""


# ── Compiler pipeline ─────────────────────────────────────────

def compile_source(source, viz=True, run=False, output='output.c', quiet=False):
    """Run the full compilation pipeline. Returns generated C code string."""

    # Stage 1: Lexer
    hdr('STAGE 1 — Lexical Analysis', quiet)
    try:
        tokens = tokenize(source)
    except Exception as e:
        err(f'Lexer error: {e}'); sys.exit(1)

    if not quiet:
        for t in tokens:
            if t.type != 'NEWLINE':
                print(f'  {BL}{t.type:<12}{R} {t.value!r:<20} line {t.lineno}')
    ok(f'{len(tokens)} tokens', quiet)

    # Stage 2: Parser → AST
    hdr('STAGE 2 — Parsing → AST', quiet)
    try:
        ast = parse(source)
    except SyntaxError as e:
        err(f'Parse error: {e}'); sys.exit(1)
    if not quiet:
        print(f'{MG}{ast}{R}')
    ok('AST built.', quiet)

    # Stage 3: Semantic analysis
    hdr('STAGE 3 — Semantic Analysis', quiet)
    try:
        sa = SemanticAnalyser()
        sa.analyse(ast)
    except SemanticError as e:
        err(f'Semantic error: {e}'); sys.exit(1)
    ok('No semantic errors.', quiet)
    ok(f'Variables: {sorted(sa.defined_vars)}', quiet)
    if sa.symbols.functions:
        ok(f'Functions: {list(sa.symbols.functions.keys())}', quiet)

    # Stage 4: Optimizer
    hdr('STAGE 4 — Optimization', quiet)
    opt = Optimizer()
    ast = opt.optimize(ast)
    ok(f'{opt.folded_count} constant(s) folded.', quiet)
    if opt.removed_count:
        ok(f'{opt.removed_count} dead statement(s) removed.', quiet)

    # Stage 5: IR
    hdr('STAGE 5 — Intermediate Representation', quiet)
    ir_gen = IRGenerator()
    instrs = ir_gen.generate(ast)
    if not quiet:
        for i in instrs:
            print(f'  {YL}{i}{R}')
    ok(f'{len(instrs)} IR instructions.', quiet)

    # Stage 6: Code generation
    hdr('STAGE 6 — C Code Generation', quiet)
    cgen = CodeGenerator()
    c_code = cgen.generate(instrs)
    if not quiet:
        print(f'{GR}{c_code}{R}')

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output)
    with open(out_path, 'w') as f:
        f.write(c_code + '\n')
    ok(f'Saved → {out_path}', quiet)

    # Bonus: AST viz
    if viz and GRAPHVIZ_OK and not quiet:
        hdr('BONUS — AST Visualisation')
        img = visualise_ast(ast, filename='ast_output', fmt='png')
        if img:
            ok(f'AST diagram → {img}')

    # Build & run
    hdr('BUILD & RUN', quiet)
    ok('Compile:  gcc output.c -o output -lm', quiet)
    ok('Run:      ./output', quiet)

    if run:
        if not quiet:
            print(f'\n{B}--- Compiling with GCC ---{R}')
        rc = subprocess.run(
            ['gcc', out_path, '-o', 'output', '-lm'],
            capture_output=True, text=True
        )
        if rc.returncode != 0:
            err(f'GCC failed:\n{rc.stderr}')
        else:
            ok('Compiled successfully.', quiet)
            if not quiet:
                print(f'\n{B}--- Program Output ---{R}')
            result = subprocess.run(['./output'], capture_output=True, text=True)
            if not quiet:
                print(result.stdout)
            if result.returncode != 0:
                warn(f'Exit code: {result.returncode}', quiet)
            return c_code, result.stdout.strip()

    return c_code, None


# ── Entry point ────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog='mini-python-compiler',
        description='Mini Python Compiler — translates Python-like code to C',
    )
    ap.add_argument('file', nargs='?', default=None,
                    help='Source file to compile (omit for built-in demo)')
    ap.add_argument('-o', '--output', default='output.c',
                    help='Output C filename (default: output.c)')
    ap.add_argument('--run', action='store_true',
                    help='Auto-compile with GCC and run the output')
    ap.add_argument('--no-viz', action='store_true',
                    help='Skip Graphviz AST diagram')
    ap.add_argument('-q', '--quiet', action='store_true',
                    help='Minimal output (used by test runner)')
    args = ap.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            err(f'File not found: {args.file!r}'); sys.exit(1)
        with open(args.file) as f:
            source = f.read()
        if not args.quiet:
            print(f'\n{B}Compiling: {args.file}{R}')
    else:
        if not args.quiet:
            print(f'\n{B}No file specified — running built-in demo.{R}')
        source = DEMO

    if not args.quiet:
        hdr('SOURCE CODE')
        for i, line in enumerate(source.splitlines(), 1):
            print(f'  {i:3}  {line}')

    compile_source(
        source,
        viz=not args.no_viz,
        run=args.run,
        output=args.output,
        quiet=args.quiet
    )


if __name__ == '__main__':
    main()
