import os
import tempfile
import unittest

from compiler import check_source, compile_source, execute_source


class PipelineTests(unittest.TestCase):
    def compile_program(self, source: str, run: bool = False):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(source, filename="inline.py", output=output_path, run=run)
            c_code = result.c_code
            run_output = result.run_output
            rendered = result.errors.render()
            output_exists = os.path.exists(output_path)
            runtime_header_exists = bool(result.runtime_header_path and os.path.exists(result.runtime_header_path))
            runtime_source_exists = bool(result.runtime_source_path and os.path.exists(result.runtime_source_path))
            executable_exists = bool(result.executable_path and os.path.exists(result.executable_path))
            return (
                result,
                c_code,
                run_output,
                rendered,
                output_exists,
                runtime_header_exists,
                runtime_source_exists,
                executable_exists,
            )

    def execute_program(self, source: str):
        result = execute_source(source, filename="inline.py")
        return result, result.run_output, result.errors.render()

    def execute_program_file(self, source: str, extra_files: dict[str, str], *, main_relative_path: str = "main.py"):
        with tempfile.TemporaryDirectory() as temp_dir:
            main_path = os.path.join(temp_dir, main_relative_path)
            os.makedirs(os.path.dirname(main_path), exist_ok=True)
            with open(main_path, "w", encoding="utf-8") as handle:
                handle.write(source)
            for relative_path, contents in extra_files.items():
                file_path = os.path.join(temp_dir, relative_path)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as handle:
                    handle.write(contents)
            result = execute_source(source, filename=main_path)
            return result, result.run_output, result.errors.render()

    def test_compile_source_returns_structured_result(self):
        result, c_code, _, rendered, output_exists, runtime_header_exists, runtime_source_exists, _ = self.compile_program("print(1)\n")
        self.assertTrue(result.success, rendered)
        self.assertTrue(output_exists)
        self.assertIsNotNone(result.lexed)
        self.assertIsNotNone(result.parsed)
        self.assertIsNotNone(result.program)
        self.assertGreater(len(result.ir.main.blocks), 0)
        self.assertIsNotNone(result.ir.main.blocks[0].terminator)
        self.assertIsNotNone(result.ssa)
        self.assertTrue(runtime_header_exists)
        self.assertTrue(runtime_source_exists)
        self.assertIn("py_write_int", c_code)
        self.assertIn('#include "py_runtime.h"', c_code)
        self.assertTrue(all(not block.phis for block in result.ir.main.blocks))

    def test_check_source_defaults_to_validated_owned_frontend(self):
        result = check_source("print(1)\n", filename="inline.py")
        self.assertTrue(result.success, result.errors.render())
        self.assertIsNotNone(result.lexed)
        self.assertIsNotNone(result.parsed)
        self.assertIsNotNone(result.program)

    def test_execute_source_returns_bytecode_and_output(self):
        result, run_output, rendered = self.execute_program("print(7)\n")
        self.assertTrue(result.success, rendered)
        self.assertIsNotNone(result.bytecode)
        self.assertIn("PRINT", str(result.bytecode))
        self.assertEqual(run_output.strip().splitlines(), ["7"])

    def test_execute_source_supports_multi_argument_print(self):
        result, run_output, rendered = self.execute_program(
            'print("hello", "world", sep=", ", end="!")\n'
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output, "hello, world!")

    def test_execute_source_supports_default_arguments(self):
        result, run_output, rendered = self.execute_program(
            "def greet(name, greeting=\"Hello\"):\n"
            "    return greeting + \", \" + name\n\n"
            "print(greet(\"Ada\"))\n"
            "print(greet(\"Bob\", \"Hi\"))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["Hello, Ada", "Hi, Bob"])

    def test_execute_source_supports_keyword_arguments(self):
        result, run_output, rendered = self.execute_program(
            "def combine(a, b, c=3):\n"
            "    return a + b + c\n\n"
            "print(combine(1, c=5, b=2))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["8"])

    def test_execute_source_supports_varargs_kwargs_and_keyword_only_parameters(self):
        result, run_output, rendered = self.execute_program(
            "def collect(a, *rest, flag=False, **named):\n"
            "    print(a)\n"
            "    print(len(rest))\n"
            "    print(flag)\n"
            "    print(named[\"extra\"])\n"
            "collect(1, 2, 3, flag=True, extra=9)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "True", "9"])

    def test_execute_source_supports_keyword_only_required_arguments(self):
        result, run_output, rendered = self.execute_program(
            "def configure(*, flag):\n"
            "    print(flag)\n"
            "configure(flag=True)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["True"])

    def test_execute_source_supports_method_keyword_arguments(self):
        result, run_output, rendered = self.execute_program(
            "class Greeter:\n"
            "    def say(self, name, greeting=\"Hello\"):\n"
            "        return greeting + \", \" + name\n\n"
            "g = Greeter()\n"
            "print(g.say(name=\"Ada\"))\n"
            "print(g.say(\"Bob\", greeting=\"Hi\"))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["Hello, Ada", "Hi, Bob"])

    def test_execute_source_supports_method_varargs_and_kwargs(self):
        result, run_output, rendered = self.execute_program(
            "class Collector:\n"
            "    def collect(self, head, *rest, flag=False, **named):\n"
            "        print(head)\n"
            "        print(len(rest))\n"
            "        print(flag)\n"
            "        print(named[\"extra\"])\n"
            "Collector().collect(1, 2, 3, flag=True, extra=5)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "True", "5"])

    def test_execute_source_supports_f_strings(self):
        result, run_output, rendered = self.execute_program(
            'name = "Ada"\nprint(f"Hello {name}")\n'
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["Hello Ada"])

    def test_execute_source_supports_in_and_is_operators(self):
        result, run_output, rendered = self.execute_program(
            "items = [1, 2, 3]\n"
            "print(2 in items)\n"
            "print(4 not in items)\n"
            "print(items is items)\n"
            "print(items is not [1, 2, 3])\n"
            "print(1 < 2 < 3)\n"
            "print(1 < 3 > 2)\n"
            "print(1 < 2 > 4)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["True", "True", "True", "True", "True", "True", "False"])

    def test_execute_source_supports_additional_builtins(self):
        result, run_output, rendered = self.execute_program(
            "items = [3, 1, 2]\n"
            "print(sorted(items)[0])\n"
            "print(str(10))\n"
            "print(abs(-4))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "10", "4"])

    def test_execute_source_supports_local_from_import(self):
        result, run_output, rendered = self.execute_program_file(
            "from util import add\nprint(add(2, 5))\n",
            {"util.py": "def add(a, b):\n    return a + b\n"},
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["7"])

    def test_execute_source_supports_local_package_imports(self):
        result, run_output, rendered = self.execute_program_file(
            "import pkg.tools\n"
            "from pkg import helper\n"
            "print(pkg.tools.value)\n"
            "print(helper.message)\n",
            {
                "pkg/__init__.py": "name = 'pkg'\n",
                "pkg/tools.py": "value = 7\n",
                "pkg/helper.py": "message = 'loaded'\n",
            },
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["7", "loaded"])

    def test_execute_source_supports_relative_imports(self):
        result, run_output, rendered = self.execute_program_file(
            "from . import helper\n"
            "from .helper import value\n"
            "print(helper.value)\n"
            "print(value)\n",
            {
                "pkg/__init__.py": "",
                "pkg/helper.py": "value = 11\n",
            },
            main_relative_path="pkg/main.py",
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["11", "11"])

    def test_execute_source_supports_star_imports(self):
        result, run_output, rendered = self.execute_program_file(
            "from helper import *\n"
            "print(value)\n"
            "print(add(2, 5))\n",
            {
                "helper.py": "__all__ = ['value', 'add']\nvalue = 7\ndef add(a, b):\n    return a + b\n_hidden = 9\n",
            },
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["7", "7"])

    def test_execute_source_supports_importlib_fallback_for_stdlib(self):
        result, run_output, rendered = self.execute_program(
            "import math\n"
            "from math import sqrt\n"
            "import os.path\n"
            "print(math.sqrt(9))\n"
            "print(sqrt(16))\n"
            'print(os.path.basename("/tmp/demo.txt"))\n'
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["3.0", "4.0", "demo.txt"])

    def test_execute_source_supports_closure_capture(self):
        result, run_output, rendered = self.execute_program(
            "def outer(x):\n"
            "    def inner(y):\n"
            "        return x + y\n"
            "    return inner(5)\n\n"
            "print(outer(7))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["12"])

    def test_execute_source_supports_basic_try_except(self):
        result, run_output, rendered = self.execute_program(
            "try:\n"
            "    raise \"boom\"\n"
            "except:\n"
            "    print(\"handled\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["handled"])

    def test_execute_source_supports_typed_except_with_binding(self):
        result, run_output, rendered = self.execute_program(
            "class MyError:\n"
            "    def __init__(self, message):\n"
            "        self.message = message\n\n"
            "try:\n"
            "    raise MyError(\"boom\")\n"
            "except MyError as err:\n"
            "    print(err.message)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["boom"])

    def test_execute_source_supports_try_finally_on_return(self):
        result, run_output, rendered = self.execute_program(
            "def compute():\n"
            "    try:\n"
            "        return 7\n"
            "    finally:\n"
            "        print(\"cleanup\")\n\n"
            "print(compute())\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["cleanup", "7"])

    def test_execute_source_runs_finally_before_outer_exception_handler(self):
        result, run_output, rendered = self.execute_program(
            "try:\n"
            "    try:\n"
            "        raise \"boom\"\n"
            "    finally:\n"
            "        print(\"cleanup\")\n"
            "except:\n"
            "    print(\"handled\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["cleanup", "handled"])

    def test_execute_source_try_except_else_finally_normal_path(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "    except ValueError:\n"
            "        print(\"except\")\n"
            "    else:\n"
            "        print(\"else\")\n"
            "    finally:\n"
            "        print(\"finally\")\n\n"
            "f()\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["try", "else", "finally"])

    def test_execute_source_exception_path_runs_finally(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "        raise ValueError(\"boom\")\n"
            "    except ValueError:\n"
            "        print(\"except\")\n"
            "    finally:\n"
            "        print(\"finally\")\n\n"
            "f()\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["try", "except", "finally"])

    def test_execute_source_nested_finally_inside_except(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError:\n"
            "        try:\n"
            "            print(\"inner try\")\n"
            "        finally:\n"
            "            print(\"inner finally\")\n"
            "    finally:\n"
            "        print(\"outer finally\")\n\n"
            "f()\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["inner try", "inner finally", "outer finally"])

    def test_execute_source_try_finally_return_override(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        return 1\n"
            "    finally:\n"
            "        return 2\n\n"
            "print(f())\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["2"])

    def test_execute_source_try_finally_break(self):
        result, run_output, rendered = self.execute_program(
            "for i in range(3):\n"
            "    try:\n"
            "        print(i)\n"
            "        break\n"
            "    finally:\n"
            "        print(\"cleanup\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "cleanup"])

    def test_execute_source_try_finally_continue(self):
        result, run_output, rendered = self.execute_program(
            "for i in range(2):\n"
            "    try:\n"
            "        print(i)\n"
            "        continue\n"
            "    finally:\n"
            "        print(\"finally\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "finally", "1", "finally"])

    def test_execute_source_exception_in_finally(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "    finally:\n"
            "        print(\"finally\")\n"
            "        raise ValueError()\n\n"
            "try:\n"
            "    f()\n"
            "except ValueError:\n"
            "    print(\"caught\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["try", "finally", "caught"])

    def test_execute_source_nested_reraise(self):
        result, run_output, rendered = self.execute_program(
            "def f():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError:\n"
            "        print(\"inner\")\n"
            "        raise\n\n"
            "try:\n"
            "    f()\n"
            "except ValueError:\n"
            "    print(\"outer\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["inner", "outer"])

    def test_execute_source_supports_for_range(self):
        result, run_output, rendered = self.execute_program(
            "for i in range(1, 4):\n"
            "    print(i)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "3"])

    def test_execute_source_supports_lists_tuples_indexing_and_len(self):
        result, run_output, rendered = self.execute_program(
            "items = [10, 20, 30]\n"
            "pair = (4, 5)\n"
            'word = "hello"\n'
            "print(len(items))\n"
            "print(items[1])\n"
            "print(pair[0])\n"
            "print(word[1])\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["3", "20", "4", "e"])

    def test_execute_source_supports_slicing(self):
        result, run_output, rendered = self.execute_program(
            "items = [0, 1, 2, 3, 4]\n"
            'word = "hello"\n'
            "print(items[1:3])\n"
            "print(items[:2])\n"
            "print(items[::2])\n"
            "print(items[::-1])\n"
            "print(word[1:4])\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["[1, 2]", "[0, 1]", "[0, 2, 4]", "[4, 3, 2, 1, 0]", "ell"])

    def test_execute_source_supports_unpack_assignment(self):
        result, run_output, rendered = self.execute_program(
            "a, b = (1, 2)\n"
            "c, d = [3, 4]\n"
            "print(a)\n"
            "print(b)\n"
            "print(c + d)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "7"])

    def test_execute_source_supports_pass_delete_global_and_nonlocal(self):
        result, run_output, rendered = self.execute_program(
            "items = [1, 2, 3]\n"
            "if True:\n"
            "    pass\n"
            "for _ in range(1):\n"
            "    pass\n"
            "def noop():\n"
            "    pass\n"
            "class Box:\n"
            "    def touch(self):\n"
            "        pass\n"
            "noop()\n"
            "Box().touch()\n"
            "del items[0]\n"
            'd = {"x": 1, "y": 2}\n'
            'del d["x"]\n'
            "box = Box()\n"
            "box.value = 4\n"
            "del box.value\n"
            "box.value = 9\n"
            "name = 5\n"
            "del name\n"
            "x = 1\n"
            "def update():\n"
            "    global x\n"
            "    x = x + 1\n"
            "def outer():\n"
            "    y = 10\n"
            "    def inner():\n"
            "        nonlocal y\n"
            "        y = y + 5\n"
            "        return y\n"
            "    return inner()\n"
            "update()\n"
            "print(items[0])\n"
            "print(len(d))\n"
            "print(box.value)\n"
            "print(x)\n"
            "print(outer())\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["2", "1", "9", "2", "15"])

    def test_execute_source_supports_with_statement(self):
        result, run_output, rendered = self.execute_program(
            "class CM:\n"
            "    def __enter__(self):\n"
            "        print(\"enter\")\n"
            "        return \"body\"\n"
            "    def __exit__(self, exc_type, exc, tb):\n"
            "        print(\"exit\")\n"
            "with CM() as value, CM() as other:\n"
            "    print(value)\n"
            "    print(other)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["enter", "enter", "body", "body", "exit", "exit"])

    def test_execute_source_with_statement_can_suppress_exception(self):
        result, run_output, rendered = self.execute_program(
            "class CM:\n"
            "    def __enter__(self):\n"
            "        return 1\n"
            "    def __exit__(self, exc_type, exc, tb):\n"
            "        print(exc_type == ValueError)\n"
            "        print(str(exc))\n"
            "        return True\n"
            "with CM():\n"
            "    raise ValueError(\"boom\")\n"
            "print(\"after\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["True", "boom", "after"])

    def test_execute_source_typed_except_respects_host_exception_hierarchy(self):
        result, run_output, rendered = self.execute_program(
            "try:\n"
            "    raise ValueError(\"boom\")\n"
            "except Exception as err:\n"
            "    print(err)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["boom"])

    def test_execute_source_supports_dicts_sets_and_container_methods(self):
        result, run_output, rendered = self.execute_program(
            'd = {"a": 1, "b": 2}\n'
            "print(d[\"a\"])\n"
            "print(len(d))\n"
            "print(d.get(\"b\"))\n"
            "s = {1, 2}\n"
            "s.add(3)\n"
            "print(3 in s)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "2", "True"])

    def test_execute_source_supports_comprehensions(self):
        result, run_output, rendered = self.execute_program(
            "nums = [1, 2, 3, 4]\n"
            "doubled = [x * 2 for x in nums if x > 1]\n"
            "mapping = {x: x * x for x in nums if x % 2 == 0}\n"
            "unique = {x for x in nums if x != 2}\n"
            "print(doubled[0])\n"
            "print(mapping[4])\n"
            "print(len(unique))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["4", "16", "3"])

    def test_execute_source_supports_classes_attributes_and_methods(self):
        result, run_output, rendered = self.execute_program(
            "class Counter:\n"
            "    def __init__(self, start):\n"
            "        self.value = start\n"
            "    def inc(self):\n"
            "        self.value = self.value + 1\n"
            "        return self.value\n\n"
            "counter = Counter(5)\n"
            "print(counter.value)\n"
            "print(counter.inc())\n"
            "print(counter.value)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["5", "6", "6"])

    def test_execute_source_supports_inheritance_super_and_class_attributes(self):
        result, run_output, rendered = self.execute_program(
            "class Base:\n"
            "    kind = \"base\"\n"
            "    def __init__(self, value):\n"
            "        self.value = value\n"
            "    def greet(self):\n"
            "        return \"base:\" + self.kind\n\n"
            "class Child(Base):\n"
            "    kind = \"child\"\n"
            "    def greet(self):\n"
            "        return super().greet() + \":\" + str(self.value)\n\n"
            "child = Child(7)\n"
            "print(child.kind)\n"
            "print(Child.kind)\n"
            "print(child.greet())\n"
            "print(isinstance(child, Base))\n"
            "print(issubclass(Child, Base))\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(
            run_output.strip().splitlines(),
            ["child", "child", "base:child:7", "True", "True"],
        )

    def test_execute_source_supports_function_and_class_decorators(self):
        result, run_output, rendered = self.execute_program(
            "def decorate(fn):\n"
            "    def wrapped(name):\n"
            "        return fn(name) + \"!\"\n"
            "    return wrapped\n\n"
            "def mark(cls):\n"
            "    cls.tag = \"ok\"\n"
            "    return cls\n\n"
            "@decorate\n"
            "def greet(name):\n"
            "    return \"hi \" + name\n\n"
            "@mark\n"
            "class Box:\n"
            "    pass\n\n"
            "print(greet(\"Ada\"))\n"
            "print(Box.tag)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["hi Ada!", "ok"])

    def test_execute_source_supports_try_else_and_reraise(self):
        result, run_output, rendered = self.execute_program(
            "try:\n"
            "    print(\"body\")\n"
            "except Exception:\n"
            "    print(\"except\")\n"
            "else:\n"
            "    print(\"else\")\n\n"
            "try:\n"
            "    try:\n"
            "        raise ValueError(\"boom\")\n"
            "    except ValueError:\n"
            "        raise\n"
            "except Exception as err:\n"
            "    print(err)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["body", "else", "boom"])

    def test_execute_source_supports_raise_from(self):
        result, _, rendered = self.execute_program(
            "try:\n"
            "    raise ValueError(\"inner\")\n"
            "except ValueError as err:\n"
            "    raise RuntimeError(\"outer\") from err\n"
        )
        self.assertFalse(result.success)
        self.assertIn("unhandled exception: outer (caused by inner)", rendered)

    def test_execute_source_reports_unhandled_exception(self):
        result, _, rendered = self.execute_program('raise "boom"\n')
        self.assertFalse(result.success)
        self.assertIn("unhandled exception: boom", rendered)

    def test_compile_source_rejects_imports_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source("from util import add\nprint(add(1, 2))\n", filename="inline.py", output=output_path)
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support imports yet", result.errors.render())

    def test_compile_source_rejects_nested_functions_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "def outer(x):\n"
                "    def inner(y):\n"
                "        return x + y\n"
                "    return inner(1)\n"
                "print(outer(2))\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support nested functions yet", result.errors.render())

    def test_compile_source_allows_basic_try_except_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "try:\n"
                "    raise \"boom\"\n"
                "except:\n"
                "    print(\"handled\")\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertTrue(result.success, result.errors.render())

    def test_compile_source_allows_typed_except_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "try:\n"
                "    raise \"boom\"\n"
                "except Exception as err:\n"
                "    print(err)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertTrue(result.success, result.errors.render())

    def test_compile_source_supports_list_tuple_literals_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "items = [1, 2, 3]\n"
                "pair = (4, 5)\n"
                "print(1)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertTrue(result.success, result.errors.render())
        self.assertIn("py_list_new_int", result.c_code)
        self.assertIn("py_tuple_new_int", result.c_code)

    def test_compile_source_rejects_mixed_type_list_literal_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "items = [1, \"two\"]\n"
                "print(1)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn(
            "native compilation only supports non-empty list/tuple literals",
            result.errors.render(),
        )

    def test_compile_source_supports_list_tuple_indexing_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [10, 20, 30]\n"
            "pair = (4, 5)\n"
            "print(items[1])\n"
            "print(pair[0])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_get_int", c_code)
        self.assertIn("py_tuple_get_int", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["20", "4"])

    def test_compile_source_supports_list_index_assignment_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [1, 2, 3]\n"
            "items[1] = 9\n"
            "print(items[1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_set_int", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["9"])

    def test_compile_source_supports_list_index_assignment_float_bool_for_native_path(self):
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "floats = [1.5, 2.5]\n"
            "floats[0] = 3.25\n"
            "flags = [True, False]\n"
            "flags[1] = True\n"
            "print(floats[0])\n"
            "print(flags[1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["3.25", "True"])

    def test_compile_source_rejects_tuple_index_assignment_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "pair = (1, 2)\n"
                "pair[0] = 9\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support tuple index assignment yet", result.errors.render())

    def test_compile_source_supports_string_indexing_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "word = \"hello\"\n"
            "print(word[1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_str_get_index", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["e"])

    def test_compile_source_supports_string_literal_indexing_for_native_path(self):
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "print(\"abc\"[1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["b"])

    def test_compile_source_supports_string_slicing_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "word = \"hello\"\n"
            "print(word[1:4])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_str_slice", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["ell"])

    def test_compile_source_supports_string_slicing_with_step_for_native_path(self):
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "print(\"abcdef\"[::2])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["ace"])

    def test_compile_source_supports_string_slicing_with_negative_step_for_native_path(self):
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "print(\"hello\"[::-1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["olleh"])

    def test_compile_source_supports_list_slicing_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [0, 1, 2, 3, 4]\n"
            "part = items[1:4]\n"
            "print(len(part))\n"
            "print(part[0])\n"
            "print(part[2])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_slice_int", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["3", "1", "3"])

    def test_compile_source_supports_list_slicing_with_negative_indices_and_step_for_native_path(self):
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [0, 1, 2, 3, 4]\n"
            "tail = items[-3:-1]\n"
            "rev = items[::-1]\n"
            "print(len(tail))\n"
            "print(tail[0])\n"
            "print(tail[1])\n"
            "print(rev[0])\n"
            "print(rev[4])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["2", "2", "3", "4", "0"])

    def test_compile_source_supports_tuple_and_string_list_slicing_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "pair = (10, 20, 30, 40)\n"
            "words = [\"aa\", \"bb\", \"cc\", \"dd\"]\n"
            "mid = pair[1:4:2]\n"
            "picked = words[::2]\n"
            "print(len(mid))\n"
            "print(mid[0])\n"
            "print(mid[1])\n"
            "print(len(picked))\n"
            "print(picked[0])\n"
            "print(picked[1])\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_tuple_slice_int", c_code)
        self.assertIn("py_list_slice_str", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["2", "20", "40", "2", "aa", "cc"])

    def test_compile_source_rejects_dynamic_slice_step_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "items = [0, 1, 2, 3]\n"
                "step = 2\n"
                "part = items[::step]\n"
                "print(len(part))\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn(
            "native compilation only supports string/list/tuple slicing with homogeneous primitive elements and a constant non-zero step for now",
            result.errors.render(),
        )

    def test_compile_source_supports_len_on_list_tuple_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [1, 2, 3]\n"
            "pair = (4, 5)\n"
            "print(len(items))\n"
            "print(len(pair))\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_len", c_code)
        self.assertIn("py_tuple_len", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["3", "2"])

    def test_compile_source_supports_printing_list_tuple_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "nums = [1, 2]\n"
            "flags = [True, False]\n"
            "words = [\"aa\", \"bb\"]\n"
            "pair = (3.5, 4.5)\n"
            "single = (7,)\n"
            "print(nums)\n"
            "print(flags)\n"
            "print(words)\n"
            "print(pair)\n"
            "print(single)\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_repr_int", c_code)
        self.assertIn("py_tuple_repr_float", c_code)
        self.assertEqual(
            run_output.strip().splitlines(),
            ["[1, 2]", "[True, False]", "['aa', 'bb']", "(3.5, 4.5)", "(7,)"],
        )

    def test_compile_source_supports_str_and_repr_on_containers_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [1, 2, 3]\n"
            "pair = (\"aa\", \"bb\")\n"
            "print(str(items))\n"
            "print(repr(pair))\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_repr_int", c_code)
        self.assertIn("py_tuple_repr_str", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["[1, 2, 3]", "('aa', 'bb')"])

    def test_compile_source_supports_container_truthiness_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [1]\n"
            "empty = items[:0]\n"
            "rev = items[::-1]\n"
            "pair = (2,)\n"
            "empty_pair = pair[:0]\n"
            "if items:\n"
            "    print(1)\n"
            "else:\n"
            "    print(0)\n"
            "if empty:\n"
            "    print(1)\n"
            "else:\n"
            "    print(0)\n"
            "print(not empty)\n"
            "if rev:\n"
            "    print(1)\n"
            "else:\n"
            "    print(0)\n"
            "if empty_pair:\n"
            "    print(1)\n"
            "else:\n"
            "    print(0)\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_truthy_list", c_code)
        self.assertIn("py_truthy_tuple", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["1", "0", "True", "1", "0"])

    def test_compile_source_supports_container_equality_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "a = [1, 2]\n"
            "b = [1, 2]\n"
            "c = [2, 1]\n"
            "pair = (\"aa\", \"bb\")\n"
            "same = (\"aa\", \"bb\")\n"
            "other = (\"aa\", \"cc\")\n"
            "print(a == b)\n"
            "print(a != c)\n"
            "print(a == c)\n"
            "print(pair == same)\n"
            "print(pair != other)\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_eq_int", c_code)
        self.assertIn("py_tuple_eq_str", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["True", "True", "False", "True", "True"])

    def test_compile_source_supports_container_membership_for_native_path(self):
        result, c_code, run_output, rendered, _, _, _, executable_exists = self.compile_program(
            "items = [1, 2, 3]\n"
            "pair = (\"aa\", \"bb\")\n"
            "print(2 in items)\n"
            "print(4 not in items)\n"
            "print(\"aa\" in pair)\n"
            "print(\"cc\" not in pair)\n",
            run=True,
        )
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertIn("py_list_contains_int", c_code)
        self.assertIn("py_tuple_contains_str", c_code)
        self.assertEqual(run_output.strip().splitlines(), ["True", "True", "True", "True"])

    def test_compile_source_rejects_unknown_container_display_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "def choose(flag):\n"
                "    if flag:\n"
                "        return [1, 2]\n"
                "    return [3, 4]\n\n"
                "items = choose(True)\n"
                "print(items)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn(
            "native compilation only supports printing homogeneous primitive-element containers plus str()/repr() on that subset for now",
            result.errors.render(),
        )

    def test_compile_source_rejects_unknown_container_compare_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "def choose(flag):\n"
                "    if flag:\n"
                "        return [1, 2]\n"
                "    return [3, 4]\n\n"
                "items = choose(True)\n"
                "print(items == [1, 2])\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn(
            "native compilation only supports list/tuple equality, membership, and truthy/display semantics on homogeneous primitive-element containers for now",
            result.errors.render(),
        )

    def test_compile_source_rejects_unsupported_stringification_for_native_path(self):
        samples = [
            "print(repr(1))\n",
            "print(ascii([1, 2]))\n",
        ]
        for source in samples:
            with self.subTest(source=source):
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_path = os.path.join(temp_dir, "program.c")
                    result = compile_source(source, filename="inline.py", output=output_path)
                self.assertFalse(result.success)
                self.assertIn(
                    "native compilation only supports printing homogeneous primitive-element containers plus str()/repr() on that subset for now",
                    result.errors.render(),
                )

    def test_compile_source_rejects_default_and_keyword_arguments_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "def add(a, b=1):\n"
                "    return a + b\n\n"
                "print(add(a=2))\n",
                filename="inline.py",
                output=output_path,
        )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support default or keyword arguments yet", result.errors.render())

    def test_compile_source_rejects_varargs_kwargs_and_keyword_only_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "def collect(a, *rest, flag=False, **named):\n"
                "    return a\n\n"
                "print(collect(1, 2, flag=True, extra=3))\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support default or keyword arguments yet", result.errors.render())

    def test_compile_source_rejects_core_vm_only_features_for_native_path(self):
        samples = [
            "a, b = (1, 2)\nprint(a)\n",
            "items = [1, 2]\ndel items[0]\nprint(len(items))\n",
            "x = 1\ndef update():\n    global x\n    x = x + 1\nprint(x)\n",
        ]
        for source in samples:
            with self.subTest(source=source):
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_path = os.path.join(temp_dir, "program.c")
                    result = compile_source(source, filename="inline.py", output=output_path)
                self.assertFalse(result.success)
                rendered = result.errors.render()
                self.assertIn(
                    "native compilation does not support unpacking assignment, delete, global/nonlocal, or with statements yet",
                    rendered,
                )

    def test_compile_source_rejects_comprehensions_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "nums = [1, 2]\nprint([x for x in nums])\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support comprehensions yet", result.errors.render())

    def test_compile_source_rejects_comparison_chaining_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "print(1 < 2 < 3)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support comparison chaining yet", result.errors.render())

    def test_compile_source_rejects_with_statement_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "class CM:\n"
                "    def __enter__(self):\n"
                "        return 1\n"
                "    def __exit__(self, exc_type, exc, tb):\n"
                "        pass\n"
                "with CM() as value:\n"
                "    print(value)\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn(
            "native compilation does not support unpacking assignment, delete, global/nonlocal, or with statements yet",
            result.errors.render(),
        )

    def test_compile_source_rejects_inheritance_and_super_for_native_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "program.c")
            result = compile_source(
                "class Base:\n"
                "    def greet(self):\n"
                "        return \"base\"\n"
                "class Child(Base):\n"
                "    def greet(self):\n"
                "        return super().greet()\n"
                "print(Child().greet())\n",
                filename="inline.py",
                output=output_path,
            )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support classes, attributes, or methods yet", result.errors.render())

    def test_unpack_count_mismatch_fails_at_runtime(self):
        result, _, rendered = self.execute_program("a, b = (1, 2, 3)\n")
        self.assertFalse(result.success)
        self.assertIn("unpack expected 2 values, got 3", rendered)

    def test_starred_unpacking_is_supported(self):
        result, run_output, rendered = self.execute_program(
            "a, *rest = [1, 2, 3]\n"
            "print(a)\n"
            "print(rest)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "[2, 3]"])

    def test_nonlocal_without_enclosing_binding_is_rejected(self):
        result, _, rendered = self.execute_program(
            "def outer():\n"
            "    def inner():\n"
            "        nonlocal missing\n"
            "        missing = 1\n"
            "    return inner()\n"
            "print(outer())\n"
        )
        self.assertFalse(result.success)
        self.assertIn("no binding for nonlocal 'missing' found", rendered)

    def test_forward_reference_compiles(self):
        source = (
            "print(later(5))\n\n"
            "def later(x):\n"
            "    return x + 3\n"
        )
        result, _, run_output, rendered, _, _, _, executable_exists = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertTrue(executable_exists)
        self.assertEqual(run_output.strip().splitlines(), ["8"])

    def test_short_circuit_runtime(self):
        source = (
            "def side():\n"
            "    print(99)\n"
            "    return True\n\n"
            "if True or side():\n"
            "    print(1)\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1"])

    def test_native_rejects_try_except_else_finally(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "    except Exception:\n"
            "        print(\"except\")\n"
            "    else:\n"
            "        print(\"else\")\n"
            "    finally:\n"
            "        print(\"finally\")\n\n"
            "f()\n"
        )
        result, _, _, rendered, _, _, _, _ = self.compile_program(source, run=False)
        self.assertFalse(result.success)
        self.assertIn("try/except or try/finally without else", rendered)

    def test_native_exception_path_runs_finally(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "        raise \"boom\"\n"
            "    except Exception:\n"
            "        print(\"except\")\n"
            "    finally:\n"
            "        print(\"finally\")\n\n"
            "f()\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["try", "except", "finally"])

    def test_native_nested_finally_inside_except(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        raise \"boom\"\n"
            "    except Exception:\n"
            "        try:\n"
            "            print(\"inner try\")\n"
            "        finally:\n"
            "            print(\"inner finally\")\n"
            "    finally:\n"
            "        print(\"outer finally\")\n\n"
            "f()\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["inner try", "inner finally", "outer finally"])

    def test_native_try_finally_return_override(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        return 1\n"
            "    finally:\n"
            "        return 2\n\n"
            "print(f())\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["2"])

    def test_native_try_finally_break(self):
        source = (
            "for i in range(3):\n"
            "    try:\n"
            "        print(i)\n"
            "        break\n"
            "    finally:\n"
            "        print(\"cleanup\")\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "cleanup"])

    def test_native_try_finally_continue(self):
        source = (
            "for i in range(2):\n"
            "    try:\n"
            "        print(i)\n"
            "        continue\n"
            "    finally:\n"
            "        print(\"finally\")\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "finally", "1", "finally"])

    def test_native_exception_in_finally(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        print(\"try\")\n"
            "    finally:\n"
            "        print(\"finally\")\n"
            "        raise \"boom\"\n\n"
            "try:\n"
            "    f()\n"
            "except Exception:\n"
            "    print(\"caught\")\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["try", "finally", "caught"])

    def test_native_nested_reraise(self):
        source = (
            "def f():\n"
            "    try:\n"
            "        raise \"boom\"\n"
            "    except Exception:\n"
            "        print(\"inner\")\n"
            "        raise\n\n"
            "try:\n"
            "    f()\n"
            "except Exception:\n"
            "    print(\"outer\")\n"
        )
        result, _, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["inner", "outer"])

    def test_wrong_argument_count_fails(self):
        source = (
            "def add(a, b):\n"
            "    return a + b\n\n"
            "print(add(1))\n"
        )
        result, _, _, rendered, _, _, _, _ = self.compile_program(source, run=False)
        self.assertFalse(result.success)
        self.assertIn("missing required argument 'b'", rendered)

    def test_bare_raise_outside_except_fails(self):
        result, _, rendered = self.execute_program("raise\n")
        self.assertFalse(result.success)
        self.assertIn("bare raise is only valid inside an except block", rendered)

    def test_duplicate_keyword_argument_fails(self):
        source = (
            "def add(a, b=1):\n"
            "    return a + b\n\n"
            "print(add(1, a=2))\n"
        )
        result, _, _, rendered, _, _, _, _ = self.compile_program(source, run=False)
        self.assertFalse(result.success)
        self.assertIn("got multiple values for argument 'a'", rendered)

    def test_missing_keyword_only_argument_fails(self):
        source = (
            "def configure(*, flag):\n"
            "    return flag\n\n"
            "print(configure())\n"
        )
        result, _, _, rendered, _, _, _, _ = self.compile_program(source, run=False)
        self.assertFalse(result.success)
        self.assertIn("missing required keyword-only argument 'flag'", rendered)

    def test_execute_source_supports_generators_with_next(self):
        result, run_output, rendered = self.execute_program(
            "def gen():\n"
            "    yield 1\n"
            "    x = yield 2\n"
            "    print(x is None)\n"
            "    yield 3\n\n"
            "g = gen()\n"
            "print(next(g))\n"
            "print(next(g))\n"
            "print(next(g))\n"
            "try:\n"
            "    next(g)\n"
            "except StopIteration:\n"
            "    print(\"done\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2", "True", "3", "done"])

    def test_execute_source_supports_generators_in_for_loops(self):
        result, run_output, rendered = self.execute_program(
            "def count(n):\n"
            "    i = 0\n"
            "    while i < n:\n"
            "        yield i\n"
            "        i = i + 1\n\n"
            "for value in count(3):\n"
            "    print(value)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "1", "2"])

    def test_execute_source_supports_generator_expressions(self):
        result, run_output, rendered = self.execute_program(
            "base = 10\n"
            "g = (base + x for x in [1, 2, 3] if x > 1)\n"
            "print(next(g))\n"
            "print(next(g))\n"
            "try:\n"
            "    next(g)\n"
            "except StopIteration:\n"
            "    print(\"done\")\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["12", "13", "done"])

    def test_execute_source_supports_yield_from(self):
        result, run_output, rendered = self.execute_program(
            "def inner():\n"
            "    yield 1\n"
            "    yield 2\n\n"
            "def outer():\n"
            "    yield 0\n"
            "    result = yield from inner()\n"
            "    print(result is None)\n"
            "    yield 3\n\n"
            "for value in outer():\n"
            "    print(value)\n"
        )
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["0", "1", "2", "True", "3"])

    def test_compile_source_rejects_generators_for_native_path(self):
        result, _, _, rendered, _, _, _, _ = self.compile_program(
            "def gen():\n"
            "    yield 1\n"
            "for value in gen():\n"
            "    print(value)\n",
            run=False,
        )
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support generators or yield yet", rendered)

    def test_invalid_syntax_is_fatal(self):
        result, _, _, rendered, _, _, _, _ = self.compile_program("x = 1 $ 2\n", run=False)
        self.assertFalse(result.success)
        self.assertIn("Syntax Error", rendered)

    def test_missing_return_path_is_rejected(self):
        source = (
            "def maybe(x):\n"
            "    if x > 0:\n"
            "        return x\n\n"
            "print(maybe(1))\n"
        )
        result, _, _, rendered, _, _, _, _ = self.compile_program(source, run=False)
        self.assertFalse(result.success)
        self.assertIn("may exit without returning", rendered)

    def test_codegen_uses_lowered_ssa_after_merge_folding(self):
        source = (
            "def choose(flag):\n"
            "    if flag:\n"
            "        x = 1\n"
            "    else:\n"
            "        x = 1\n"
            "    return x + 2\n\n"
            "print(choose(True))\n"
        )
        result, c_code, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["3"])
        self.assertNotIn(" = x + 2;", c_code)
        self.assertIn("_t7 = 3;", c_code)

    def test_top_level_locals_do_not_emit_unused_globals(self):
        source = (
            "x = 3\n"
            "while x > 0:\n"
            "    print(x)\n"
            "    x -= 1\n"
        )
        result, c_code, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["3", "2", "1"])
        self.assertNotIn("\nint x = 0;\n", c_code)
        self.assertIn("int x__ssa_", c_code)

    def test_codegen_uses_ssa_value_propagation_for_identities(self):
        source = (
            "def clean(x):\n"
            "    y = x + 0\n"
            "    z = y * 1\n"
            "    return z\n\n"
            "print(clean(7))\n"
        )
        result, c_code, run_output, rendered, _, _, _, _ = self.compile_program(source, run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["7"])
        self.assertNotIn(" + 0;", c_code)
        self.assertNotIn(" * 1;", c_code)

    def test_codegen_routes_print_through_runtime_helpers(self):
        result, c_code, run_output, rendered, _, _, _, _ = self.compile_program('print(1)\nprint(2.5)\nprint("hi")\n', run=True)
        self.assertTrue(result.success, rendered)
        self.assertEqual(run_output.strip().splitlines(), ["1", "2.5", "hi"])
        self.assertIn("py_write_int(", c_code)
        self.assertIn("py_write_float(", c_code)
        self.assertIn("py_write_str(", c_code)
        self.assertIn('#include "py_runtime.h"', c_code)
        self.assertNotIn('printf("%d\\n", _t', c_code)
        self.assertNotIn('printf("%g\\n", _t', c_code)
        self.assertNotIn('printf("%s\\n", _t', c_code)


if __name__ == "__main__":
    unittest.main()
