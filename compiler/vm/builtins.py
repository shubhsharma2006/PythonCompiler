from __future__ import annotations

import builtins as py_builtins
from typing import Protocol

from compiler.vm.errors import VMError
from compiler.vm.objects import ClassObject, InstanceObject, class_is_subclass, unwrap_runtime_value, py_load_attr


class BuiltinHost(Protocol):
    output: list[str]

    def format_value(self, value: object) -> str: ...

    def current_globals(self) -> dict[str, object]: ...

    def current_locals(self) -> dict[str, object]: ...

    def build_super(self, *args) -> object: ...

    def invoke_builtin_callable(self, callable_obj: object, *args, **kwargs) -> object: ...


def builtin_isinstance(obj: object, classinfo: object) -> bool:
    obj = unwrap_runtime_value(obj)
    classinfo = unwrap_runtime_value(classinfo)
    if isinstance(classinfo, tuple):
        return any(builtin_isinstance(obj, item) for item in classinfo)
    if isinstance(classinfo, ClassObject):
        return isinstance(obj, InstanceObject) and class_is_subclass(obj.class_object, classinfo)
    try:
        return isinstance(obj, classinfo)
    except TypeError as exc:
        raise VMError(str(exc)) from None


def builtin_issubclass(cls: object, classinfo: object) -> bool:
    cls = unwrap_runtime_value(cls)
    classinfo = unwrap_runtime_value(classinfo)
    if not isinstance(cls, ClassObject):
        try:
            return issubclass(cls, classinfo)
        except TypeError as exc:
            raise VMError(str(exc)) from None
    if isinstance(classinfo, tuple):
        return any(builtin_issubclass(cls, item) for item in classinfo)
    if isinstance(classinfo, ClassObject):
        return class_is_subclass(cls, classinfo)
    raise VMError("issubclass() arg 2 must be a class or tuple of classes")


def builtin_range(*args):
    if len(args) not in {1, 2, 3}:
        raise VMError("range() expects 1 to 3 arguments")
    normalized: list[int] = []
    for index, value in enumerate((unwrap_runtime_value(arg) for arg in args), start=1):
        if not isinstance(value, int) or isinstance(value, bool):
            raise VMError(f"range() argument {index} must be int")
        normalized.append(value)
    return range(*normalized)


def builtin_len(host_or_value, *args):
    if hasattr(host_or_value, "invoke_builtin_callable"):
        host = host_or_value
        values = args
    else:
        host = None
        values = (host_or_value, *args)

    if len(values) != 1:
        raise VMError("len() expects exactly 1 argument")
    value = unwrap_runtime_value(values[0])
    if isinstance(value, (list, tuple, str, dict, set)):
        return len(value)

    # VM object: attempt __len__ dispatch.
    try:
        method = py_load_attr(value, "__len__")
    except VMError:
        method = None

    if method is not None:
        if host is None:
            raise VMError("len() on VM objects requires a runtime host")
        result = host.invoke_builtin_callable(method)
        result = unwrap_runtime_value(result)
        if not isinstance(result, int) or isinstance(result, bool):
            raise VMError("__len__() should return an int")
        return result

    raise VMError(f"len() expects a list, tuple, string, dict, or set, got {type(value).__name__}")


def builtin_print(host: BuiltinHost, *args, sep=" ", end="\n", file=None, flush=False):
    rendered_args = [host.format_value(unwrap_runtime_value(arg)) for arg in args]
    rendered = str(unwrap_runtime_value(sep)).join(rendered_args) + str(unwrap_runtime_value(end))
    if file is None:
        host.output.append(rendered)
        return None
    file.write(rendered)
    if flush and hasattr(file, "flush"):
        file.flush()
    return None


def _adapt_host_callable(host: BuiltinHost, callback: object | None):
    callback = unwrap_runtime_value(callback)
    if callback is None or callable(callback):
        return callback

    def wrapper(*args, **kwargs):
        return host.invoke_builtin_callable(callback, *args, **kwargs)

    return wrapper


def builtin_sorted(host: BuiltinHost, iterable, *, key=None, reverse=False):
    iterable = unwrap_runtime_value(iterable)
    key = _adapt_host_callable(host, key)
    reverse = bool(unwrap_runtime_value(reverse))
    try:
        return sorted(iterable, key=key, reverse=reverse)
    except TypeError as exc:
        raise VMError(str(exc)) from None


def build_builtins(host: BuiltinHost) -> dict[str, object]:
    return {
        "print": lambda *args, sep=" ", end="\n", file=None, flush=False: builtin_print(
            host, *args, sep=sep, end=end, file=file, flush=flush
        ),
    "len": lambda *args: builtin_len(host, *args),
        "range": builtin_range,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "bytes": bytes,
        "bytearray": bytearray,
        "frozenset": frozenset,
        "complex": complex,
        "type": type,
        "isinstance": builtin_isinstance,
        "issubclass": builtin_issubclass,
        "hasattr": hasattr,
        "getattr": getattr,
        "setattr": setattr,
        "delattr": delattr,
        "callable": callable,
        "id": id,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "reversed": reversed,
        "sorted": lambda iterable, *, key=None, reverse=False: builtin_sorted(
            host, iterable, key=key, reverse=reverse
        ),
        "iter": iter,
        "next": next,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "divmod": divmod,
        "hash": hash,
        "hex": hex,
        "oct": oct,
        "bin": bin,
        "chr": chr,
        "ord": ord,
        "repr": repr,
        "format": format,
        "ascii": ascii,
        "input": input,
        "open": open,
        "any": any,
        "all": all,
        "object": object,
        "super": host.build_super,
        "property": property,
        "staticmethod": staticmethod,
        "classmethod": classmethod,
        "vars": vars,
        "dir": dir,
        "globals": host.current_globals,
        "locals": host.current_locals,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "StopIteration": StopIteration,
        "NameError": NameError,
        "ImportError": ImportError,
        "OSError": OSError,
        "IOError": IOError,
        "FileNotFoundError": FileNotFoundError,
        "ZeroDivisionError": ZeroDivisionError,
        "OverflowError": OverflowError,
        "MemoryError": MemoryError,
        "RecursionError": RecursionError,
        "NotImplementedError": NotImplementedError,
        "AssertionError": AssertionError,
        "SystemExit": SystemExit,
        "KeyboardInterrupt": KeyboardInterrupt,
        "GeneratorExit": GeneratorExit,
        "ArithmeticError": ArithmeticError,
        "LookupError": LookupError,
        "NotImplemented": NotImplemented,
        "Ellipsis": ...,
        "None": None,
        "True": True,
        "False": False,
        "__builtins__": py_builtins,
    }
