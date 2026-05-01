#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile


TESTS = [
    {
        "name": "Arithmetic & Basic Features",
        "file": "test_input.py",
        "expected": [
            "14",
            "6",
            "40",
            "2.5",
            "14",
            "20",
            "25",
            "30",
            "42",
            "3",
            "2",
            "1",
            "600",
            "All tests passed!",
        ],
    },
    {
        "name": "Function Definitions & Calls",
        "file": "test_functions.py",
        "expected": [
            "42",
            "17",
            "16",
            "15",
            "Functions test done!",
        ],
    },
    {
        "name": "Control Flow",
        "file": "test_control_flow.py",
        "expected": [
            "1",
            "2",
            "3",
            "15",
            "4",
            "5",
            "Control flow test done!",
        ],
    },
    {
        "name": "Optimizer Coverage",
        "file": "test_optimizer.py",
        "expected": [
            "5",
            "50",
            "70",
            "25",
            "50",
            "13",
            "True",
            "True",
            "42",
            "Optimizer test done!",
        ],
    },
    {
        "name": "Advanced Features",
        "file": "test_advanced.py",
        "expected": [
            "15",
            "13",
            "26",
            "13",
            "medium",
            "55",
            "120",
            "True",
            "True",
            "Advanced tests passed!",
        ],
    },
    {
        "name": "Booleans & Short-Circuit",
        "file": "test_booleans.py",
        "expected": [
            "True",
            "False",
            "False",
            "True",
            "False",
            "1",
            "2",
            "3",
            "4",
            "booleans done!",
        ],
    },
    {
        "name": "Phase 1 Operators",
        "file": "test_phase1_ops.py",
        "expected": [
            "3",
            "49",
            "2",
            "7",
            "5",
            "14",
            "3",
            "7",
            "-8",
            "Phase 1 ops done!",
            "-4",
            "-4",
            "3",
            "1024",
            "Phase 1 ops edge cases done!",
        ],
    },
    {
        "name": "Native semantics (modulo, truthiness)",
        "file": "test_native_semantics.py",
        "expected": [
            "1",
            "-1",
            "-1",
            "ok",
            "ok",
            "ok",
            "ok",
            "ok",
            "ok",
            "Native semantics done!",
        ],
    },
]


SOURCE_TESTS = [
    {
        "name": "Forward function references",
        "source": """result = use_later(5)\nprint(result)\n\n\ndef use_later(x):\n    return x + 7\n""",
        "expected": ["12"],
    },
    {
        "name": "Mutual recursion",
        "source": """def is_even(n):\n    if n == 0:\n        return True\n    return is_odd(n - 1)\n\n\ndef is_odd(n):\n    if n == 0:\n        return False\n    return is_even(n - 1)\n\n\nprint(is_even(6))\nprint(is_odd(7))\n""",
        "expected": ["True", "True"],
    },
    {
        "name": "Local module import",
        "source": """from helper import add\nprint(add(4, 5))\n""",
        "extra_files": {"helper.py": "def add(a, b):\n    return a + b\n"},
        "expected": ["9"],
    },
    {
        "name": "Local package import",
        "source": """import pkg.tools\nfrom pkg import helper\nprint(pkg.tools.value)\nprint(helper.message)\n""",
        "extra_files": {
            "pkg/__init__.py": "name = 'pkg'\n",
            "pkg/tools.py": "value = 7\n",
            "pkg/helper.py": "message = 'loaded'\n",
        },
        "expected": ["7", "loaded"],
    },
    {
        "name": "Relative imports",
        "source": """from . import helper\nfrom .helper import value\nprint(helper.value)\nprint(value)\n""",
        "filename": "pkg/main.py",
        "extra_files": {
            "pkg/__init__.py": "",
            "pkg/helper.py": "value = 11\n",
        },
        "expected": ["11", "11"],
    },
    {
        "name": "Star imports",
        "source": """from helper import *\nprint(value)\nprint(add(2, 5))\n""",
        "extra_files": {
            "helper.py": "__all__ = ['value', 'add']\nvalue = 7\ndef add(a, b):\n    return a + b\n_hidden = 9\n",
        },
        "expected": ["7", "7"],
    },
    {
        "name": "Stdlib import fallback",
        "source": """import math\nfrom math import sqrt\nimport os.path\nprint(math.sqrt(9))\nprint(sqrt(16))\nprint(os.path.basename("/tmp/demo.txt"))\n""",
        "expected": ["3.0", "4.0", "demo.txt"],
    },
    {
        "name": "Closure capture",
        "source": """def outer(x):\n    def inner(y):\n        return x + y\n    return inner(3)\n\nprint(outer(4))\n""",
        "expected": ["7"],
    },
    {
        "name": "For loop with range",
        "source": """for i in range(1, 4):\n    print(i)\n""",
        "expected": ["1", "2", "3"],
    },
    {
        "name": "Lists tuples indexing and len",
        "source": """items = [10, 20, 30]\npair = (4, 5)\nword = "hello"\nprint(len(items))\nprint(items[1])\nprint(pair[0])\nprint(word[1])\n""",
        "expected": ["3", "20", "4", "e"],
    },
    {
        "name": "Slicing",
        "source": """items = [0, 1, 2, 3, 4]\nword = "hello"\nprint(items[1:3])\nprint(items[:2])\nprint(items[::2])\nprint(items[::-1])\nprint(word[1:4])\n""",
        "expected": ["[1, 2]", "[0, 1]", "[0, 2, 4]", "[4, 3, 2, 1, 0]", "ell"],
    },
    {
        "name": "Unpack assignment",
        "source": """a, b = (1, 2)\nc, d = [3, 4]\nprint(a)\nprint(b)\nprint(c + d)\n""",
        "expected": ["1", "2", "7"],
    },
    {
        "name": "Pass delete global and nonlocal",
        "source": """items = [1, 2, 3]\nif True:\n    pass\nfor _ in range(1):\n    pass\ndef noop():\n    pass\nclass Box:\n    def touch(self):\n        pass\nnoop()\nBox().touch()\ndel items[0]\nd = {"x": 1, "y": 2}\ndel d["x"]\nx = 1\ndef update():\n    global x\n    x = x + 1\ndef outer():\n    y = 10\n    def inner():\n        nonlocal y\n        y = y + 5\n        return y\n    return inner()\nupdate()\nprint(items[0])\nprint(len(d))\nprint(x)\nprint(outer())\n""",
        "expected": ["2", "1", "2", "15"],
    },
    {
        "name": "With statement",
        "source": """class CM:\n    def __enter__(self):\n        print("enter")\n        return "body"\n    def __exit__(self, exc_type, exc, tb):\n        print("exit")\nwith CM() as value, CM() as other:\n    print(value)\n    print(other)\n""",
        "expected": ["enter", "enter", "body", "body", "exit", "exit"],
    },
    {
        "name": "Dicts sets and container methods",
        "source": """d = {"a": 1, "b": 2}\nprint(d["a"])\nprint(len(d))\nprint(d.get("b"))\ns = {1, 2}\ns.add(3)\nprint(3 in s)\n""",
        "expected": ["1", "2", "2", "True"],
    },
    {
        "name": "Comprehensions",
        "source": """nums = [1, 2, 3, 4]\ndoubled = [x * 2 for x in nums if x > 1]\nmapping = {x: x * x for x in nums if x % 2 == 0}\nunique = {x for x in nums if x != 2}\nprint(doubled[0])\nprint(mapping[4])\nprint(len(unique))\n""",
        "expected": ["4", "16", "3"],
    },
    {
        "name": "Classes attributes and methods",
        "source": """class Counter:\n    def __init__(self, start):\n        self.value = start\n    def inc(self):\n        self.value = self.value + 1\n        return self.value\n\ncounter = Counter(5)\nprint(counter.value)\nprint(counter.inc())\nprint(counter.value)\n""",
        "expected": ["5", "6", "6"],
    },
    {
        "name": "Inheritance super and class attributes",
        "source": """class Base:\n    kind = "base"\n    def __init__(self, value):\n        self.value = value\n    def greet(self):\n        return "base:" + self.kind\n\nclass Child(Base):\n    kind = "child"\n    def greet(self):\n        return super().greet() + ":" + str(self.value)\n\nchild = Child(7)\nprint(child.kind)\nprint(Child.kind)\nprint(child.greet())\nprint(isinstance(child, Base))\nprint(issubclass(Child, Base))\n""",
        "expected": ["child", "child", "base:child:7", "True", "True"],
    },
    {
        "name": "Decorators",
        "source": """def decorate(fn):\n    def wrapped(name):\n        return fn(name) + "!"\n    return wrapped\n\ndef mark(cls):\n    cls.tag = "ok"\n    return cls\n\n@decorate\ndef greet(name):\n    return "hi " + name\n\n@mark\nclass Box:\n    pass\n\nprint(greet("Ada"))\nprint(Box.tag)\n""",
        "expected": ["hi Ada!", "ok"],
    },
    {
        "name": "Basic try/except",
        "source": """try:\n    raise "boom"\nexcept:\n    print("handled")\n""",
        "expected": ["handled"],
    },
    {
        "name": "Typed except with binding",
        "source": """class MyError:\n    def __init__(self, message):\n        self.message = message\n\ntry:\n    raise MyError("boom")\nexcept MyError as err:\n    print(err.message)\n""",
        "expected": ["boom"],
    },
    {
        "name": "Multi argument print",
        "source": """print("hello", "world", sep=", ", end="!")\n""",
        "expected": ["hello, world!"],
    },
    {
        "name": "Default arguments",
        "source": """def greet(name, greeting="Hello"):\n    return greeting + ", " + name\n\nprint(greet("Ada"))\nprint(greet("Bob", "Hi"))\n""",
        "expected": ["Hello, Ada", "Hi, Bob"],
    },
    {
        "name": "Keyword arguments",
        "source": """def combine(a, b, c=3):\n    return a + b + c\n\nprint(combine(1, c=5, b=2))\n""",
        "expected": ["8"],
    },
    {
        "name": "Varargs kwargs and keyword-only parameters",
        "source": """def collect(a, *rest, flag=False, **named):\n    print(a)\n    print(len(rest))\n    print(flag)\n    print(named["extra"])\ncollect(1, 2, 3, flag=True, extra=9)\n""",
        "expected": ["1", "2", "True", "9"],
    },
    {
        "name": "F strings",
        "source": """name = "Ada"\nprint(f"Hello {name}")\n""",
        "expected": ["Hello Ada"],
    },
    {
        "name": "Membership and identity operators",
        "source": """items = [1, 2, 3]\nprint(2 in items)\nprint(4 not in items)\nprint(items is items)\nprint(1 < 2 < 3)\nprint(1 < 2 > 4)\n""",
        "expected": ["True", "True", "True", "True", "False"],
    },
    {
        "name": "Additional builtins",
        "source": """items = [3, 1, 2]\nprint(sorted(items)[0])\nprint(str(10))\nprint(abs(-4))\n""",
        "expected": ["1", "10", "4"],
    },
    {
        "name": "Mixed numeric ops (VM)",
        "source": """print(7.0 // 2)\nprint(7 // 2.0)\nprint(2 ** 3.0)\nprint(2.0 ** 3)\n""",
        "expected": ["3.0", "3.0", "8.0", "8.0"],
    },
    {
        "name": "Phase 2: tuple target in for-loop",
        "source": """pairs = [(1, 2), (3, 4)]\ntotal = 0\nfor a, b in pairs:\n    total = total + a + b\nprint(total)\n""",
        "expected": ["10"],
    },
    {
        "name": "Phase 2: starred unpack assignment",
        "source": """a, *rest, b = [1, 2, 3, 4]\nprint(a)\nprint(rest[0])\nprint(len(rest))\nprint(b)\n""",
        "expected": ["1", "2", "2", "4"],
    },
    {
        "name": "Phase 2: *args splat in calls",
        "source": """def add3(a, b, c):\n    return a + b + c\n\nargs = [1, 2, 3]\nprint(add3(*args))\n""",
        "expected": ["6"],
    },
    {
        "name": "Try/finally on return",
        "source": """def compute():\n    try:\n        return 7\n    finally:\n        print("cleanup")\n\nprint(compute())\n""",
        "expected": ["cleanup", "7"],
    },
    {
        "name": "Try/finally exception propagation",
        "source": """try:\n    try:\n        raise "boom"\n    finally:\n        print("cleanup")\nexcept:\n    print("handled")\n""",
        "expected": ["cleanup", "handled"],
    },
    {
        "name": "Try else and reraise",
        "source": """try:\n    print("body")\nexcept Exception:\n    print("except")\nelse:\n    print("else")\n\ntry:\n    try:\n        raise ValueError("boom")\n    except ValueError:\n        raise\nexcept Exception as err:\n    print(err)\n""",
        "expected": ["body", "else", "boom"],
    },
]


NEGATIVE_TESTS = [
    {
        "name": "Reject missing modules",
        "source": "from missing import add\nprint(add(1, 2))\n",
        "expected_substring": "cannot import 'missing'",
    },
    {
        "name": "Reject mixed arithmetic",
        "source": 'x = "a" + 1\n',
        "expected_substring": "requires numeric operands",
    },
    {
        "name": "Reject bad len argument",
        "source": "print(len(1))\n",
        "expected_substring": "len() expects a list, tuple, string, dict, or set",
    },
    {
        "name": "Reject bad range arity",
        "source": "for i in range(1, 2, 3, 4):\n    print(i)\n",
        "expected_substring": "range() expects 1 to 3 arguments",
    },
    {
        "name": "Reject syntax errors",
        "source": "x = 1 $ 2\n",
        "expected_substring": "Syntax Error",
    },
    {
        "name": "Reject wrong argument count",
        "source": "def add(a, b):\n    return a + b\n\nprint(add(1))\n",
        "expected_substring": "missing required argument 'b'",
    },
    {
        "name": "Reject duplicate keyword argument",
        "source": "def add(a, b=1):\n    return a + b\n\nprint(add(1, a=2))\n",
        "expected_substring": "got multiple values for argument 'a'",
    },
    {
        "name": "Reject missing keyword-only argument",
        "source": "def configure(*, flag):\n    return flag\n\nprint(configure())\n",
        "expected_substring": "missing required keyword-only argument 'flag'",
    },
    {
        "name": "Reject unhandled exceptions",
        "source": 'raise "boom"\n',
        "expected_substring": "unhandled exception: boom",
    },
    {
        "name": "Reject unsupported print keyword",
        "source": 'print("x", flush=True)\n',
        "expected_substring": "print() keyword 'flush' is not supported yet",
    },
    {
        "name": "Reject unpack count mismatch",
        "source": "a, b = (1, 2, 3)\n",
        "expected_substring": "unpack expected 2 values, got 3",
    },
    {
        "name": "Reject starred unpacking",
        "source": "a, *rest, *more = [1, 2, 3]\n",
        "expected_substring": "only a single starred assignment target is supported",
    },
    {
        "name": "Reject invalid nonlocal",
        "source": "def outer():\n    def inner():\n        nonlocal missing\n        missing = 1\n    return inner()\nprint(outer())\n",
        "expected_substring": "no binding for nonlocal 'missing' found",
    },
    {
        "name": "Reject unsupported delete target",
        "source": "class Box:\n    pass\nbox = Box()\nbox.value = 1\ndel box.value\n",
        "expected_substring": "only name and subscript delete targets are supported",
    },
    {
        "name": "Reject invalid with-as target",
        "source": "class CM:\n    def __enter__(self):\n        return 1\n    def __exit__(self, exc_type, exc, tb):\n        pass\nwith CM() as (a, b):\n    print(a)\n",
        "expected_substring": "only simple name targets in with-as clauses are supported",
    },
    {
        "name": "Reject bare raise outside except",
        "source": "raise\n",
        "expected_substring": "bare raise is only valid inside an except block",
    },
    {
        "name": "Reject negative exponent in native codegen",
        "source": "print(2 ** -1)\n",
        "native": True,
        "expected_substring": "native compilation does not support negative integer exponents",
    },
    {
        "name": "Reject mixed int/float // or ** in native codegen",
        "source": "print(7.0 // 2)\nprint(2 ** 3.0)\n",
        "native": True,
        "expected_substring": "native compilation does not support mixed int/float operands for '//' or '**' yet",
    },
    {
        "name": "Reject **kwargs splat in native codegen",
        "source": """def inner(**kw):
    return 0

def outer(**kw):
    return inner(**kw)

print(outer(a=1))
""",
        "native": True,
    "expected_substring": "native compilation does not support default or keyword arguments yet",
    },
    {
        "name": "Reject walrus in native codegen",
        "source": """if (x := 1) == 1:
    print(x)
""",
        "native": True,
        "expected_substring": "native compilation does not support the walrus operator ':=' yet",
    },
]


GR = "\033[92m"
RD = "\033[91m"
CY = "\033[96m"
B = "\033[1m"
R = "\033[0m"
DM = "\033[2m"


def run_positive_test(test):
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "program.c")
        executable_path = os.path.splitext(output_path)[0]
        result = subprocess.run(
            [sys.executable, "main.py", test["file"], "--run", "--no-viz", "-q", "-o", output_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  {RD}✘ FAIL{R}  {test['name']} — compiler error")
            if result.stderr.strip():
                print(f"    {DM}{result.stderr.strip()}{R}")
            return False

        run = subprocess.run([executable_path], capture_output=True, text=True)
        actual_lines = run.stdout.strip().splitlines() if run.stdout.strip() else []
        if actual_lines == test["expected"]:
            print(f"  {GR}✔ PASS{R}  {test['name']}  {DM}({len(test['expected'])} checks){R}")
            return True

        print(f"  {RD}✘ FAIL{R}  {test['name']}")
        for index, (expected, actual) in enumerate(zip(test["expected"], actual_lines), start=1):
            if expected != actual:
                print(f"    {RD}✘{R} line {index}: expected {expected!r}, got {actual!r}")
        if len(actual_lines) != len(test["expected"]):
            print(f"    Expected {len(test['expected'])} lines, got {len(actual_lines)}")
        return False


def run_negative_test(test):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=".") as handle:
        handle.write(test["source"])
        temp_path = handle.name

    try:
        native = test.get("native", False)
        cmd = [sys.executable, "main.py", temp_path, "--no-viz", "-q"]
        if native:
            cmd.insert(3, "--compile-native")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  {RD}✘ FAIL{R}  {test['name']} — expected compilation failure")
            return False
        output = f"{result.stdout}\n{result.stderr}"
        if test["expected_substring"] in output:
            print(f"  {GR}✔ PASS{R}  {test['name']}")
            return True
        print(f"  {RD}✘ FAIL{R}  {test['name']} — missing diagnostic")
        if output.strip():
            print(f"    {DM}{output.strip()}{R}")
        return False
    finally:
        os.unlink(temp_path)


def run_source_test(test):
    with tempfile.TemporaryDirectory() as root_dir:
        main_relative = test.get("filename", "main.py")
        temp_path = os.path.join(root_dir, main_relative)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(test["source"])

        created_files = []
        for relative_path, contents in test.get("extra_files", {}).items():
            full_path = os.path.join(root_dir, relative_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as handle:
                handle.write(contents)
            created_files.append(full_path)

        result = subprocess.run(
            [sys.executable, "main.py", temp_path, "--no-viz", "-q"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  {RD}✘ FAIL{R}  {test['name']} — runtime error")
            if result.stderr.strip():
                print(f"    {DM}{result.stderr.strip()}{R}")
            return False

        actual_lines = result.stdout.strip().splitlines() if result.stdout.strip() else []
        if actual_lines == test["expected"]:
            print(f"  {GR}✔ PASS{R}  {test['name']}")
            return True

        print(f"  {RD}✘ FAIL{R}  {test['name']}")
        print(f"    Expected {test['expected']!r}, got {actual_lines!r}")
        return False


def run_cli_smoke():
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "program.c")
        result = subprocess.run(
            [sys.executable, "main.py", "test_input.py", "--compile-native", "--no-viz", "-q", "-o", output_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  {RD}✘ FAIL{R}  CLI compile-only")
            return False
        if not os.path.exists(output_path):
            print(f"  {RD}✘ FAIL{R}  CLI compile-only — output file not created")
            return False
        print(f"  {GR}✔ PASS{R}  CLI compile-only")
        return True


def run_quiet_mode_smoke():
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "program.c")
        result = subprocess.run(
            [sys.executable, "main.py", "test_input.py", "--run", "--no-viz", "-q", "-o", output_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  {RD}✘ FAIL{R}  CLI quiet mode")
            return False
        if result.stdout.strip() or result.stderr.strip():
            print(f"  {RD}✘ FAIL{R}  CLI quiet mode — expected no terminal output")
            return False
        print(f"  {GR}✔ PASS{R}  CLI quiet mode")
        return True


def main():
    print(f"\n{B}{CY}╔══════════════════════════════════════════════════════════╗")
    print("║  Python Subset Compiler — Test Suite                    ║")
    print(f"╚══════════════════════════════════════════════════════════╝{R}\n")

    passed = 0
    failed = 0

    for test in TESTS:
        if run_positive_test(test):
            passed += 1
        else:
            failed += 1

    for test in NEGATIVE_TESTS:
        if run_negative_test(test):
            passed += 1
        else:
            failed += 1

    for test in SOURCE_TESTS:
        if run_source_test(test):
            passed += 1
        else:
            failed += 1

    if run_cli_smoke():
        passed += 1
    else:
        failed += 1

    if run_quiet_mode_smoke():
        passed += 1
    else:
        failed += 1

    total = passed + failed
    print(f"\n{B}Results: {GR}{passed} passed{R}{B}, {RD if failed else GR}{failed} failed{R}{B}, {total} total{R}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
