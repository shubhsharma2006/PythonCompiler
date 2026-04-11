from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from compiler.vm.bytecode import BytecodeFunction
from compiler.vm.errors import VMError


@dataclass
class PyObject:
    value: object


@dataclass
class PyIntObject(PyObject):
    value: int


@dataclass
class PyFloatObject(PyObject):
    value: float


@dataclass
class PyBoolObject(PyObject):
    value: bool


@dataclass
class PyStrObject(PyObject):
    value: str


@dataclass
class PyListObject(PyObject):
    value: list[object]


@dataclass
class PyTupleObject(PyObject):
    value: tuple[object, ...]


@dataclass
class PyDictObject(PyObject):
    value: dict[object, object]


@dataclass
class PySetObject(PyObject):
    value: set[object]


@dataclass
class PyExceptionObject(PyObject):
    type_name: str = "Exception"


@dataclass
class PyFunctionObject(PyObject):
    value: BytecodeFunction


@dataclass
class PyClassObject(PyObject):
    value: "ClassObject"


@dataclass
class PyInstanceObject(PyObject):
    value: "InstanceObject"


@dataclass
class ModuleObject:
    name: str
    filename: str
    namespace: dict[str, object]


@dataclass
class Closure:
    function: BytecodeFunction
    closure_scopes: list[dict[str, object]]
    defaults: list[object] = field(default_factory=list)


@dataclass
class ClassObject:
    name: str
    methods: dict[str, BytecodeFunction]


@dataclass
class InstanceObject:
    class_object: ClassObject
    fields: dict[str, object] = field(default_factory=dict)


@dataclass
class BoundMethod:
    instance: InstanceObject | ModuleObject
    function: object


def unwrap_runtime_value(value: object) -> object:
    return value.value if isinstance(value, PyObject) else value


def py_truthy(value: object) -> bool:
    return bool(unwrap_runtime_value(value))


def py_binary_op(op: str, left: object, right: object) -> object:
    left = unwrap_runtime_value(left)
    right = unwrap_runtime_value(right)
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right
    if op == "%":
        return left % right
    raise VMError(f"unsupported binary operator {op!r}")


def py_compare_op(op: str, left: object, right: object) -> bool:
    left = unwrap_runtime_value(left)
    right = unwrap_runtime_value(right)
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "in":
        return left in right
    if op == "not in":
        return left not in right
    if op == "is":
        return left is right
    if op == "is not":
        return left is not right
    raise VMError(f"unsupported comparison operator {op!r}")


def py_unary_op(op: str, operand: object) -> object:
    operand = unwrap_runtime_value(operand)
    if op == "-":
        return -operand
    if op == "not":
        return not py_truthy(operand)
    raise VMError(f"unsupported unary operator {op!r}")


def py_index_get(collection: object, index: object) -> object:
    collection = unwrap_runtime_value(collection)
    index = unwrap_runtime_value(index)
    try:
        return collection[index]
    except (IndexError, KeyError, TypeError) as exc:
        raise VMError(str(exc)) from None


def py_load_attr(obj: object, attr_name: str) -> object:
    obj = unwrap_runtime_value(obj)
    if isinstance(obj, ModuleObject):
        if attr_name not in obj.namespace:
            raise VMError(f"module {obj.name!r} has no attribute {attr_name!r}")
        return obj.namespace[attr_name]
    if isinstance(obj, InstanceObject):
        if attr_name in obj.fields:
            return obj.fields[attr_name]
        method = obj.class_object.methods.get(attr_name)
        if method is not None:
            return BoundMethod(instance=obj, function=method)
        raise VMError(f"instance of {obj.class_object.name!r} has no attribute {attr_name!r}")
    if isinstance(obj, ClassObject):
        method = obj.methods.get(attr_name)
        if method is not None:
            return method
        raise VMError(f"class {obj.name!r} has no attribute {attr_name!r}")
    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)
    raise VMError(f"cannot access attribute {attr_name!r} on {type(obj).__name__}")


def py_store_attr(obj: object, attr_name: str, value: object) -> None:
    obj = unwrap_runtime_value(obj)
    value = unwrap_runtime_value(value)
    if isinstance(obj, InstanceObject):
        obj.fields[attr_name] = value
        return
    if isinstance(obj, ModuleObject):
        obj.namespace[attr_name] = value
        return
    raise VMError(f"cannot set attribute {attr_name!r} on {type(obj).__name__}")


def py_matches_exception(value: object, type_name: str | None) -> bool:
    value = unwrap_runtime_value(value)
    if type_name is None:
        return True
    if isinstance(value, InstanceObject):
        return value.class_object.name == type_name
    if isinstance(value, ClassObject):
        return value.name == type_name
    return type(value).__name__ == type_name


def py_invoke_callable(
    callable_obj: object,
    args: list[object],
    module: ModuleObject,
    *,
    kwargs: dict[str, object] | None = None,
    execute_function: Callable[[BytecodeFunction, list[object], ModuleObject, list[dict[str, object]] | None], object],
) -> object:
    callable_obj = unwrap_runtime_value(callable_obj)
    args = [unwrap_runtime_value(arg) for arg in args]
    kwargs = {key: unwrap_runtime_value(value) for key, value in (kwargs or {}).items()}
    if isinstance(callable_obj, BytecodeFunction):
        bound_args = bind_function_args(callable_obj.name, callable_obj.params, callable_obj.defaults, args, kwargs)
        return execute_function(callable_obj, bound_args, module, None)
    if isinstance(callable_obj, Closure):
        defaults = callable_obj.defaults or callable_obj.function.defaults
        bound_args = bind_function_args(callable_obj.function.name, callable_obj.function.params, defaults, args, kwargs)
        return execute_function(callable_obj.function, bound_args, module, callable_obj.closure_scopes)
    if isinstance(callable_obj, BoundMethod):
        if isinstance(callable_obj.function, BytecodeFunction):
            bound_args = bind_function_args(
                callable_obj.function.name,
                callable_obj.function.params,
                callable_obj.function.defaults,
                [callable_obj.instance, *args],
                kwargs,
            )
            return execute_function(callable_obj.function, bound_args, module, None)
        if callable(callable_obj.function):
            return callable_obj.function(callable_obj.instance, *args, **kwargs)
        raise VMError("invalid bound method")
    if isinstance(callable_obj, ClassObject):
        instance = InstanceObject(class_object=callable_obj)
        initializer = callable_obj.methods.get("__init__")
        if initializer is not None:
            bound_args = bind_function_args(initializer.name, initializer.params, initializer.defaults, [instance, *args], kwargs)
            execute_function(initializer, bound_args, module, None)
        elif args or kwargs:
            raise VMError(f"class {callable_obj.name!r} takes no arguments")
        return instance
    if callable(callable_obj):
        try:
            return callable_obj(*args, **kwargs)
        except TypeError as exc:
            raise VMError(str(exc)) from None
    raise VMError(f"cannot call {callable_obj!r}")


def bind_function_args(
    function_name: str,
    params: list[str],
    defaults: list[object],
    args: list[object],
    kwargs: dict[str, object] | None = None,
) -> list[object]:
    kwargs = dict(kwargs or {})
    if len(args) > len(params):
        raise VMError(f"function {function_name!r} expects at most {len(params)} arguments, got {len(args)}")

    values: dict[str, object] = {}
    for index, arg in enumerate(args):
        values[params[index]] = arg

    for name, value in kwargs.items():
        if name not in params:
            raise VMError(f"function {function_name!r} got unexpected keyword argument {name!r}")
        if name in values:
            raise VMError(f"function {function_name!r} got multiple values for argument {name!r}")
        values[name] = value

    first_default_index = len(params) - len(defaults)
    for index, name in enumerate(params):
        if name in values:
            continue
        default_index = index - first_default_index
        if 0 <= default_index < len(defaults):
            values[name] = defaults[default_index]
            continue
        raise VMError(f"function {function_name!r} missing required argument {name!r}")

    return [values[name] for name in params]
