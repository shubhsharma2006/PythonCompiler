import unittest

from compiler.frontend import lex_source, lower_cst, parse_tokens
from compiler.utils.error_handler import ErrorHandler


class FrontendTests(unittest.TestCase):
    def frontend(self, source: str):
        errors = ErrorHandler(source, "test_case.py")
        lexed = lex_source(source, "test_case.py", errors)
        parsed = parse_tokens(lexed, errors) if lexed is not None else None
        program = lower_cst(parsed, errors) if parsed is not None else None
        return lexed, parsed, program, errors

    def test_parses_valid_python_subset(self):
        lexed, parsed, program, errors = self.frontend(
            "x = 1\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "if x > 0:\n"
            "    print(add(x, 2))\n"
        )
        self.assertIsNotNone(lexed)
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())
        self.assertEqual(len(program.body), 3)
        self.assertGreater(len(lexed.tokens), 0)

    def test_lowers_import_statements(self):
        _, _, program, errors = self.frontend("import math\nimport os.path\nfrom util import add\n")
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())
        self.assertEqual(len(program.body), 3)

    def test_lowers_multi_argument_print_and_keywords(self):
        _, _, program, errors = self.frontend('print("hello", "world", sep=", ", end="!")\n')
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_default_arguments_and_keyword_calls(self):
        _, _, program, errors = self.frontend(
            "def greet(name, greeting=\"Hello\"):\n"
            "    return greeting + \", \" + name\n\n"
            "print(greet(name=\"Ada\"))\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_varargs_kwargs_and_keyword_only_parameters(self):
        _, _, program, errors = self.frontend(
            "def collect(a, *rest, flag=True, **named):\n"
            "    return a\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_f_string(self):
        _, _, program, errors = self.frontend('name = "Ada"\nprint(f"Hello {name}")\n')
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_membership_and_identity_compare(self):
        _, _, program, errors = self.frontend("items = [1, 2]\nprint(1 in items)\nprint(items is items)\n")
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_dict_and_set_literals(self):
        _, _, program, errors = self.frontend('d = {"a": 1}\ns = {1, 2, 3}\nprint(d["a"])\n')
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_comprehensions(self):
        _, _, program, errors = self.frontend(
            "nums = [1, 2, 3]\n"
            "doubled = [x * 2 for x in nums if x > 1]\n"
            "mapping = {x: x + 1 for x in nums}\n"
            "unique = {x for x in nums if x != 2}\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_nested_function(self):
        _, _, program, errors = self.frontend(
            "def outer(x):\n"
            "    def inner(y):\n"
            "        return y\n"
            "    return inner(x)\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_try_and_raise(self):
        _, _, program, errors = self.frontend(
            "try:\n"
            "    raise \"boom\"\n"
            "except:\n"
            "    print(\"handled\")\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())
        self.assertEqual(len(program.body), 1)

    def test_lowers_typed_except_with_binding(self):
        _, _, program, errors = self.frontend(
            "class MyError:\n"
            "    def __init__(self, message):\n"
            "        self.message = message\n"
            "try:\n"
            "    raise MyError(\"boom\")\n"
            "except MyError as err:\n"
            "    print(err.message)\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_try_finally(self):
        _, _, program, errors = self.frontend(
            "try:\n"
            "    print(1)\n"
            "finally:\n"
            "    print(2)\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_for_range_loop(self):
        _, _, program, errors = self.frontend(
            "for i in range(3):\n"
            "    print(i)\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())
        self.assertEqual(len(program.body), 1)

    def test_lowers_list_tuple_and_indexing(self):
        _, _, program, errors = self.frontend(
            "items = [1, 2, 3]\n"
            "pair = (4, 5)\n"
            "print(items[1])\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())
        self.assertEqual(len(program.body), 3)

    def test_lowers_core_vm_gap_nodes(self):
        _, _, program, errors = self.frontend(
            "items = [1, 2, 3]\n"
            "a, b = items[:2]\n"
            "pass\n"
            "del items[0]\n"
            "x = 1\n"
            "def update():\n"
            "    global x\n"
            "    x = x + 1\n"
            "def outer():\n"
            "    y = 1\n"
            "    def inner():\n"
            "        nonlocal y\n"
            "        y = y + 1\n"
            "        return y\n"
            "    return inner()\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_with_statement(self):
        _, _, program, errors = self.frontend(
            "class CM:\n"
            "    def __enter__(self):\n"
            "        return 1\n"
            "    def __exit__(self, exc_type, exc, tb):\n"
            "        pass\n"
            "with CM() as value:\n"
            "    print(value)\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_class_methods_and_attributes(self):
        _, _, program, errors = self.frontend(
            "class Counter:\n"
            "    def __init__(self, start):\n"
            "        self.value = start\n"
            "    def inc(self):\n"
            "        self.value = self.value + 1\n"
            "        return self.value\n"
            "counter = Counter(2)\n"
            "print(counter.inc())\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lowers_class_inheritance_super_and_class_attributes(self):
        _, _, program, errors = self.frontend(
            "class Base:\n"
            "    kind = \"base\"\n"
            "    def greet(self):\n"
            "        return self.kind\n"
            "class Child(Base):\n"
            "    kind = \"child\"\n"
            "    def greet(self):\n"
            "        return super().greet()\n"
        )
        self.assertIsNotNone(program)
        self.assertFalse(errors.has_errors(), errors.render())

    def test_lexer_emits_python_tokens(self):
        errors = ErrorHandler("x = 1 + 2\n", "tokens.py")
        lexed = lex_source("x = 1 + 2\n", "tokens.py", errors)
        self.assertIsNotNone(lexed)
        self.assertFalse(errors.has_errors(), errors.render())
        kinds = [token.kind for token in lexed.tokens[:5]]
        self.assertIn("NAME", kinds)
        self.assertIn("NUMBER", kinds)


if __name__ == "__main__":
    unittest.main()
