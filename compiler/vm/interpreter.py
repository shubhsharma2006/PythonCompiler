from __future__ import annotations

from dataclasses import dataclass, field
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
    py_binary_op,
    py_compare_op,
    py_index_get,
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
    pending_unwind: tuple[str, object] | None = None
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
            raise VMError(f"unhandled exception: {self.format_value(signal.value)}") from None
        return "".join(self.output)

    def _execute_module(self, module: BytecodeModule) -> ModuleObject:
        existing = self.modules.get(module.filename)
        if existing is not None:
            return existing

        module_object = ModuleObject(name=module.name, filename=module.filename, namespace={})
        self.bytecode_modules[module.filename] = module
        for exported_name, function_key in module.top_level_bindings.items():
            module_object.namespace[exported_name] = module.functions[function_key]
        self.modules[module.filename] = module_object
        self.loading.add(module.filename)
        try:
            self._execute_function(module.entrypoint, [], module_object)
        finally:
            self.loading.discard(module.filename)
        return module_object

    def _execute_function(
        self,
        function: BytecodeFunction,
        args: list[object],
        module: ModuleObject,
        closure_scopes: list[dict[str, object]] | None = None,
    ):
        frame = Frame(module=module, function=function, globals=module.namespace, closure_scopes=list(closure_scopes or []))
        frame.locals.update(zip(function.params, args))
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
        if op == "LOAD_GLOBAL":
            if arg in frame.globals:
                frame.stack.append(frame.globals[arg])
                return
            if arg in self.builtins:
                frame.stack.append(self.builtins[arg])
                return
            raise VMError(f"undefined global name {arg!r}")
        if op == "LOAD_DEREF":
            for scope in frame.closure_scopes:
                if arg in scope:
                    frame.stack.append(scope[arg])
                    return
            raise VMError(f"free variable {arg!r} not found in closure")
        if op == "STORE_NAME":
            value = frame.stack.pop()
            if frame.is_module:
                frame.globals[arg] = value
            else:
                frame.locals[arg] = value
            return
        if op == "STORE_GLOBAL":
            frame.globals[arg] = frame.stack.pop()
            return
        if op == "STORE_DEREF":
            value = frame.stack.pop()
            for scope in frame.closure_scopes:
                if arg in scope:
                    scope[arg] = value
                    return
            raise VMError(f"free variable {arg!r} not found in closure")
        if op == "DELETE_NAME":
            if arg in frame.locals:
                del frame.locals[arg]
                return
            if arg in frame.globals:
                del frame.globals[arg]
                return
            raise VMError(f"cannot delete undefined name {arg!r}")
        if op == "POP_TOP":
            if frame.stack:
                frame.stack.pop()
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
            pairs = []
            for _ in range(count):
                value = frame.stack.pop()
                key = frame.stack.pop()
                pairs.append((key, value))
            pairs.reverse()
            frame.stack.append(dict(pairs))
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
            try:
                values = list(sequence)
            except TypeError as exc:
                raise VMError(str(exc)) from None
            if len(values) != expected:
                raise VMError(f"unpack expected {expected} values, got {len(values)}")
            for value in reversed(values):
                frame.stack.append(value)
            return
        if op == "BUILD_CLASS":
            class_name, method_specs = arg
            methods: dict[str, BytecodeFunction] = {}
            for method_name, function_key in method_specs:
                methods[method_name] = self._lookup_function(frame.module, function_key)
            frame.stack.append(ClassObject(name=class_name, methods=methods))
            return
        if op == "TRY_FINALLY":
            frame.try_stack.append(TryHandler(kind="finally", target=int(arg), stack_depth=len(frame.stack)))
            return
        if op == "TRY_EXCEPT":
            frame.try_stack.append(TryHandler(kind="except", handlers=list(arg), stack_depth=len(frame.stack)))
            return
        if op == "END_TRY":
            if frame.try_stack:
                frame.try_stack.pop()
            return
        if op == "POP_FINALLY":
            if frame.try_stack and frame.try_stack[-1].kind == "finally":
                frame.try_stack.pop()
            return
        if op == "END_FINALLY":
            if frame.pending_unwind is None:
                return
            kind, value = frame.pending_unwind
            frame.pending_unwind = None
            if kind == "return":
                raise ReturnSignal(value)
            if kind == "raise":
                raise RaisedSignal(value)
            raise VMError(f"unknown unwind kind {kind!r}")
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
            frame.stack.append(py_index_get(collection, index))
            return
        if op == "DELETE_SUBSCR":
            index = frame.stack.pop()
            collection = frame.stack.pop()
            try:
                del collection[index]
            except (IndexError, KeyError, TypeError) as exc:
                raise VMError(str(exc)) from None
            return
        if op == "LOAD_ATTR":
            obj = frame.stack.pop()
            frame.stack.append(py_load_attr(obj, arg))
            return
        if op == "STORE_ATTR":
            value = frame.stack.pop()
            obj = frame.stack.pop()
            py_store_attr(obj, arg, value)
            return
        if op == "BINARY_OP":
            right = frame.stack.pop()
            left = frame.stack.pop()
            frame.stack.append(py_binary_op(arg, left, right))
            return
        if op == "COMPARE_OP":
            right = frame.stack.pop()
            left = frame.stack.pop()
            frame.stack.append(py_compare_op(arg, left, right))
            return
        if op == "UNARY_OP":
            operand = frame.stack.pop()
            frame.stack.append(py_unary_op(arg, operand))
            return
        if op == "TO_BOOL":
            frame.stack.append(py_truthy(frame.stack.pop()))
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
        if op == "CALL_FUNCTION":
            func_name, argc = arg
            args = [frame.stack.pop() for _ in range(argc)]
            args.reverse()
            callable_obj = frame.locals.get(func_name, frame.globals.get(func_name))
            if callable_obj is None:
                for scope in frame.closure_scopes:
                    if func_name in scope:
                        callable_obj = scope[func_name]
                        break
            if callable_obj is None:
                callable_obj = self.builtins.get(func_name)
            if callable_obj is None:
                raise VMError(f"cannot call {func_name!r}")
            frame.stack.append(self._invoke_callable(callable_obj, args, frame.module))
            return
        if op == "CALL_FUNCTION_KW":
            func_name, argc, kw_names = arg
            kw_count = len(kw_names)
            kw_values = [frame.stack.pop() for _ in range(kw_count)]
            kw_values.reverse()
            kwargs = dict(zip(kw_names, kw_values))
            args = [frame.stack.pop() for _ in range(argc)]
            args.reverse()
            callable_obj = frame.locals.get(func_name, frame.globals.get(func_name))
            if callable_obj is None:
                for scope in frame.closure_scopes:
                    if func_name in scope:
                        callable_obj = scope[func_name]
                        break
            if callable_obj is None:
                callable_obj = self.builtins.get(func_name)
            if callable_obj is None:
                raise VMError(f"cannot call {func_name!r}")
            frame.stack.append(
                py_invoke_callable(callable_obj, args, frame.module, kwargs=kwargs, execute_function=self._execute_function)
            )
            return
        if op == "CALL_METHOD":
            method_name, argc = arg
            args = [frame.stack.pop() for _ in range(argc)]
            args.reverse()
            obj = frame.stack.pop()
            callable_obj = py_load_attr(obj, method_name)
            frame.stack.append(
                py_invoke_callable(callable_obj, args, frame.module, execute_function=self._execute_function)
            )
            return
        if op == "CALL_METHOD_KW":
            method_name, argc, kw_names = arg
            kw_count = len(kw_names)
            kw_values = [frame.stack.pop() for _ in range(kw_count)]
            kw_values.reverse()
            kwargs = dict(zip(kw_names, kw_values))
            args = [frame.stack.pop() for _ in range(argc)]
            args.reverse()
            obj = frame.stack.pop()
            callable_obj = py_load_attr(obj, method_name)
            frame.stack.append(
                py_invoke_callable(callable_obj, args, frame.module, kwargs=kwargs, execute_function=self._execute_function)
            )
            return
        if op == "MAKE_FUNCTION":
            function_key, n_defaults = arg
            function = self._lookup_function(frame.module, function_key)
            defaults = [frame.stack.pop() for _ in range(n_defaults)]
            defaults.reverse()
            captured_scopes = [frame.locals, *frame.closure_scopes]
            frame.stack.append(Closure(function=function, closure_scopes=captured_scopes, defaults=defaults))
            return
        if op == "IMPORT_MODULE":
            frame.stack.append(self._import_module(arg, frame.module.filename))
            return
        if op == "IMPORT_FROM":
            module_name, export_name = arg
            module_object = self._import_module(module_name, frame.module.filename)
            if export_name not in module_object.namespace:
                raise VMError(f"module {module_name!r} has no attribute {export_name!r}")
            frame.stack.append(module_object.namespace[export_name])
            return
        if op == "PRINT":
            argc, has_sep, has_end = arg
            end = frame.stack.pop() if has_end else "\n"
            sep = frame.stack.pop() if has_sep else " "
            values = [frame.stack.pop() for _ in range(argc)]
            values.reverse()
            self.builtins["print"](*values, sep=sep, end=end)
            return
        if op == "RAISE":
            raise RaisedSignal(frame.stack.pop() if frame.stack else None)
        if op == "RETURN_VALUE":
            raise ReturnSignal(frame.stack.pop() if frame.stack else None)

        raise VMError(f"unsupported opcode {op!r}")

    def _import_module(self, module_name: str, requester_filename: str) -> ModuleObject:
        if self.module_loader is None:
            raise VMError(f"cannot import {module_name!r} without a module loader")
        module = self.module_loader(module_name, requester_filename)
        if module.filename in self.loading:
            existing = self.modules.get(module.filename)
            if existing is not None:
                return existing
        return self._execute_module(module)

    def _lookup_function(self, module: ModuleObject, function_key: str) -> BytecodeFunction:
        loaded = self.bytecode_modules.get(module.filename)
        if loaded is None or function_key not in loaded.functions:
            raise VMError(f"unknown function {function_key!r}")
        return loaded.functions[function_key]

    def _handle_exception(self, frame: Frame, signal: RaisedSignal) -> bool:
        while frame.try_stack:
            handler = frame.try_stack.pop()
            if handler.kind == "except":
                for target, type_name, bind_name in handler.handlers:
                    if not py_matches_exception(signal.value, type_name):
                        continue
                    del frame.stack[handler.stack_depth:]
                    if bind_name is not None:
                        if frame.is_module:
                            frame.globals[bind_name] = signal.value
                        else:
                            frame.locals[bind_name] = signal.value
                    frame.ip = target
                    return True
                continue
            if handler.kind == "finally":
                del frame.stack[handler.stack_depth:]
                frame.pending_unwind = ("raise", signal.value)
                frame.ip = int(handler.target)
                return True
        return False

    def _handle_return(self, frame: Frame, signal: ReturnSignal) -> bool:
        while frame.try_stack:
            handler = frame.try_stack.pop()
            if handler.kind != "finally":
                continue
            del frame.stack[handler.stack_depth:]
            frame.pending_unwind = ("return", signal.value)
            frame.ip = int(handler.target)
            return True
        return False

    def _invoke_callable(self, callable_obj, args: list[object], module: ModuleObject):
        return py_invoke_callable(callable_obj, args, module, execute_function=self._execute_function)

    def format_value(self, value) -> str:
        return repr(value) if isinstance(value, float) else str(value)

    def current_globals(self):
        return dict(self._current_frame.globals) if self._current_frame is not None else {}

    def current_locals(self):
        if self._current_frame is None:
            return {}
        return dict(self._current_frame.locals)
