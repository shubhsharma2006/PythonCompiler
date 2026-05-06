import unittest
from compiler import execute_source


class Tier2Phase1Tests(unittest.TestCase):

    def run_vm(self, source):
        result = execute_source(source, filename="test.py")
        self.assertTrue(result.success, result.errors.render())
        return result.run_output.strip().splitlines()

    def run_vm_expect_failure(self, source, substring):
        result = execute_source(source, filename="test.py")
        self.assertFalse(result.success)
        self.assertIn(substring, result.errors.render())

    # ── Assert ──────────────────────────────────────────────────────────

    def test_assert_passes_when_true(self):
        lines = self.run_vm("assert True\nprint('ok')\n")
        self.assertEqual(lines, ["ok"])

    def test_assert_raises_on_false(self):
        self.run_vm_expect_failure("assert False\n", "unhandled exception: assertion failed")

    def test_assert_with_message(self):
        self.run_vm_expect_failure(
            'assert False, "custom message"\n',
            "custom message",
        )

    def test_assert_with_expression(self):
        lines = self.run_vm("x = 5\nassert x > 0\nprint('positive')\n")
        self.assertEqual(lines, ["positive"])

    def test_assert_caught_by_except(self):
        lines = self.run_vm(
            "try:\n"
            "    assert False, 'boom'\n"
            "except AssertionError as e:\n"
            "    print('caught')\n"
        )
        self.assertEqual(lines, ["caught"])

    # ── Ternary ─────────────────────────────────────────────────────────

    def test_ternary_true_branch(self):
        lines = self.run_vm("x = 1 if True else 2\nprint(x)\n")
        self.assertEqual(lines, ["1"])

    def test_ternary_false_branch(self):
        lines = self.run_vm("x = 1 if False else 2\nprint(x)\n")
        self.assertEqual(lines, ["2"])

    def test_ternary_with_condition_variable(self):
        lines = self.run_vm("flag = 10 > 5\nx = 'yes' if flag else 'no'\nprint(x)\n")
        self.assertEqual(lines, ["yes"])

    def test_ternary_nested(self):
        lines = self.run_vm(
            "x = 3\n"
            "label = 'big' if x > 10 else ('medium' if x > 1 else 'small')\n"
            "print(label)\n"
        )
        self.assertEqual(lines, ["medium"])

    def test_ternary_in_expression(self):
        lines = self.run_vm("print((10 if True else 0) + 5)\n")
        self.assertEqual(lines, ["15"])

    def test_ternary_constant_folding(self):
        # The optimizer should fold this at compile time
        lines = self.run_vm("x = 42 if True else 0\nprint(x)\n")
        self.assertEqual(lines, ["42"])

    def test_ternary_in_function(self):
        lines = self.run_vm(
            "def classify(n):\n"
            "    return 'even' if n % 2 == 0 else 'odd'\n"
            "print(classify(4))\n"
            "print(classify(7))\n"
        )
        self.assertEqual(lines, ["even", "odd"])

    # ── Lambda ──────────────────────────────────────────────────────────

    def test_lambda_basic(self):
        lines = self.run_vm("f = lambda x: x * 2\nprint(f(5))\n")
        self.assertEqual(lines, ["10"])

    def test_lambda_multi_param(self):
        lines = self.run_vm("add = lambda a, b: a + b\nprint(add(3, 4))\n")
        self.assertEqual(lines, ["7"])

    def test_lambda_no_params(self):
        lines = self.run_vm("f = lambda: 42\nprint(f())\n")
        self.assertEqual(lines, ["42"])

    def test_lambda_as_argument(self):
        lines = self.run_vm(
            "def apply(f, x):\n"
            "    return f(x)\n"
            "print(apply(lambda x: x + 1, 9))\n"
        )
        self.assertEqual(lines, ["10"])

    def test_lambda_with_default(self):
        lines = self.run_vm("f = lambda x, y=10: x + y\nprint(f(5))\nprint(f(5, 3))\n")
        self.assertEqual(lines, ["15", "8"])

    def test_lambda_captures_closure(self):
        lines = self.run_vm(
            "def make_adder(n):\n"
            "    return lambda x: x + n\n"
            "add5 = make_adder(5)\n"
            "print(add5(3))\n"
        )
        self.assertEqual(lines, ["8"])

    def test_lambda_with_sorted(self):
        lines = self.run_vm(
            "items = [3, 1, 4, 1, 5]\n"
            "result = sorted(items, key=lambda x: -x)\n"
            "print(result[0])\n"
        )
        self.assertEqual(lines, ["5"])


if __name__ == "__main__":
    unittest.main()
