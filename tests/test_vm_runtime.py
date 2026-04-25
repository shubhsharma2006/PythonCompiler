import unittest

from compiler.vm.builtins import build_builtins, builtin_len, builtin_range
from compiler.vm.bytecode import BytecodeFunction
from compiler.vm.errors import VMError
from compiler.vm.objects import (
    ClassObject,
    InstanceObject,
    ModuleObject,
    PyListObject,
    PyStrObject,
    py_binary_op,
    bind_function_args,
    py_compare_op,
    py_index_get,
    py_load_attr,
    py_matches_exception,
    py_store_attr,
    py_truthy,
    unwrap_runtime_value,
)


class _Host:
    def __init__(self) -> None:
        self.output: list[str] = []
        self._globals = {"g": 1}
        self._locals = {"l": 2}

    def format_value(self, value: object) -> str:
        return repr(value) if isinstance(value, float) else str(value)

    def current_globals(self) -> dict[str, object]:
        return dict(self._globals)

    def current_locals(self) -> dict[str, object]:
        return dict(self._locals)

    def build_super(self, *args) -> object:
        return args


class VMRuntimeTests(unittest.TestCase):
    def test_unwrap_runtime_value_returns_underlying_python_value(self):
        self.assertEqual(unwrap_runtime_value(PyStrObject("hello")), "hello")
        self.assertEqual(unwrap_runtime_value(7), 7)

    def test_runtime_helpers_accept_wrapped_values(self):
        wrapped = PyListObject([1, 2, 3])
        self.assertTrue(py_truthy(wrapped))
        self.assertEqual(py_index_get(wrapped, 1), 2)
        self.assertEqual(py_binary_op("+", PyStrObject("a"), PyStrObject("b")), "ab")
        self.assertTrue(py_compare_op("in", 2, wrapped))

    def test_runtime_attribute_helpers_support_instances_and_modules(self):
        method = BytecodeFunction(key="Counter.inc", name="inc", params=["self"])
        class_object = ClassObject(name="Counter", methods={"inc": method})
        instance = InstanceObject(class_object=class_object)
        py_store_attr(instance, "value", 3)
        self.assertEqual(py_load_attr(instance, "value"), 3)
        bound = py_load_attr(instance, "inc")
        self.assertEqual(bound.instance, instance)
        self.assertEqual(bound.function, method)

        module = ModuleObject(name="m", filename="m.py", namespace={})
        py_store_attr(module, "answer", 42)
        self.assertEqual(py_load_attr(module, "answer"), 42)

    def test_runtime_attribute_helpers_support_class_attributes_and_inheritance(self):
        base_method = BytecodeFunction(key="Base.greet", name="greet", params=["self"])
        base = ClassObject(name="Base", methods={"greet": base_method}, attributes={"kind": "base"})
        child = ClassObject(name="Child", methods={}, bases=[base], attributes={"label": "child"})
        instance = InstanceObject(class_object=child)
        self.assertEqual(py_load_attr(instance, "kind"), "base")
        self.assertEqual(py_load_attr(child, "kind"), "base")
        self.assertEqual(py_load_attr(child, "label"), "child")
        bound = py_load_attr(instance, "greet")
        self.assertEqual(bound.instance, instance)
        self.assertEqual(bound.function, base_method)

    def test_builtin_registry_is_hosted_outside_interpreter(self):
        host = _Host()
        builtins = build_builtins(host)
        builtins["print"]("hello", "world", sep=", ", end="!")
        self.assertEqual(host.output, ["hello, world!"])
        self.assertEqual(builtins["globals"](), {"g": 1})
        self.assertEqual(builtins["locals"](), {"l": 2})

    def test_builtin_len_and_range_validate_arguments(self):
        self.assertEqual(builtin_len(PyListObject([1, 2])), 2)
        self.assertEqual(list(builtin_range(1, 4)), [1, 2, 3])
        with self.assertRaises(VMError):
            builtin_range(True)

    def test_bind_function_args_applies_defaults_and_keywords(self):
        args = bind_function_args("combine", ["a", "b", "c"], [3], [1], {"b": 2})
        self.assertEqual(args, {"a": 1, "b": 2, "c": 3})

    def test_bind_function_args_rejects_duplicate_keyword(self):
        with self.assertRaisesRegex(VMError, "multiple values"):
            bind_function_args("combine", ["a", "b"], [], [1], {"a": 2})

    def test_bind_function_args_supports_varargs_kwargs_and_kwonly(self):
        args = bind_function_args(
            "collect",
            ["a"],
            [],
            [1, 2, 3],
            {"flag": True, "extra": 9},
            kwonly_params=["flag"],
            kwonly_defaults={},
            vararg_name="rest",
            kwarg_name="named",
        )
        self.assertEqual(args["a"], 1)
        self.assertEqual(args["rest"], (2, 3))
        self.assertEqual(args["flag"], True)
        self.assertEqual(args["named"], {"extra": 9})

    def test_py_matches_exception_supports_host_exception_hierarchy(self):
        self.assertTrue(py_matches_exception(ValueError("boom"), Exception))
        self.assertTrue(py_matches_exception(ValueError("boom"), ValueError))
        self.assertFalse(py_matches_exception(ValueError("boom"), KeyError))

    def test_py_matches_exception_supports_custom_class_hierarchy(self):
        base = ClassObject(name="BaseError", methods={})
        child = ClassObject(name="ChildError", methods={}, bases=[base])
        err = InstanceObject(class_object=child)
        self.assertTrue(py_matches_exception(err, base))
        self.assertTrue(py_matches_exception(err, "BaseError"))
        self.assertFalse(py_matches_exception(err, "OtherError"))


if __name__ == "__main__":
    unittest.main()
