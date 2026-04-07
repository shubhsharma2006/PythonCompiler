#!/usr/bin/env python3
"""
run_tests.py — Automated Test Runner
======================================
Compiles each test file, runs the generated C, and compares output
against expected values. Reports pass/fail with a summary.

Usage:
    python3 run_tests.py           # run all tests
    python3 run_tests.py -v        # verbose (show compiler output)
"""

import subprocess
import sys
import os

# ── Test definitions: (file, expected_output_lines) ────────────

TESTS = [
    {
        'name': 'Arithmetic & Basic Features',
        'file': 'test_input.py',
        'expected': [
            '14', '6', '40', '2.5',        # a+b, a-b, a*b, a/b
            '14', '20',                     # precedence, grouping
            '25', '30',                     # square(5), add(10,20)
            '42',                           # if x>10
            '3', '2', '1',                  # while countdown
            '600',                          # constant folding
            'All tests passed!',
        ],
    },
    {
        'name': 'Function Definitions & Calls',
        'file': 'test_functions.py',
        'expected': [
            '42',                           # multiply(6,7)
            '17',                           # add(multiply(3,4), 5)
            '16',                           # compute(2,3,10)
            '15',                           # multiply(2+3, 4-1)
            'Functions test done!',
        ],
    },
    {
        'name': 'Control Flow (if/else/while)',
        'file': 'test_control_flow.py',
        'expected': [
            '1',                            # if x>10
            '2',                            # else branch
            '3',                            # nested if/else
            '15',                           # sum 1..5
            '4',                            # a == b
            '5',                            # a != 20
            'Control flow test done!',
        ],
    },
    {
        'name': 'Optimizer (Constant Folding)',
        'file': 'test_optimizer.py',
        'expected': [
            '5', '50', '70', '25', '50',   # folded constants
            '13',                           # x + 2*3 (partial fold)
            '1', '1',                       # comparison folding
            '42',                           # dead code func
            'Optimizer test done!',
        ],
    },
    {
        'name': 'Advanced Features (elif, +=, nested)',
        'file': 'test_advanced.py',
        'expected': [
            '15',                           # counter += 5
            '13',                           # counter -= 2
            '26',                           # counter *= 2
            '13',                           # counter /= 2
            'medium',                       # elif branch
            '55',                           # sum 1..10 via while + +=
            '120',                          # factorial(5) recursive
            'Advanced tests passed!',
        ],
    },
]

# ── ANSI colours ───────────────────────────────────────────────

GR = '\033[92m'; RD = '\033[91m'; YL = '\033[93m'; CY = '\033[96m'
B  = '\033[1m';  R  = '\033[0m';  DM = '\033[2m'

# ── Test runner ────────────────────────────────────────────────

def run_test(test, verbose=False):
    """Compile a test file, run the output, check against expected."""
    name = test['name']
    src  = test['file']
    expected = test['expected']

    if not os.path.exists(src):
        print(f'  {RD}✘ SKIP{R}  {name} — file {src!r} not found')
        return False

    # Step 1: compile via our compiler
    cmd = [sys.executable, 'main.py', src, '--run', '--no-viz', '-q']
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  {RD}✘ FAIL{R}  {name} — compiler error')
        if verbose:
            print(f'    {DM}{result.stderr.strip()}{R}')
        return False

    # Step 2: run the compiled binary
    run = subprocess.run(['./output'], capture_output=True, text=True)
    actual_lines = run.stdout.strip().split('\n') if run.stdout.strip() else []

    # Step 3: compare
    if actual_lines == expected:
        print(f'  {GR}✔ PASS{R}  {name}  {DM}({len(expected)} checks){R}')
        return True
    else:
        print(f'  {RD}✘ FAIL{R}  {name}')
        for i, (exp, act) in enumerate(zip(expected, actual_lines)):
            marker = f'{GR}✔{R}' if exp == act else f'{RD}✘{R}'
            if exp != act:
                print(f'    {marker} line {i+1}: expected {exp!r}, got {act!r}')
        if len(actual_lines) != len(expected):
            print(f'    Expected {len(expected)} lines, got {len(actual_lines)}')
        return False


def main():
    verbose = '-v' in sys.argv

    print(f'\n{B}{CY}╔══════════════════════════════════════════════════════════╗')
    print(f'║  Mini Python Compiler — Test Suite                       ║')
    print(f'╚══════════════════════════════════════════════════════════╝{R}\n')

    passed = 0
    failed = 0

    for test in TESTS:
        if run_test(test, verbose):
            passed += 1
        else:
            failed += 1

    # Summary
    total = passed + failed
    print(f'\n{B}Results: {GR}{passed} passed{R}{B}, {RD if failed else GR}{failed} failed{R}{B}, {total} total{R}')

    if failed == 0:
        print(f'{GR}{B}All tests passed! ✨{R}\n')
    else:
        print(f'{RD}{B}{failed} test(s) failed.{R}\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
