from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    BreakStmt,
    CallExpr,
    ClassDef,
    Comprehension,
    CompareExpr,
    ConstantExpr,
    ContinueStmt,
    DeleteStmt,
    DictExpr,
    DictCompExpr,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    IfStmt,
    IfExpr,
    ImportStmt,
    IndexExpr,
    LambdaExpr,
    ListExpr,
    ListCompExpr,
    MethodCallExpr,
    NameExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    SetCompExpr,
    SliceExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WhileStmt,
    WithStmt,
    BreakStmt,
    ContinueStmt,
)
from compiler.vm.bytecode import BytecodeFunction, BytecodeModule, Instruction


class BytecodeLowerer:
    def __init__(self) -> None:
        self.label_counter = 0
        self.function_counter = 0
        self.temp_counter = 0
        self.functions: dict[str, BytecodeFunction] = {}
        self.loop_stack: list[tuple[str, str]] = []
        self.scope_stack: list[tuple[set[str], set[str]]] = []

    def lower(self, program: Program, *, module_name: str = "__main__", filename: str = "<stdin>") -> BytecodeModule:
        self.functions = {}
        top_level_bindings: dict[str, str] = {}
        for statement in program.body:
            if isinstance(statement, FunctionDef):
                lowered = self._lower_function(statement, parent_key=module_name)
                top_level_bindings[statement.name] = lowered.key

        entry = self._lower_body("<module>", [], program.body)
        entry.key = f"{module_name}:<module>"
        return BytecodeModule(
            name=module_name,
            filename=filename,
            functions=dict(self.functions),
            top_level_bindings=top_level_bindings,
            entrypoint=entry,
        )

    def _lower_function(self, function: FunctionDef, *, parent_key: str, owner_class_name: str | None = None) -> BytecodeFunction:
        function_key = self._new_function_key(parent_key, function.name)
        lowered = self._lower_body(function.name, function.params, function.body, parent_key=function_key)
        lowered.key = function_key
        lowered.owner_class_name = owner_class_name
        lowered.defaults = [self._literal_default(default) for default in function.defaults]
        lowered.kwonly_params = list(function.kwonly_params)
        lowered.kwonly_defaults = {
            name: self._literal_default(default)
            for name, default in function.kwonly_defaults.items()
        }
        lowered.vararg_name = function.vararg
        lowered.kwarg_name = function.kwarg
        self.functions[function_key] = lowered
        return lowered

    def _lower_body(self, name: str, params: list[str], body: list[object], parent_key: str | None = None) -> BytecodeFunction:
        instructions: list[Instruction] = []
        global_names, nonlocal_names = self._collect_scope_declarations(body)
        self.scope_stack.append((global_names, nonlocal_names))
        try:
            for statement in body:
                self._emit_statement(statement, instructions, parent_key or name)
        finally:
            self.scope_stack.pop()
        instructions.append(Instruction("LOAD_CONST", None))
        instructions.append(Instruction("RETURN_VALUE"))
        return BytecodeFunction(
            key="",
            name=name,
            params=list(params),
            instructions=self._resolve_labels(instructions),
            global_names=global_names,
            nonlocal_names=nonlocal_names,
        )

    def _emit_statement(self, statement, instructions: list[Instruction], parent_key: str) -> None:
        if isinstance(statement, FunctionDef):
            lowered = self._lower_function(statement, parent_key=parent_key)
            for default in statement.defaults:
                self._emit_expr(default, instructions)
            kwonly_default_names = [name for name in statement.kwonly_params if name in statement.kwonly_defaults]
            for name in kwonly_default_names:
                self._emit_expr(statement.kwonly_defaults[name], instructions)
            instructions.append(Instruction("MAKE_FUNCTION", (lowered.key, len(statement.defaults), kwonly_default_names)))
            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, ClassDef):
            method_specs = []
            class_parent = self._new_function_key(parent_key, statement.name)
            for method in statement.methods:
                lowered = self._lower_function(method, parent_key=class_parent, owner_class_name=statement.name)
                method_specs.append((method.name, lowered.key))
            for base in statement.bases:
                self._emit_expr(base, instructions, parent_key)
            attribute_names = []
            for attribute in statement.attributes:
                self._emit_expr(attribute.value, instructions, parent_key)
                attribute_names.append(attribute.name)
            instructions.append(Instruction("BUILD_CLASS", (statement.name, method_specs, len(statement.bases), attribute_names)))
            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, AssignStmt):
            self._emit_expr(statement.value, instructions)
            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, UnpackAssignStmt):
            self._emit_expr(statement.value, instructions, parent_key)
            instructions.append(Instruction("UNPACK_SEQUENCE", len(statement.targets)))
            for target in statement.targets:
                self._emit_store_name(target, instructions)
            return

        if isinstance(statement, AttributeAssignStmt):
            self._emit_expr(statement.object, instructions)
            self._emit_expr(statement.value, instructions)
            instructions.append(Instruction("STORE_ATTR", statement.attr_name))
            return

        if isinstance(statement, PassStmt):
            return

        if isinstance(statement, (GlobalStmt, NonlocalStmt)):
            return

        if isinstance(statement, DeleteStmt):
            for target in statement.targets:
                if isinstance(target, NameExpr):
                    instructions.append(Instruction("DELETE_NAME", target.name))
                elif isinstance(target, IndexExpr):
                    self._emit_expr(target.collection, instructions, parent_key)
                    self._emit_expr(target.index, instructions, parent_key)
                    instructions.append(Instruction("DELETE_SUBSCR"))
            return

        if isinstance(statement, PrintStmt):
            for value in statement.values:
                self._emit_expr(value, instructions)
            if statement.sep is not None:
                self._emit_expr(statement.sep, instructions)
            if statement.end is not None:
                self._emit_expr(statement.end, instructions)
            instructions.append(Instruction("PRINT", (len(statement.values), statement.sep is not None, statement.end is not None)))
            return

        if isinstance(statement, RaiseStmt):
            self._emit_expr(statement.value, instructions, parent_key)
            instructions.append(Instruction("RAISE"))
            return

        if isinstance(statement, TryStmt):
            finally_label = self._new_label("finally") if statement.finalbody else None
            if finally_label is not None:
                instructions.append(Instruction("TRY_FINALLY", finally_label))

            if statement.handlers:
                handler_labels = [self._new_label("except") for _ in statement.handlers]
                end_label = self._new_label("try_end")
                handler_specs = [
                    (label, handler.type_name, handler.name)
                    for label, handler in zip(handler_labels, statement.handlers)
                ]
                instructions.append(Instruction("TRY_EXCEPT", handler_specs))
                for child in statement.body:
                    self._emit_statement(child, instructions, parent_key)
                instructions.append(Instruction("END_TRY"))
                instructions.append(Instruction("JUMP", end_label))
                for label, handler in zip(handler_labels, statement.handlers):
                    instructions.append(Instruction("LABEL", label))
                    for child in handler.body:
                        self._emit_statement(child, instructions, parent_key)
                    instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", end_label))
            else:
                for child in statement.body:
                    self._emit_statement(child, instructions, parent_key)

            if finally_label is not None:
                instructions.append(Instruction("POP_FINALLY"))
                instructions.append(Instruction("JUMP", finally_label))
                instructions.append(Instruction("LABEL", finally_label))
                for child in statement.finalbody:
                    self._emit_statement(child, instructions, parent_key)
                instructions.append(Instruction("END_FINALLY"))
            return

        if isinstance(statement, WithStmt):
            finally_label = self._new_label("with_exit")
            self._emit_expr(statement.context_expr, instructions, parent_key)
            instructions.append(Instruction("WITH_ENTER"))
            if statement.optional_var is not None:
                self._emit_store_name(statement.optional_var, instructions)
            else:
                instructions.append(Instruction("POP_TOP"))
            instructions.append(Instruction("TRY_FINALLY", finally_label))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("POP_FINALLY"))
            instructions.append(Instruction("JUMP", finally_label))
            instructions.append(Instruction("LABEL", finally_label))
            instructions.append(Instruction("WITH_EXIT"))
            instructions.append(Instruction("END_FINALLY"))
            return

        if isinstance(statement, ImportStmt):
            instructions.append(Instruction("IMPORT_MODULE", (statement.module, statement.alias is None)))
            self._emit_store_name(self._import_binding_name(statement), instructions)
            return

        if isinstance(statement, FromImportStmt):
            instructions.append(Instruction("IMPORT_FROM", (statement.module, statement.name)))
            self._emit_store_name(statement.alias or statement.name, instructions)
            return

        if isinstance(statement, ExprStmt):
            self._emit_expr(statement.expr, instructions, parent_key)
            instructions.append(Instruction("POP_TOP"))
            return

        if isinstance(statement, IfStmt):
            else_label = self._new_label("if_else")
            end_label = self._new_label("if_end")
            self._emit_expr(statement.condition, instructions, parent_key)
            instructions.append(Instruction("JUMP_IF_FALSE", else_label))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("JUMP", end_label))
            instructions.append(Instruction("LABEL", else_label))
            for child in statement.orelse:
                self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, WhileStmt):
            start_label = self._new_label("while_start")
            if statement.orelse:
                orelse_label = self._new_label("while_else")
                end_label = self._new_label("while_end")
                false_target = orelse_label
                break_target = end_label
            else:
                end_label = self._new_label("while_end")
                false_target = end_label
                break_target = end_label
            instructions.append(Instruction("LABEL", start_label))
            self._emit_expr(statement.condition, instructions, parent_key)
            instructions.append(Instruction("JUMP_IF_FALSE", false_target))
            self.loop_stack.append((start_label, break_target))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            self.loop_stack.pop()
            instructions.append(Instruction("JUMP", start_label))
            if statement.orelse:
                instructions.append(Instruction("LABEL", orelse_label))
                for child in statement.orelse:
                    self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, ForStmt):
            start_label = self._new_label("for_start")
            if statement.orelse:
                orelse_label = self._new_label("for_else")
                end_label = self._new_label("for_end")
                false_target = orelse_label
                break_target = end_label
            else:
                end_label = self._new_label("for_end")
                false_target = end_label
                break_target = end_label
            self._emit_expr(statement.iterator, instructions, parent_key)
            instructions.append(Instruction("GET_ITER"))
            instructions.append(Instruction("LABEL", start_label))
            instructions.append(Instruction("FOR_ITER", false_target))
            self._emit_store_name(statement.target, instructions)
            self.loop_stack.append((start_label, break_target))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            self.loop_stack.pop()
            instructions.append(Instruction("JUMP", start_label))
            if statement.orelse:
                instructions.append(Instruction("LABEL", orelse_label))
                for child in statement.orelse:
                    self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, BreakStmt):
            if self.loop_stack:
                instructions.append(Instruction("JUMP", self.loop_stack[-1][1]))
            return

        if isinstance(statement, ContinueStmt):
            if self.loop_stack:
                instructions.append(Instruction("JUMP", self.loop_stack[-1][0]))
            return

        if isinstance(statement, ReturnStmt):
            if statement.value is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(statement.value, instructions, parent_key)
            instructions.append(Instruction("RETURN_VALUE"))

    def _emit_expr(
        self,
        expr,
        instructions: list[Instruction],
        parent_key: str = "<module>",
        name_bindings: dict[str, str] | None = None,
    ) -> None:
        name_bindings = name_bindings or {}
        if isinstance(expr, IfExpr):
            else_label = self._new_label("ifexpr_else")
            end_label = self._new_label("ifexpr_end")
            self._emit_expr(expr.condition, instructions, parent_key, name_bindings)
            instructions.append(Instruction("JUMP_IF_FALSE", else_label))
            self._emit_expr(expr.body, instructions, parent_key, name_bindings)
            instructions.append(Instruction("JUMP", end_label))
            instructions.append(Instruction("LABEL", else_label))
            self._emit_expr(expr.orelse, instructions, parent_key, name_bindings)
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, LambdaExpr):
            lowered = self._lower_function(expr.func_def, parent_key=parent_key or "<lambda>")
            for default in expr.func_def.defaults:
                self._emit_expr(default, instructions, parent_key, name_bindings)
            kwonly_default_names = [name for name in expr.func_def.kwonly_params if name in expr.func_def.kwonly_defaults]
            for name in kwonly_default_names:
                self._emit_expr(expr.func_def.kwonly_defaults[name], instructions, parent_key, name_bindings)
            instructions.append(Instruction("MAKE_FUNCTION", (lowered.key, len(expr.func_def.defaults), kwonly_default_names)))
            return

        if isinstance(expr, ConstantExpr):
            instructions.append(Instruction("LOAD_CONST", expr.value))
            return

        if isinstance(expr, NameExpr):
            self._emit_load_name(name_bindings.get(expr.name, expr.name), instructions)
            return

        if isinstance(expr, BinaryExpr):
            self._emit_expr(expr.left, instructions, parent_key, name_bindings)
            self._emit_expr(expr.right, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BINARY_OP", expr.op))
            return

        if isinstance(expr, CompareExpr):
            self._emit_expr(expr.left, instructions, parent_key, name_bindings)
            self._emit_expr(expr.right, instructions, parent_key, name_bindings)
            instructions.append(Instruction("COMPARE_OP", expr.op))
            return

        if isinstance(expr, UnaryExpr):
            self._emit_expr(expr.operand, instructions, parent_key, name_bindings)
            instructions.append(Instruction("UNARY_OP", expr.op))
            return

        if isinstance(expr, BoolOpExpr):
            end_label = self._new_label("bool_end")
            short_label = self._new_label("bool_short")
            self._emit_expr(expr.left, instructions, parent_key, name_bindings)
            if expr.op == "and":
                instructions.append(Instruction("JUMP_IF_FALSE", short_label))
                self._emit_expr(expr.right, instructions, parent_key, name_bindings)
                instructions.append(Instruction("TO_BOOL"))
                instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", short_label))
                instructions.append(Instruction("LOAD_CONST", False))
            else:
                instructions.append(Instruction("JUMP_IF_TRUE", short_label))
                self._emit_expr(expr.right, instructions, parent_key, name_bindings)
                instructions.append(Instruction("TO_BOOL"))
                instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", short_label))
                instructions.append(Instruction("LOAD_CONST", True))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, CallExpr):
            for arg in expr.args:
                self._emit_expr(arg, instructions, parent_key, name_bindings)
            callee_name = name_bindings.get(expr.func_name, expr.func_name)
            if expr.kwargs:
                for kw_arg in expr.kwargs.values():
                    self._emit_expr(kw_arg, instructions, parent_key, name_bindings)
                instructions.append(Instruction("CALL_FUNCTION_KW", (callee_name, len(expr.args), list(expr.kwargs.keys()))))
            else:
                instructions.append(Instruction("CALL_FUNCTION", (callee_name, len(expr.args))))
            return

        if isinstance(expr, ListExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BUILD_LIST", len(expr.elements)))
            return

        if isinstance(expr, TupleExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BUILD_TUPLE", len(expr.elements)))
            return

        if isinstance(expr, DictExpr):
            for key, value in zip(expr.keys, expr.values):
                self._emit_expr(key, instructions, parent_key, name_bindings)
                self._emit_expr(value, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BUILD_MAP", len(expr.keys)))
            return

        if isinstance(expr, SetExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BUILD_SET", len(expr.elements)))
            return

        if isinstance(expr, ListCompExpr):
            result_name = self._new_temp("listcomp")
            instructions.append(Instruction("BUILD_LIST", 0))
            instructions.append(Instruction("STORE_NAME", result_name))
            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                lambda bindings: self._emit_list_comp_append(expr.element, result_name, instructions, parent_key, bindings),
            )
            self._emit_load_name(result_name, instructions)
            instructions.append(Instruction("DELETE_NAME", result_name))
            return

        if isinstance(expr, SetCompExpr):
            result_name = self._new_temp("setcomp")
            instructions.append(Instruction("BUILD_SET", 0))
            instructions.append(Instruction("STORE_NAME", result_name))
            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                lambda bindings: self._emit_set_comp_add(expr.element, result_name, instructions, parent_key, bindings),
            )
            self._emit_load_name(result_name, instructions)
            instructions.append(Instruction("DELETE_NAME", result_name))
            return

        if isinstance(expr, DictCompExpr):
            result_name = self._new_temp("dictcomp")
            instructions.append(Instruction("BUILD_MAP", 0))
            instructions.append(Instruction("STORE_NAME", result_name))
            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                lambda bindings: self._emit_dict_comp_store(expr, result_name, instructions, parent_key, bindings),
            )
            self._emit_load_name(result_name, instructions)
            instructions.append(Instruction("DELETE_NAME", result_name))
            return

        if isinstance(expr, SliceExpr):
            if expr.lower is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(expr.lower, instructions, parent_key, name_bindings)
            if expr.upper is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(expr.upper, instructions, parent_key, name_bindings)
            if expr.step is None:
                instructions.append(Instruction("BUILD_SLICE", 2))
            else:
                self._emit_expr(expr.step, instructions, parent_key, name_bindings)
                instructions.append(Instruction("BUILD_SLICE", 3))
            return

        if isinstance(expr, IndexExpr):
            self._emit_expr(expr.collection, instructions, parent_key, name_bindings)
            self._emit_expr(expr.index, instructions, parent_key, name_bindings)
            instructions.append(Instruction("BINARY_SUBSCR"))
            return

        if isinstance(expr, AttributeExpr):
            self._emit_expr(expr.object, instructions, parent_key, name_bindings)
            instructions.append(Instruction("LOAD_ATTR", expr.attr_name))
            return

        if isinstance(expr, MethodCallExpr):
            self._emit_expr(expr.object, instructions, parent_key, name_bindings)
            for arg in expr.args:
                self._emit_expr(arg, instructions, parent_key, name_bindings)
            if expr.kwargs:
                for kw_arg in expr.kwargs.values():
                    self._emit_expr(kw_arg, instructions, parent_key, name_bindings)
                instructions.append(Instruction("CALL_METHOD_KW", (expr.method_name, len(expr.args), list(expr.kwargs.keys()))))
            else:
                instructions.append(Instruction("CALL_METHOD", (expr.method_name, len(expr.args))))
            return

        instructions.append(Instruction("LOAD_CONST", None))

    @staticmethod
    def _collect_scope_declarations(body: list[object]) -> tuple[set[str], set[str]]:
        global_names: set[str] = set()
        nonlocal_names: set[str] = set()
        for statement in body:
            if isinstance(statement, GlobalStmt):
                global_names.update(statement.names)
            elif isinstance(statement, NonlocalStmt):
                nonlocal_names.update(statement.names)
        return global_names, nonlocal_names

    def _emit_load_name(self, name: str, instructions: list[Instruction]) -> None:
        if self._declares_global(name):
            instructions.append(Instruction("LOAD_GLOBAL", name))
            return
        if self._declares_nonlocal(name):
            instructions.append(Instruction("LOAD_DEREF", name))
            return
        instructions.append(Instruction("LOAD_NAME", name))

    def _emit_store_name(self, name: str, instructions: list[Instruction]) -> None:
        if self._declares_global(name):
            instructions.append(Instruction("STORE_GLOBAL", name))
            return
        if self._declares_nonlocal(name):
            instructions.append(Instruction("STORE_DEREF", name))
            return
        instructions.append(Instruction("STORE_NAME", name))

    def _declares_global(self, name: str) -> bool:
        return bool(self.scope_stack and name in self.scope_stack[-1][0])

    def _declares_nonlocal(self, name: str) -> bool:
        return bool(self.scope_stack and name in self.scope_stack[-1][1])

    def _emit_comprehension(
        self,
        generators: list[Comprehension],
        instructions: list[Instruction],
        parent_key: str,
        emit_body,
        *,
        depth: int = 0,
        name_bindings: dict[str, str] | None = None,
    ) -> None:
        name_bindings = dict(name_bindings or {})
        generator = generators[depth]
        loop_target = self._new_temp(generator.target)
        continue_label = self._new_label("comp_continue")
        end_label = self._new_label("comp_end")
        self._emit_expr(generator.iterator, instructions, parent_key, name_bindings)
        instructions.append(Instruction("GET_ITER"))
        instructions.append(Instruction("LABEL", continue_label))
        instructions.append(Instruction("FOR_ITER", end_label))
        instructions.append(Instruction("STORE_NAME", loop_target))
        next_bindings = dict(name_bindings)
        next_bindings[generator.target] = loop_target
        skip_label = self._new_label("comp_skip")
        for condition in generator.ifs:
            self._emit_expr(condition, instructions, parent_key, next_bindings)
            instructions.append(Instruction("JUMP_IF_FALSE", skip_label))
        if depth + 1 < len(generators):
            self._emit_comprehension(
                generators,
                instructions,
                parent_key,
                emit_body,
                depth=depth + 1,
                name_bindings=next_bindings,
            )
        else:
            emit_body(next_bindings)
        instructions.append(Instruction("LABEL", skip_label))
        instructions.append(Instruction("JUMP", continue_label))
        instructions.append(Instruction("LABEL", end_label))

    def _emit_list_comp_append(self, element, result_name: str, instructions: list[Instruction], parent_key: str, name_bindings: dict[str, str]) -> None:
        self._emit_load_name(result_name, instructions)
        self._emit_expr(element, instructions, parent_key, name_bindings)
        instructions.append(Instruction("CALL_METHOD", ("append", 1)))
        instructions.append(Instruction("POP_TOP"))

    def _emit_set_comp_add(self, element, result_name: str, instructions: list[Instruction], parent_key: str, name_bindings: dict[str, str]) -> None:
        self._emit_load_name(result_name, instructions)
        self._emit_expr(element, instructions, parent_key, name_bindings)
        instructions.append(Instruction("CALL_METHOD", ("add", 1)))
        instructions.append(Instruction("POP_TOP"))

    def _emit_dict_comp_store(self, expr: DictCompExpr, result_name: str, instructions: list[Instruction], parent_key: str, name_bindings: dict[str, str]) -> None:
        self._emit_load_name(result_name, instructions)
        self._emit_expr(expr.key, instructions, parent_key, name_bindings)
        self._emit_expr(expr.value, instructions, parent_key, name_bindings)
        instructions.append(Instruction("STORE_SUBSCR"))

    def _new_temp(self, prefix: str) -> str:
        self.temp_counter += 1
        return f"__{prefix}_{self.temp_counter}"

    @staticmethod
    def _import_binding_name(statement: ImportStmt) -> str:
        return statement.alias or statement.module.split(".", 1)[0]

    def _literal_default(self, expr):
        if isinstance(expr, ConstantExpr):
            return expr.value
        if isinstance(expr, ListExpr):
            return [self._literal_default(element) for element in expr.elements]
        if isinstance(expr, TupleExpr):
            return tuple(self._literal_default(element) for element in expr.elements)
        if isinstance(expr, DictExpr):
            return {
                self._literal_default(key): self._literal_default(value)
                for key, value in zip(expr.keys, expr.values)
            }
        if isinstance(expr, SetExpr):
            return {self._literal_default(element) for element in expr.elements}
        return None

    def _new_label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def _new_function_key(self, parent_key: str, name: str) -> str:
        self.function_counter += 1
        return f"{parent_key}.{name}#{self.function_counter}"

    @staticmethod
    def _resolve_labels(instructions: list[Instruction]) -> list[Instruction]:
        label_positions: dict[str, int] = {}
        lowered: list[Instruction] = []
        for instruction in instructions:
            if instruction.opcode == "LABEL":
                label_positions[instruction.arg] = len(lowered)
                continue
            lowered.append(instruction)

        for instruction in lowered:
            if instruction.opcode in {"JUMP", "JUMP_IF_FALSE", "JUMP_IF_TRUE", "FOR_ITER"}:
                instruction.arg = label_positions[instruction.arg]
            elif instruction.opcode == "TRY_FINALLY":
                instruction.arg = label_positions[instruction.arg]
            elif instruction.opcode == "TRY_EXCEPT":
                instruction.arg = [
                    (label_positions[label], type_name, bind_name)
                    for label, type_name, bind_name in instruction.arg
                ]
        return lowered
