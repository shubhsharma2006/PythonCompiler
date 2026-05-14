from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from compiler.core.signature import bind_call_arguments
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
    kwonly_defaults: dict[str, object] = field(default_factory=dict)


@dataclass
class ClassObject:
    name: str
    methods: dict[str, BytecodeFunction]
    bases: list["ClassObject"] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)


@dataclass
class InstanceObject:
    class_object: ClassObject
    fields: dict[str, object] = field(default_factory=dict)


@dataclass
class BoundMethod:
    instance: InstanceObject | ModuleObject
    function: object


@dataclass
class SuperObject:
    owner_class: ClassObject
    instance: InstanceObject


_MISSING = object()


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
    if op == "//":
        return left // right
    if op == "**":
        return left ** right
    if op == "&":
        return left & right
    if op == "|":
        return left | right
    if op == "^":
        return left ^ right
    if op == "<<":
        return left << right
    if op == ">>":
        return left >> right

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

    if op == "+":
        return +operand

    if op == "not":
        return not py_truthy(operand)

    if op == "~":
        return ~operand

    raise VMError(f"unsupported unary operator {op!r}")


def py_index_get(collection: object, index: object) -> object:
    collection = unwrap_runtime_value(collection)
    index = unwrap_runtime_value(index)

    try:
        return collection[index]
    except (IndexError, KeyError, TypeError) as exc:
        raise VMError(str(exc)) from None


def py_index_set(collection: object, index: object, value: object) -> None:
    collection = unwrap_runtime_value(collection)
    index = unwrap_runtime_value(index)
    value = unwrap_runtime_value(value)

    try:
        collection[index] = value
    except (IndexError, KeyError, TypeError) as exc:
        raise VMError(str(exc)) from None


def py_index_delete(collection: object, index: object) -> None:
    collection = unwrap_runtime_value(collection)
    index = unwrap_runtime_value(index)

    try:
        del collection[index]
    except (IndexError, KeyError, TypeError) as exc:
        raise VMError(str(exc)) from None


def class_is_subclass(
    subclass: ClassObject,
    superclass: ClassObject | str,
) -> bool:
    if isinstance(superclass, str):
        if subclass.name == superclass:
            return True
    elif subclass is superclass:
        return True

    for base in subclass.bases:
        if class_is_subclass(base, superclass):
            return True

    return False


def _find_class_member(class_object: ClassObject, attr_name: str) -> object:
    if attr_name in class_object.attributes:
        return class_object.attributes[attr_name]

    if attr_name in class_object.methods:
        return class_object.methods[attr_name]

    for base in class_object.bases:
        value = _find_class_member(base, attr_name)
        if value is not _MISSING:
            return value

    return _MISSING


def _find_super_member(class_object: ClassObject, attr_name: str) -> object:
    for base in class_object.bases:
        value = _find_class_member(base, attr_name)

        if value is not _MISSING:
            return value

    return _MISSING


def py_load_attr(obj: object, attr_name: str) -> object:
    obj = unwrap_runtime_value(obj)

    if isinstance(obj, ModuleObject):
        if attr_name not in obj.namespace:
            raise VMError(
                f"module {obj.name!r} has no attribute {attr_name!r}"
            )

        return obj.namespace[attr_name]

    if isinstance(obj, InstanceObject):
        if attr_name in obj.fields:
            return obj.fields[attr_name]

        member = _find_class_member(obj.class_object, attr_name)

        if member is not _MISSING:
            if isinstance(member, BytecodeFunction) or callable(member):
                return BoundMethod(instance=obj, function=member)

            return member

        raise VMError(
            f"instance of {obj.class_object.name!r} "
            f"has no attribute {attr_name!r}"
        )

    if isinstance(obj, ClassObject):
        member = _find_class_member(obj, attr_name)

        if member is not _MISSING:
            return member

        raise VMError(
            f"class {obj.name!r} has no attribute {attr_name!r}"
        )

    if isinstance(obj, SuperObject):
        member = _find_super_member(obj.owner_class, attr_name)

        if member is _MISSING:
            raise VMError(
                f"super object for {obj.owner_class.name!r} "
                f"has no attribute {attr_name!r}"
            )

        if isinstance(member, BytecodeFunction) or callable(member):
            return BoundMethod(instance=obj.instance, function=member)

        return member

    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)

    raise VMError(
        f"cannot access attribute {attr_name!r} "
        f"on {type(obj).__name__}"
    )


def py_store_attr(obj: object, attr_name: str, value: object) -> None:
    obj = unwrap_runtime_value(obj)
    value = unwrap_runtime_value(value)

    if isinstance(obj, InstanceObject):
        obj.fields[attr_name] = value
        return

    if isinstance(obj, ClassObject):
        obj.attributes[attr_name] = value
        return

    if isinstance(obj, ModuleObject):
        obj.namespace[attr_name] = value
        return

    raise VMError(
        f"cannot set attribute {attr_name!r} "
        f"on {type(obj).__name__}"
    )


def py_delete_attr(obj: object, attr_name: str) -> None:
    obj = unwrap_runtime_value(obj)

    if isinstance(obj, InstanceObject):
        if attr_name not in obj.fields:
            raise VMError(
                f"instance of {obj.class_object.name!r} "
                f"has no attribute {attr_name!r}"
            )

        del obj.fields[attr_name]
        return

    if isinstance(obj, ClassObject):
        if attr_name not in obj.attributes:
            raise VMError(
                f"class {obj.name!r} has no attribute {attr_name!r}"
            )

        del obj.attributes[attr_name]
        return

    if isinstance(obj, ModuleObject):
        if attr_name not in obj.namespace:
            raise VMError(
                f"module {obj.name!r} has no attribute {attr_name!r}"
            )

        del obj.namespace[attr_name]
        return

    if hasattr(obj, attr_name):
        try:
            delattr(obj, attr_name)
            return
        except AttributeError as exc:
            raise VMError(str(exc)) from None

    raise VMError(
        f"cannot delete attribute {attr_name!r} "
        f"on {type(obj).__name__}"
    )


def py_matches_exception(
    value: object,
    expected: object | str | None,
) -> bool:
    value = unwrap_runtime_value(value)

    if expected is None:
        return True

    if isinstance(expected, tuple):
        return any(
            py_matches_exception(value, item)
            for item in expected
        )

    expected = unwrap_runtime_value(expected)

    if isinstance(expected, str):
        if isinstance(value, InstanceObject):
            return class_is_subclass(value.class_object, expected)

        if isinstance(value, ClassObject):
            return class_is_subclass(value, expected)

        return type(value).__name__ == expected

    if isinstance(expected, ClassObject):
        if isinstance(value, InstanceObject):
            return class_is_subclass(value.class_object, expected)

        if isinstance(value, ClassObject):
            return class_is_subclass(value, expected)

        return False

    try:
        return isinstance(value, expected)
    except TypeError:
        return False


def py_invoke_callable(
    callable_obj: object,
    args: list[object],
    module: ModuleObject,
    *,
    kwargs: dict[str, object] | None = None,
    execute_function: Callable[
        [
            BytecodeFunction,
            dict[str, object],
            ModuleObject,
            list[dict[str, object]] | None,
        ],
        object,
    ],
) -> object:
    callable_obj = unwrap_runtime_value(callable_obj)

    args = [
        unwrap_runtime_value(arg)
        for arg in args
    ]

    kwargs = {
        key: unwrap_runtime_value(value)
        for key, value in (kwargs or {}).items()
    }

    if isinstance(callable_obj, BytecodeFunction):
        bound_args = bind_function_args(
            callable_obj.name,
            callable_obj.params,
            callable_obj.defaults,
            args,
            kwargs,
            kwonly_params=callable_obj.kwonly_params,
            kwonly_defaults=callable_obj.kwonly_defaults,
            vararg_name=callable_obj.vararg_name,
            kwarg_name=callable_obj.kwarg_name,
        )

        return execute_function(
            callable_obj,
            bound_args,
            module,
            None,
        )

    if isinstance(callable_obj, Closure):
        defaults = (
            callable_obj.defaults
            or callable_obj.function.defaults
        )

        kwonly_defaults = (
            callable_obj.kwonly_defaults
            or callable_obj.function.kwonly_defaults
        )

        bound_args = bind_function_args(
            callable_obj.function.name,
            callable_obj.function.params,
            defaults,
            args,
            kwargs,
            kwonly_params=callable_obj.function.kwonly_params,
            kwonly_defaults=kwonly_defaults,
            vararg_name=callable_obj.function.vararg_name,
            kwarg_name=callable_obj.function.kwarg_name,
        )

        return execute_function(
            callable_obj.function,
            bound_args,
            module,
            callable_obj.closure_scopes,
        )

    if isinstance(callable_obj, BoundMethod):
        if isinstance(callable_obj.function, BytecodeFunction):
            bound_args = bind_function_args(
                callable_obj.function.name,
                callable_obj.function.params,
                callable_obj.function.defaults,
                [callable_obj.instance, *args],
                kwargs,
                kwonly_params=callable_obj.function.kwonly_params,
                kwonly_defaults=callable_obj.function.kwonly_defaults,
                vararg_name=callable_obj.function.vararg_name,
                kwarg_name=callable_obj.function.kwarg_name,
            )

            return execute_function(
                callable_obj.function,
                bound_args,
                module,
                None,
            )

        if callable(callable_obj.function):
            return callable_obj.function(
                callable_obj.instance,
                *args,
                **kwargs,
            )

        raise VMError("invalid bound method")

    if isinstance(callable_obj, ClassObject):
        instance = InstanceObject(class_object=callable_obj)

        initializer = _find_class_member(
            callable_obj,
            "__init__",
        )

        if isinstance(initializer, BytecodeFunction):
            if initializer.is_generator:
                raise VMError("__init__ cannot be a generator function")
            bound_args = bind_function_args(
                initializer.name,
                initializer.params,
                initializer.defaults,
                [instance, *args],
                kwargs,
                kwonly_params=initializer.kwonly_params,
                kwonly_defaults=initializer.kwonly_defaults,
                vararg_name=initializer.vararg_name,
                kwarg_name=initializer.kwarg_name,
            )

            execute_function(
                initializer,
                bound_args,
                module,
                None,
            )

        elif args or kwargs:
            raise VMError(
                f"class {callable_obj.name!r} "
                f"takes no arguments"
            )

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
    *,
    kwonly_params: list[str] | None = None,
    kwonly_defaults: dict[str, object] | None = None,
    vararg_name: str | None = None,
    kwarg_name: str | None = None,
) -> dict[str, object]:
    try:
        return bind_call_arguments(
            function_name,
            params,
            defaults,
            args,
            kwargs,
            kwonly_params=kwonly_params,
            kwonly_defaults=kwonly_defaults,
            vararg_name=vararg_name,
            kwarg_name=kwarg_name,
        )

    except ValueError as exc:
        raise VMError(str(exc)) from None
