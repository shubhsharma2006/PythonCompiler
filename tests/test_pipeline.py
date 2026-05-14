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

    def test_compile_source_rejects_exceptions_for_native_path(self):
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
        self.assertFalse(result.success)
        self.assertIn("native compilation does not support exceptions yet", result.errors.render())

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
            "items = [1, 2]\nprint(items[:1])\n",
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
                self.assertIn(
                    "native compilation does not support slicing, unpacking assignment, delete, global/nonlocal, or with statements yet",
                    result.errors.render(),
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
        self.assertIn("native compilation does not support lists, tuples, indexing, or len() yet", result.errors.render())

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
        self.assertIn("native compilation does not support slicing, unpacking assignment, delete, global/nonlocal, or with statements yet", result.errors.render())

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
