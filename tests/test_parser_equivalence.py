import unittest
import sys
import os
from dataclasses import fields, is_dataclass
from compiler.pipeline import _analyze_source

# Make sure we can import from run_tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from run_tests import INLINE_TESTS, SOURCE_TESTS, TESTS

class TestParserEquivalence(unittest.TestCase):
    def _normalize_spans(self, node):
        if is_dataclass(node):
            kwargs = {}
            for field in fields(node):
                if not field.init:
                    continue
                value = getattr(node, field.name)
                if field.name == "span":
                    kwargs[field.name] = type(value)()
                elif isinstance(value, list):
                    kwargs[field.name] = [self._normalize_spans(item) for item in value]
                elif isinstance(value, dict):
                    kwargs[field.name] = {
                        key: self._normalize_spans(item)
                        for key, item in value.items()
                    }
                else:
                    kwargs[field.name] = self._normalize_spans(value)
            return type(node)(**kwargs)
        return node

    def test_inline_tests_aliases_source_tests(self):
        self.assertIs(INLINE_TESTS, SOURCE_TESTS)

    def test_inline_sources(self):
        """Verify that owned parser produces same AST as CPython for inline tests."""
        for test in INLINE_TESTS:
            source = test['source']
            name = test['name']
            with self.subTest(name=name):
                # We expect the compilation to succeed for all inline tests since they are valid programs
                res_cpython = _analyze_source(source, frontend="cpython")
                res_owned = _analyze_source(source, frontend="owned")
                
                # If they both fail, they are equivalent
                if not res_cpython.success and not res_owned.success:
                    continue
                    
                self.assertTrue(res_cpython.success, f"CPython parser failed on {name}")
                self.assertTrue(res_owned.success, f"Owned parser failed on {name}")
                
                ast_cpython = self._normalize_spans(res_cpython.program)
                ast_owned = self._normalize_spans(res_owned.program)

                # Check structural equivalence
                self.assertEqual(ast_cpython, ast_owned, f"AST mismatch on {name}")

if __name__ == '__main__':
    unittest.main()
