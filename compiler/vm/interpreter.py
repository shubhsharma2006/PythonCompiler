from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from typing import Callable

from compiler.vm.bytecode import BytecodeFunction, BytecodeModule
from compiler.vm.builtins import build_builtins
from compiler.vm.errors import RaisedSignal, ReturnSignal, VMError
from compiler.vm.objects import (
    ClassObject,
    Closure,
    InstanceObject,
    ModuleObject,
    BoundMethod,
    SuperObject,
    py_binary_op,
    class_is_subclass,
    py_compare_op,
    py_delete_attr,
    py_index_get,
    py_index_delete,
    py_index_set,
    py_invoke_callable,
    py_load_attr,
    py_matches_exception,
    py_store_attr,
    py_truthy,
    py_unary_op,
)


@dataclass
class TryHandler:
    kind: str
    stack_depth: int
    handlers: list[tuple[int, str | None, str | None]] = field(default_factory=list)
    target: int | None = None


@dataclass
class Frame:
    module: ModuleObject
    function: BytecodeFunction
    globals: dict[str, object]
    locals: dict[str, object] = field(default_factory=dict)
    closure_scopes: list[dict[str, object]] = field(default_factory=list)
    stack: list[object] = field(default_factory=list)
    try_stack: list[TryHandler] = field(default_factory=list)
    with_stack: list[object] = field(default_factory=list)
    pending_unwind: tuple[str, object] | None = None
    active_exceptions: list[RaisedSignal] = field(default_factory=list)
    ip: int = 0

    @property
    def is_module(self) -> bool:
        return self.function.name == "<module>"


class BytecodeInterpreter:
    def __init__(self, module_loader: Callable[[str, str], BytecodeModule] | None = None) -> None:
        self.output: list[str] = []
        self.module_loader = module_loader
        self.modules: dict[str, ModuleObject] = {}
        self.bytecode_modules: dict[str, BytecodeModule] = {}
        self.loading: set[str] = set()
        self._current_frame: Frame | None = None
        self.builtins: dict[str, object] = build_builtins(self)

    def run(self, module: BytecodeModule) -> str:
        try:
            self._execute_module(module)
        except RaisedSignal as signal:
            message = f"unhandled exception: {self.format_value(signal.value)}"
            if signal.cause is not None:
                message += f" (caused by {self.format_value(signal.cause)})"
            raise VMError(message) from None
        return "".join(self.output)

    def _execute_module(self, module: BytecodeModule) -> ModuleObject:
        existing = self.modules.get(module.filename)
        if existing is not None:
            return existing

        module_object = ModuleObject(
            name=module.name,
            filename=module.filename,
            namespace={},
        )

        self.bytecode_modules[module.filename] = module

        for exported_name, function_key in module.top_level_bindings.items():
            module_object.namespace[exported_name] = module.functions[function_key]

        self.modules[module.filename] = module_object
        self.loading.add(module.filename)

        try:
            self._execute_function(module.entrypoint, {}, module_object)
        finally:
            self.loading.discard(module.filename)

        return module_object

    def _execute_function(
        self,
        function: BytecodeFunction,
        bound_args: dict[str, object],
        module: ModuleObject,
        closure_scopes: list[dict[str, object]] | None = None,
    ):
        frame = Frame(
            module=module,
            function=function,
            globals=module.namespace,
            closure_scopes=list(closure_scopes or []),
        )

        frame.locals.update(bound_args)

        try:
            while frame.ip < len(function.instructions):
                self._current_frame = frame

                instruction = function.instructions[frame.ip]
                frame.ip += 1

                try:
                    self._execute_instruction(frame, instruction)

                except ReturnSignal as signal:
                    if not self._handle_return(frame, signal):
                        raise

                except RaisedSignal as signal:
                    if not self._handle_exception(frame, signal):
                        raise

        except ReturnSignal as signal:
            return signal.value

        return None

    def _execute_instruction(self, frame: Frame, instruction) -> None:
        op = instruction.opcode
        arg = instruction.arg

        if op == "LOAD_CONST":
            frame.stack.append(arg)
            return

        if op == "LOAD_NAME":
            if arg in frame.locals:
                frame.stack.append(frame.locals[arg])
                return

            for scope in frame.closure_scopes:
                if arg in scope:
                    frame.stack.append(scope[arg])
                    return

            if arg in frame.globals:
                frame.stack.append(frame.globals[arg])
                return

            if arg in self.builtins:
                frame.stack.append(self.builtins[arg])
                return

            raise VMError(f"undefined name {arg!r}")

        if op == "LOAD_DEREF":
            for scope in frame.closure_scopes:
                if arg in scope:
                    frame.stack.append(scope[arg])
                    return
            raise VMError(f"undefined nonlocal name {arg!r}")

        if op == "LOAD_GLOBAL":
            if arg in frame.globals:
                frame.stack.append(frame.globals[arg])
                return

            if arg in self.builtins:
                frame.stack.append(self.builtins[arg])
                return

            raise VMError(f"undefined global name {arg!r}")

        if op == "STORE_NAME":
            value = frame.stack.pop()

            if frame.is_module:
                frame.globals[arg] = value
            else:
                frame.locals[arg] = value

            return

        if op == "STORE_GLOBAL":
            value = frame.stack.pop()
            frame.globals[arg] = value
            return

        if op == "STORE_DEREF":
            value = frame.stack.pop()
            for scope in frame.closure_scopes:
                if arg in scope:
                    scope[arg] = value
                    return
            raise VMError(f"undefined nonlocal name {arg!r}")

        if op == "POP_TOP":
            if frame.stack:
                frame.stack.pop()
            return

        if op == "DELETE_NAME":
            if arg in frame.locals:
                del frame.locals[arg]
                return
            if arg in frame.globals:
                del frame.globals[arg]
                return
            raise VMError(f"cannot delete name {arg!r}")

        if op == "BINARY_OP":
            right = frame.stack.pop()
            left = frame.stack.pop()

            frame.stack.append(
                py_binary_op(arg, left, right)
            )
            return

        if op == "COMPARE_OP":
            right = frame.stack.pop()
            left = frame.stack.pop()

            frame.stack.append(
                py_compare_op(arg, left, right)
            )
            return

        if op == "UNARY_OP":
            operand = frame.stack.pop()

            frame.stack.append(
                py_unary_op(arg, operand)
            )
            return

        if op == "TO_BOOL":
            frame.stack.append(
                py_truthy(frame.stack.pop())
            )
            return

        if op == "JUMP":
            frame.ip = int(arg)
            return

        if op == "JUMP_IF_FALSE":
            condition = frame.stack.pop()

            if not bool(condition):
                frame.ip = int(arg)

            return

        if op == "JUMP_IF_TRUE":
            condition = frame.stack.pop()

            if bool(condition):
                frame.ip = int(arg)

            return

        if op == "BUILD_LIST":
            count = int(arg)

            values = [frame.stack.pop() for _ in range(count)]
            values.reverse()

            frame.stack.append(values)
            return

        if op == "BUILD_TUPLE":
            count = int(arg)

            values = [frame.stack.pop() for _ in range(count)]
            values.reverse()

            frame.stack.append(tuple(values))
            return

        if op == "BUILD_MAP":
            count = int(arg)

            result = {}

            for _ in range(count):
                value = frame.stack.pop()
                key = frame.stack.pop()
                result[key] = value

            frame.stack.append(result)
            return

        if op == "BUILD_SET":
            count = int(arg)

            values = [frame.stack.pop() for _ in range(count)]
            values.reverse()

            frame.stack.append(set(values))
            return

        if op == "BUILD_SLICE":
            if int(arg) == 3:
                step = frame.stack.pop()
                stop = frame.stack.pop()
                start = frame.stack.pop()

                frame.stack.append(slice(start, stop, step))
                return

            stop = frame.stack.pop()
            start = frame.stack.pop()

            frame.stack.append(slice(start, stop))
            return

        if op == "UNPACK_SEQUENCE":
            expected = int(arg)
            sequence = frame.stack.pop()

            values = list(sequence)

            if len(values) != expected:
                raise VMError(
                    f"unpack expected {expected} values, got {len(values)}"
                )

            for value in reversed(values):
                frame.stack.append(value)

            return

        if op == "UNPACK_EX":
            prefix_count, suffix_count = arg
            sequence = frame.stack.pop()

            values = list(sequence)
            if len(values) < prefix_count + suffix_count:
                raise VMError(
                    f"unpack expected at least {prefix_count + suffix_count} values, got {len(values)}"
                )

            prefix_vals = values[:prefix_count]
            suffix_vals = values[len(values) - suffix_count :] if suffix_count else []
            rest_vals = values[prefix_count : len(values) - suffix_count]

            # Push prefix, then rest-list, then suffix.
            for value in reversed(suffix_vals):
                frame.stack.append(value)
            frame.stack.append(list(rest_vals))
            for value in reversed(prefix_vals):
                frame.stack.append(value)
            return

        if op == "GET_ITER":
            frame.stack.append(iter(frame.stack.pop()))
            return

        if op == "FOR_ITER":
            iterator = frame.stack[-1]

            try:
                frame.stack.append(next(iterator))

            except StopIteration:
                frame.stack.pop()
                frame.ip = int(arg)

            return

        if op == "BINARY_SUBSCR":
            index = frame.stack.pop()
            collection = frame.stack.pop()

            frame.stack.append(
                py_index_get(collection, index)
            )
            return

        if op == "DELETE_SUBSCR":
            index = frame.stack.pop()
            collection = frame.stack.pop()
            py_index_delete(collection, index)
            return

        if op == "STORE_SUBSCR":
            value = frame.stack.pop()
            index = frame.stack.pop()
            collection = frame.stack.pop()

            py_index_set(collection, index, value)
            return

        if op == "LOAD_ATTR":
            obj = frame.stack.pop()

            try:
                value = py_load_attr(obj, arg)
            except VMError:
                if isinstance(obj, ModuleObject):
                    try:
                        value = self._import_module(
                            f"{obj.name}.{arg}",
                            obj.filename,
                            bind_root=False,
                            requester_module_name=obj.name,
                        )
                        obj.namespace[arg] = value
                    except VMError:
                        raise
                else:
                    raise

            frame.stack.append(value)
            return

        if op == "STORE_ATTR":
            value = frame.stack.pop()
            obj = frame.stack.pop()

            py_store_attr(obj, arg, value)
            return

        if op == "DELETE_ATTR":
            obj = frame.stack.pop()

            py_delete_attr(obj, arg)
            return

        if op == "CALL_FUNCTION":
            if len(arg) == 2:
                func_name, argc = arg
                has_kwargs = False
            else:
                func_name, argc, has_kwargs = arg

            kwargs = {}
            if has_kwargs:
                kwargs = frame.stack.pop()

            if argc == -1:
                args = frame.stack.pop()
            else:
                args = [frame.stack.pop() for _ in range(argc)]
                args.reverse()

            callable_obj = None

            if func_name in frame.locals:
                callable_obj = frame.locals[func_name]

            if callable_obj is None:
                for scope in frame.closure_scopes:
                    if func_name in scope:
                        callable_obj = scope[func_name]
                        break

            if callable_obj is None and func_name in frame.globals:
                callable_obj = frame.globals[func_name]

            if callable_obj is None:
                callable_obj = self.builtins.get(func_name)

            if callable_obj is None:
                raise VMError(f"cannot call {func_name!r}")

            frame.stack.append(
                py_invoke_callable(
                    callable_obj,
                    args,
                    frame.module,
                    kwargs=kwargs,
                    execute_function=self._execute_function,
                )
            )

            return

        if op == "CALL_VALUE":
            if isinstance(arg, tuple):
                argc, has_kwargs = arg
            else:
                argc, has_kwargs = int(arg), False

            kwargs = {}
            if has_kwargs:
                kwargs = frame.stack.pop()

            if argc == -1:
                args = frame.stack.pop()
            else:
                args = [frame.stack.pop() for _ in range(argc)]
                args.reverse()

            callable_obj = frame.stack.pop()

            frame.stack.append(
                py_invoke_callable(
                    callable_obj,
                    args,
                    frame.module,
                    kwargs=kwargs,
                    execute_function=self._execute_function,
                )
            )

            return

        if op == "EXPAND_ARGS":
            # arg: list[bool] flags for each original positional argument. True means the
            # value is an iterable to splat (from StarredExpr), False means a single arg.
            flags = arg
            parts = [frame.stack.pop() for _ in range(len(flags))]
            parts.reverse()

            expanded = []
            for value, is_starred in zip(parts, flags):
                if is_starred:
                    expanded.extend(list(value))
                else:
                    expanded.append(value)

            frame.stack.append(expanded)
            return

        if op == "BUILD_KWARGS":
            # arg: (kwarg_names: list[str], n_starred: int)
            kwarg_names, n_starred = arg

            # Values are pushed in this order:
            #   [explicit kw values...], [**mapping values...]
            starred_parts = [frame.stack.pop() for _ in range(n_starred)]
            starred_parts.reverse()

            explicit_values = [frame.stack.pop() for _ in range(len(kwarg_names))]
            explicit_values.reverse()

            kwargs = dict(zip(kwarg_names, explicit_values))
            for part in starred_parts:
                if part is None:
                    continue
                kwargs.update(dict(part))

            frame.stack.append(kwargs)
            return

        if op == "DUP_TOP":
            frame.stack.append(frame.stack[-1])
            return

        if op == "MAKE_FUNCTION":
            function_key, n_defaults, kwonly_default_names = arg

            function = self._lookup_function(
                frame.module,
                function_key,
            )

            kwonly_values = [
                frame.stack.pop()
                for _ in range(len(kwonly_default_names))
            ]

            kwonly_values.reverse()

            kwonly_defaults = dict(
                zip(kwonly_default_names, kwonly_values)
            )

            defaults = [
                frame.stack.pop()
                for _ in range(n_defaults)
            ]

            defaults.reverse()

            captured_scopes = [
                frame.locals,
                *frame.closure_scopes,
            ]

            frame.stack.append(
                Closure(
                    function=function,
                    closure_scopes=captured_scopes,
                    defaults=defaults,
                    kwonly_defaults=kwonly_defaults,
                )
            )

            return

        if op == "IMPORT_MODULE":
            if isinstance(arg, tuple):
                if len(arg) == 2:
                    module_name, bind_root = arg
                    level = 0
                else:
                    module_name, bind_root, level = arg
            else:
                module_name, bind_root = arg, False
                level = 0

            frame.stack.append(
                self._import_module(
                    module_name,
                    frame.module.filename,
                    bind_root=bool(bind_root),
                    level=level,
                    requester_module_name=frame.module.name,
                )
            )

            return

        if op == "IMPORT_STAR":
            module_obj = frame.stack.pop()
            if not isinstance(module_obj, ModuleObject):
                raise VMError("import * expects a module")

            names = module_obj.namespace.get("__all__")
            if isinstance(names, (list, tuple, set)):
                export_names = [name for name in names if isinstance(name, str)]
            else:
                export_names = [
                    name for name in module_obj.namespace
                    if not name.startswith("_")
                ]

            for name in export_names:
                if frame.is_module:
                    frame.globals[name] = module_obj.namespace[name]
                else:
                    frame.locals[name] = module_obj.namespace[name]

            return

        if op == "PRINT":
            argc, has_sep, has_end = arg

            end = frame.stack.pop() if has_end else "\n"
            sep = frame.stack.pop() if has_sep else " "

            values = [frame.stack.pop() for _ in range(argc)]
            values.reverse()

            self.builtins["print"](
                *values,
                sep=sep,
                end=end,
            )

            return

        if op == "TRY_EXCEPT":
            frame.try_stack.append(
                TryHandler(
                    kind="except",
                    stack_depth=len(frame.stack),
                    handlers=list(arg),
                )
            )
            return

        if op == "TRY_FINALLY":
            frame.try_stack.append(
                TryHandler(
                    kind="finally",
                    stack_depth=len(frame.stack),
                    target=int(arg),
                )
            )
            return

        if op == "POP_TRY":
            if frame.try_stack:
                frame.try_stack.pop()
            return

        if op == "LOAD_EXCEPTION":
            if not frame.active_exceptions:
                raise VMError("no active exception")
            value = frame.active_exceptions[-1].value
            if arg is not None:
                if frame.is_module:
                    frame.globals[arg] = value
                else:
                    frame.locals[arg] = value
            else:
                frame.stack.append(value)
            return

        if op == "POP_EXCEPT":
            if frame.active_exceptions:
                frame.active_exceptions.pop()
            return

        if op == "END_FINALLY":
            if frame.pending_unwind is None:
                return
            action, payload = frame.pending_unwind
            frame.pending_unwind = None
            if action == "return":
                raise ReturnSignal(payload)
            if action == "raise":
                raise payload
            if action == "jump":
                frame.ip = int(payload)
                return
            return

        if op == "WITH_ENTER":
            context = frame.stack.pop()
            enter = py_load_attr(context, "__enter__")
            exit_method = py_load_attr(context, "__exit__")

            value = py_invoke_callable(
                enter,
                [],
                frame.module,
                execute_function=self._execute_function,
            )
            frame.with_stack.append(exit_method)

            if arg is not None:
                if frame.is_module:
                    frame.globals[arg] = value
                else:
                    frame.locals[arg] = value
            return

        if op == "WITH_EXIT":
            if not frame.with_stack:
                raise VMError("with exit without enter")
            exit_method = frame.with_stack.pop()
            if frame.pending_unwind is not None and frame.pending_unwind[0] == "raise":
                signal = frame.pending_unwind[1]
                exc_value = signal.value if isinstance(signal, RaisedSignal) else signal
                exc_type = type(exc_value)
                handled = py_invoke_callable(
                    exit_method,
                    [exc_type, exc_value, None],
                    frame.module,
                    execute_function=self._execute_function,
                )
                if handled:
                    frame.pending_unwind = None
                    if frame.active_exceptions:
                        frame.active_exceptions.pop()
                return
            py_invoke_callable(
                exit_method,
                [None, None, None],
                frame.module,
                execute_function=self._execute_function,
            )
            return

        if op == "RAISE":
            if frame.stack:
                raise RaisedSignal(frame.stack.pop())
            if frame.active_exceptions:
                raise frame.active_exceptions[-1]
            raise RaisedSignal(None)

        if op == "RAISE_CAUSE":
            cause = frame.stack.pop()
            value = frame.stack.pop()
            raise RaisedSignal(value, cause=cause)

        if op == "RETURN_VALUE":
            raise ReturnSignal(
                frame.stack.pop() if frame.stack else None
            )

        if op == "BUILD_CLASS":
            class_name, method_specs, base_count, attribute_names = arg

            attributes: dict[str, object] = {}
            for name in reversed(attribute_names):
                attributes[name] = frame.stack.pop()

            bases = [frame.stack.pop() for _ in range(base_count)]
            bases.reverse()

            methods: dict[str, BytecodeFunction] = {}
            for method_name, function_key in method_specs:
                methods[method_name] = self._lookup_function(
                    frame.module,
                    function_key,
                )

            frame.stack.append(
                ClassObject(
                    name=class_name,
                    methods=methods,
                    bases=bases,
                    attributes=attributes,
                )
            )
            return

        raise VMError(f"unsupported opcode {op!r}")

    def _import_module(
        self,
        module_name: str | None,
        requester_filename: str,
        *,
        bind_root: bool = False,
        level: int = 0,
        requester_module_name: str | None = None,
    ) -> ModuleObject:

        module_name = self._resolve_import_name(
            module_name,
            level,
            requester_filename,
            requester_module_name,
        )

        if self.module_loader is not None:
            try:
                module = self.module_loader(
                    module_name,
                    requester_filename,
                )

            except VMError as exc:
                if "cannot resolve local module" not in str(exc):
                    raise

            else:
                if module.filename in self.loading:
                    existing = self.modules.get(module.filename)

                    if existing is not None:
                        return existing

                module_object = self._execute_module(module)

                if "." in module_name:
                    parent_name, child_name = module_name.rsplit(".", 1)

                    parent_module = self._import_module(
                        parent_name,
                        requester_filename,
                    )

                    parent_module.namespace[child_name] = module_object

                    if bind_root:
                        return self._import_module(
                            module_name.split(".", 1)[0],
                            requester_filename,
                        )

                return module_object

        target_name = (
            module_name.split(".", 1)[0]
            if bind_root
            else module_name
        )

        try:
            importlib.import_module(module_name)
            py_module = importlib.import_module(target_name)

        except ImportError as exc:
            raise VMError(
                f"cannot import {module_name!r}: {exc}"
            ) from None

        filename = getattr(py_module, "__file__", None) or f"<builtin:{target_name}>"

        existing = self.modules.get(filename)

        if existing is not None:
            return existing

        module_object = ModuleObject(
            name=target_name,
            filename=filename,
            namespace=dict(vars(py_module)),
        )

        self.modules[filename] = module_object

        return module_object

    def _lookup_function(
        self,
        module: ModuleObject,
        function_key: str,
    ) -> BytecodeFunction:

        loaded = self.bytecode_modules.get(module.filename)

        if loaded is None or function_key not in loaded.functions:
            raise VMError(f"unknown function {function_key!r}")

        return loaded.functions[function_key]

    def _handle_exception(
        self,
        frame: Frame,
        signal: RaisedSignal,
    ) -> bool:

        while frame.try_stack:
            handler = frame.try_stack.pop()

            if handler.kind == "finally":
                frame.pending_unwind = ("raise", signal)
                frame.active_exceptions.append(signal)
                frame.ip = int(handler.target)
                return True

            if handler.kind == "except":
                expected_handlers = handler.handlers
                frame.stack = frame.stack[: handler.stack_depth]
                for target, type_name, bind_name in expected_handlers:
                    expected = None
                    if type_name is not None:
                        expected = (
                            frame.globals.get(type_name)
                            or self.builtins.get(type_name)
                            or type_name
                        )
                    if py_matches_exception(signal.value, expected):
                        frame.active_exceptions.append(signal)
                        if bind_name is not None:
                            if frame.is_module:
                                frame.globals[bind_name] = signal.value
                            else:
                                frame.locals[bind_name] = signal.value
                        frame.ip = int(target)
                        return True

        return False

    def _handle_return(
        self,
        frame: Frame,
        signal: ReturnSignal,
    ) -> bool:

        while frame.try_stack:
            handler = frame.try_stack.pop()

            if handler.kind != "finally":
                continue

            frame.pending_unwind = ("return", signal.value)
            frame.ip = int(handler.target)

            return True

        return False

    def _invoke_callable(
        self,
        callable_obj,
        args,
        module,
    ):
        from compiler.vm.objects import Closure, BoundMethod
        from compiler.vm.errors import VMError

        # bound methods
        if isinstance(callable_obj, BoundMethod):
            return self._invoke_callable(
                callable_obj.function,
                [callable_obj.instance, *args],
                module,
            )

        # user-defined closures/functions
        if isinstance(callable_obj, Closure):
            bound = {}

            params = callable_obj.function.params

            for i, param in enumerate(params):
                if i < len(args):
                    bound[param] = args[i]

            return self._execute_function(
                callable_obj.function,
                bound,
                module,
                callable_obj.closure_scopes,
            )

        # native python callable
        if callable(callable_obj):
            return callable_obj(*args)

        raise VMError(f"cannot call {callable_obj!r}")
    

    def format_value(self, value) -> str:
        return repr(value) if isinstance(value, float) else str(value)

    def current_globals(self):
        return (
            dict(self._current_frame.globals)
            if self._current_frame is not None
            else {}
        )

    def current_locals(self):
        if self._current_frame is None:
            return {}

        return dict(self._current_frame.locals)

    def invoke_builtin_callable(self, callable_obj: object, *args, **kwargs) -> object:
        if self._current_frame is None:
            raise VMError("no active frame for builtin callback")
        return py_invoke_callable(
            callable_obj,
            list(args),
            self._current_frame.module,
            kwargs=dict(kwargs),
            execute_function=self._execute_function,
        )

    def _resolve_import_name(
        self,
        module_name: str | None,
        level: int,
        requester_filename: str,
        requester_module_name: str | None,
    ) -> str:

        if level == 0:
            return module_name or ""

        if not requester_module_name or requester_module_name == "__main__":
            raise VMError(
                "relative imports require a package context"
            )

        package_parts = requester_module_name.split(".")

        if requester_filename.endswith("__init__.py"):
            current_package = package_parts
        else:
            current_package = package_parts[:-1]

        climb = level - 1

        if climb > len(current_package):
            raise VMError(
                "relative import goes beyond top-level package"
            )

        base_parts = current_package[: len(current_package) - climb]

        if module_name:
            return ".".join([*base_parts, module_name])

        if not base_parts:
            raise VMError(
                "relative import resolved to an empty module name"
            )

        return ".".join(base_parts)

    def build_super(self, *args):
        frame = self._current_frame

        if frame is None:
            raise VMError(
                "super() called without an active frame"
            )

        if len(args) == 0:
            owner_class_name = frame.function.owner_class_name

            if owner_class_name is None or not frame.function.params:
                raise VMError(
                    "super() is only supported inside instance methods"
                )

            owner_class = frame.globals.get(owner_class_name)

            if not isinstance(owner_class, ClassObject):
                raise VMError(
                    f"super() could not resolve class {owner_class_name!r}"
                )

            instance = frame.locals.get(frame.function.params[0])

            if not isinstance(instance, InstanceObject):
                raise VMError(
                    "super() requires an instance as the first method argument"
                )

            if not class_is_subclass(
                instance.class_object,
                owner_class,
            ):
                raise VMError(
                    "super() instance is not compatible with the current class"
                )

            return SuperObject(
                owner_class=owner_class,
                instance=instance,
            )

        if len(args) != 2:
            raise VMError("super() expects 0 or 2 arguments")

        owner_class, instance = args

        if not isinstance(owner_class, ClassObject):
            raise VMError("super() arg 1 must be a class")

        if not isinstance(instance, InstanceObject):
            raise VMError("super() arg 2 must be an instance")

        if not class_is_subclass(
            instance.class_object,
            owner_class,
        ):
            raise VMError(
                "super() instance is not compatible with the provided class"
            )

        return SuperObject(
            owner_class=owner_class,
            instance=instance,
        )
