import unittest

from compiler.runtime.c_runtime import CRuntimeSupport


class RuntimeGCScaffoldingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = CRuntimeSupport()

    def test_header_defines_gc_header_and_helpers(self):
        header = self.runtime.header_source()
        self.assertIn("typedef struct PyObjectHeader", header)
        self.assertIn("int refcount;", header)
        self.assertIn("int type_id;", header)
        self.assertIn("struct PyObjectHeader *gc_next;", header)
        self.assertIn("void *py_malloc(size_t size, int type_id);", header)
        self.assertIn("void py_dump_live_objects(void);", header)

    def test_impl_includes_leak_dump_and_typed_allocations(self):
        impl = self.runtime.implementation_source()
        self.assertIn("py_dump_live_objects", impl)
        self.assertIn("py_malloc_site", impl)
        self.assertIn("py_malloc(32, PY_TYPE_STR)", impl)


if __name__ == "__main__":
    unittest.main()
