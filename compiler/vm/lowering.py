from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    BreakStmt,
    CallExpr,
    CallValueExpr,
    ClassDef,
    Comprehension,
    CompareExpr,
    CompareChainExpr,
    ConstantExpr,
    ContinueStmt,
    DeleteStmt,
    DictCompExpr,
    DictExpr,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    IfExpr,
    IfStmt,
    ImportStmt,
    IndexExpr,
    LambdaExpr,
    ListCompExpr,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetCompExpr,
    SetExpr,
    SliceExpr,
    StarUnpackAssignStmt,
    StarredExpr,
    KwStarredExpr,
    NamedExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WhileStmt,
    WithStmt,
    YieldExpr,
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

    def lower(
        self,
        program: Program,
        *,
        module_name: str = "__main__",
        filename: str = "<stdin>",
    ) -> BytecodeModule:
        self.functions = {}

        top_level_bindings: dict[str, str] = {}

        for statement in program.body:
            if isinstance(statement, FunctionDef):
                lowered = self._lower_function(
                    statement,
                    parent_key=module_name,
                )
                top_level_bindings[statement.name] = lowered.key

        entry = self._lower_body(
            "<module>",
            [],
            program.body,
        )

        entry.key = f"{module_name}:<module>"

        return BytecodeModule(
            name=module_name,
            filename=filename,
            functions=dict(self.functions),
            top_level_bindings=top_level_bindings,
            entrypoint=entry,
        )

    def _lower_function(
        self,
        function: FunctionDef,
        *,
        parent_key: str,
        owner_class_name: str | None = None,
    ) -> BytecodeFunction:
        function_key = self._new_function_key(parent_key, function.name)

        lowered = self._lower_body(
            function.name,
            function.params,
            function.body,
            parent_key=function_key,
        )

        lowered.key = function_key
        lowered.owner_class_name = owner_class_name
        lowered.is_generator = self._function_uses_yield(function.body)

        lowered.defaults = [
            self._literal_default(default)
            for default in function.defaults
        ]

        lowered.kwonly_params = list(function.kwonly_params)

        lowered.kwonly_defaults = {
            name: self._literal_default(default)
            for name, default in function.kwonly_defaults.items()
        }

        lowered.vararg_name = function.vararg
        lowered.kwarg_name = function.kwarg

        self.functions[function_key] = lowered

        return lowered

    def _lower_body(
        self,
        name: str,
        params: list[str],
        body: list[object],
        parent_key: str | None = None,
    ) -> BytecodeFunction:
        instructions: list[Instruction] = []

        global_names, nonlocal_names = self._collect_scope_declarations(body)

        self.scope_stack.append((global_names, nonlocal_names))

        try:
            for statement in body:
                self._emit_statement(
                    statement,
                    instructions,
                    parent_key or name,
                )
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

    def _emit_statement(
        self,
        statement,
        instructions: list[Instruction],
        parent_key: str,
    ) -> None:

        if isinstance(statement, FunctionDef):
            lowered = self._lower_function(
                statement,
                parent_key=parent_key,
            )

            for default in statement.defaults:
                self._emit_expr(default, instructions)

            kwonly_default_names = [
                name
                for name in statement.kwonly_params
                if name in statement.kwonly_defaults
            ]

            for name in kwonly_default_names:
                self._emit_expr(
                    statement.kwonly_defaults[name],
                    instructions,
                )

            instructions.append(
                Instruction(
                    "MAKE_FUNCTION",
                    (
                        lowered.key,
                        len(statement.defaults),
                        kwonly_default_names,
                    ),
                )
            )

            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, ClassDef):
            method_specs = []

            class_parent = self._new_function_key(
                parent_key,
                statement.name,
            )

            for method in statement.methods:
                lowered = self._lower_function(
                    method,
                    parent_key=class_parent,
                    owner_class_name=statement.name,
                )

                method_specs.append((method.name, lowered.key))

            for base in statement.bases:
                self._emit_expr(base, instructions, parent_key)

            attribute_names = []

            for attribute in statement.attributes:
                self._emit_expr(
                    attribute.value,
                    instructions,
                    parent_key,
                )

                attribute_names.append(attribute.name)

            instructions.append(
                Instruction(
                    "BUILD_CLASS",
                    (
                        statement.name,
                        method_specs,
                        len(statement.bases),
                        attribute_names,
                    ),
                )
            )

            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, AssignStmt):
            self._emit_expr(statement.value, instructions)
            self._emit_store_name(statement.name, instructions)
            return

        if isinstance(statement, UnpackAssignStmt):
            self._emit_expr(
                statement.value,
                instructions,
                parent_key,
            )

            instructions.append(
                Instruction(
                    "UNPACK_SEQUENCE",
                    len(statement.targets),
                )
            )

            for target in statement.targets:
                self._emit_store_name(target, instructions)

            return

        if isinstance(statement, StarUnpackAssignStmt):
            self._emit_expr(
                statement.value,
                instructions,
                parent_key,
            )

            instructions.append(
                Instruction(
                    "UNPACK_EX",
                    (len(statement.prefix_targets), len(statement.suffix_targets)),
                )
            )

            # Stack order after UNPACK_EX: prefix items, rest-list, suffix items
            for target in statement.prefix_targets:
                self._emit_store_name(target, instructions)
            self._emit_store_name(statement.starred_target, instructions)
            for target in statement.suffix_targets:
                self._emit_store_name(target, instructions)
            return

        if isinstance(statement, AttributeAssignStmt):
            self._emit_expr(statement.object, instructions)
            self._emit_expr(statement.value, instructions)

            instructions.append(
                Instruction(
                    "STORE_ATTR",
                    statement.attr_name,
                )
            )
            return

        if isinstance(statement, PassStmt):
            return

        if isinstance(statement, (GlobalStmt, NonlocalStmt)):
            return

        if isinstance(statement, DeleteStmt):
            for target in statement.targets:

                if isinstance(target, NameExpr):
                    instructions.append(
                        Instruction(
                            "DELETE_NAME",
                            target.name,
                        )
                    )

                elif isinstance(target, AttributeExpr):
                    self._emit_expr(
                        target.object,
                        instructions,
                        parent_key,
                    )

                    instructions.append(
                        Instruction(
                            "DELETE_ATTR",
                            target.attr_name,
                        )
                    )

                elif isinstance(target, IndexExpr):
                    self._emit_expr(
                        target.collection,
                        instructions,
                        parent_key,
                    )

                    self._emit_expr(
                        target.index,
                        instructions,
                        parent_key,
                    )

                    instructions.append(
                        Instruction("DELETE_SUBSCR")
                    )

            return

        if isinstance(statement, PrintStmt):
            for value in statement.values:
                self._emit_expr(value, instructions)

            if statement.sep is not None:
                self._emit_expr(statement.sep, instructions)

            if statement.end is not None:
                self._emit_expr(statement.end, instructions)

            instructions.append(
                Instruction(
                    "PRINT",
                    (
                        len(statement.values),
                        statement.sep is not None,
                        statement.end is not None,
                    ),
                )
            )
            return

        if isinstance(statement, ExprStmt):
            self._emit_expr(
                statement.expr,
                instructions,
                parent_key,
            )
            instructions.append(Instruction("POP_TOP"))
            return

        if isinstance(statement, ReturnStmt):

            if statement.value is None:
                instructions.append(
                    Instruction("LOAD_CONST", None)
                )
            else:
                self._emit_expr(
                    statement.value,
                    instructions,
                    parent_key,
                )

            instructions.append(
                Instruction("RETURN_VALUE")
            )
            return

        if isinstance(statement, ImportStmt):
            bind_root = "." in statement.module and statement.alias is None

            instructions.append(
                Instruction(
                    "IMPORT_MODULE",
                    (statement.module, bind_root, 0),
                )
            )

            self._emit_store_name(
                self._import_binding_name(statement),
                instructions,
            )
            return

        if isinstance(statement, FromImportStmt):
            instructions.append(
                Instruction(
                    "IMPORT_MODULE",
                    (statement.module, False, statement.level),
                )
            )

            if statement.name == "*":
                instructions.append(
                    Instruction("IMPORT_STAR")
                )
                return

            instructions.append(
                Instruction("LOAD_ATTR", statement.name)
            )

            self._emit_store_name(
                statement.alias or statement.name,
                instructions,
            )
            return

        if isinstance(statement, IfStmt):
            else_label = self._new_label("if_else")
            end_label = self._new_label("if_end")

            self._emit_expr(statement.condition, instructions, parent_key)
            instructions.append(
                Instruction("JUMP_IF_FALSE", else_label)
            )

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
            end_label = self._new_label("while_end")

            instructions.append(Instruction("LABEL", start_label))
            self._emit_expr(statement.condition, instructions, parent_key)
            instructions.append(
                Instruction("JUMP_IF_FALSE", end_label)
            )

            self.loop_stack.append((start_label, end_label))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            self.loop_stack.pop()

            instructions.append(Instruction("JUMP", start_label))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, ForStmt):
            start_label = self._new_label("for_start")
            end_label = self._new_label("for_end")

            self._emit_expr(statement.iterator, instructions, parent_key)
            instructions.append(Instruction("GET_ITER"))
            instructions.append(Instruction("LABEL", start_label))
            instructions.append(Instruction("FOR_ITER", end_label))

            if isinstance(statement.target, list):
                instructions.append(
                    Instruction(
                        "UNPACK_SEQUENCE",
                        str(len(statement.target)),
                    )
                )
                for target in statement.target:
                    self._emit_store_name(target, instructions)
            else:
                self._emit_store_name(statement.target, instructions)

            self.loop_stack.append((start_label, end_label))
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            self.loop_stack.pop()

            instructions.append(Instruction("JUMP", start_label))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, BreakStmt):
            if not self.loop_stack:
                return
            _, break_label = self.loop_stack[-1]
            instructions.append(Instruction("JUMP", break_label))
            return

        if isinstance(statement, ContinueStmt):
            if not self.loop_stack:
                return
            continue_label, _ = self.loop_stack[-1]
            instructions.append(Instruction("JUMP", continue_label))
            return

        if isinstance(statement, RaiseStmt):
            if statement.value is not None:
                self._emit_expr(statement.value, instructions, parent_key)
            if statement.cause is not None:
                self._emit_expr(statement.cause, instructions, parent_key)
                instructions.append(Instruction("RAISE_CAUSE"))
            else:
                instructions.append(Instruction("RAISE"))
            return

        if isinstance(statement, TryStmt):
            end_label = self._new_label("try_end")
            else_label = self._new_label("try_else") if statement.orelse else None
            finally_label = self._new_label("try_finally") if statement.finalbody else None

            handler_specs = []
            for handler in statement.handlers:
                handler_label = self._new_label("except")
                handler_specs.append(
                    (handler_label, handler.type_name, handler.name)
                )

            if handler_specs:
                instructions.append(
                    Instruction("TRY_EXCEPT", handler_specs)
                )

            if finally_label is not None:
                instructions.append(
                    Instruction("TRY_FINALLY", finally_label)
                )

            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)

            if handler_specs:
                instructions.append(Instruction("POP_TRY"))

            if else_label is not None:
                instructions.append(Instruction("JUMP", else_label))
            elif finally_label is not None:
                instructions.append(Instruction("JUMP", finally_label))
            else:
                instructions.append(Instruction("JUMP", end_label))

            for handler, (label, type_name, bind_name) in zip(statement.handlers, handler_specs):
                instructions.append(Instruction("LABEL", label))
                if bind_name is not None:
                    instructions.append(
                        Instruction("LOAD_EXCEPTION", bind_name)
                    )
                for child in handler.body:
                    self._emit_statement(child, instructions, parent_key)
                instructions.append(Instruction("POP_EXCEPT"))
                if finally_label is not None:
                    instructions.append(Instruction("JUMP", finally_label))
                else:
                    instructions.append(Instruction("JUMP", end_label))

            if else_label is not None:
                instructions.append(Instruction("LABEL", else_label))
                for child in statement.orelse:
                    self._emit_statement(child, instructions, parent_key)
                if finally_label is not None:
                    instructions.append(Instruction("JUMP", finally_label))
                else:
                    instructions.append(Instruction("JUMP", end_label))

            if finally_label is not None:
                instructions.append(Instruction("LABEL", finally_label))
                for child in statement.finalbody:
                    self._emit_statement(child, instructions, parent_key)
                instructions.append(Instruction("END_FINALLY"))

            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(statement, WithStmt):
            self._emit_expr(statement.context_expr, instructions, parent_key)
            finally_label = self._new_label("with_finally")
            instructions.append(Instruction("WITH_ENTER", statement.optional_var))
            instructions.append(
                Instruction(
                    "TRY_FINALLY",
                    finally_label,
                )
            )
            for child in statement.body:
                self._emit_statement(child, instructions, parent_key)
            instructions.append(Instruction("POP_TRY"))
            instructions.append(Instruction("JUMP", finally_label))
            instructions.append(Instruction("LABEL", finally_label))
            instructions.append(Instruction("WITH_EXIT"))
            instructions.append(Instruction("END_FINALLY"))
            return

    def _emit_expr(
        self,
        expr,
        instructions: list[Instruction],
        parent_key: str = "<module>",
        name_bindings: dict[str, str] | None = None,
    ) -> None:

        name_bindings = name_bindings or {}

        if isinstance(expr, ConstantExpr):
            instructions.append(
                Instruction("LOAD_CONST", expr.value)
            )
            return

        if isinstance(expr, NameExpr):
            self._emit_load_name(
                name_bindings.get(expr.name, expr.name),
                instructions,
            )
            return

        if isinstance(expr, BinaryExpr):
            self._emit_expr(
                expr.left,
                instructions,
                parent_key,
                name_bindings,
            )

            self._emit_expr(
                expr.right,
                instructions,
                parent_key,
                name_bindings,
            )

            instructions.append(
                Instruction("BINARY_OP", expr.op)
            )
            return

        if isinstance(expr, UnaryExpr):
            self._emit_expr(
                expr.operand,
                instructions,
                parent_key,
                name_bindings,
            )

            instructions.append(
                Instruction("UNARY_OP", expr.op)
            )
            return

        if isinstance(expr, CompareExpr):
            self._emit_expr(
                expr.left,
                instructions,
                parent_key,
                name_bindings,
            )

            self._emit_expr(
                expr.right,
                instructions,
                parent_key,
                name_bindings,
            )

            instructions.append(
                Instruction("COMPARE_OP", expr.op)
            )
            return

        if isinstance(expr, CompareChainExpr):
            temp_names = []

            for operand in expr.operands:
                self._emit_expr(
                    operand,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                temp_name = self._new_temp("cmp")
                self._emit_store_name(temp_name, instructions)
                temp_names.append(temp_name)

            false_label = self._new_label("cmp_false")
            end_label = self._new_label("cmp_end")

            for index, op in enumerate(expr.ops):
                self._emit_load_name(temp_names[index], instructions)
                self._emit_load_name(temp_names[index + 1], instructions)
                instructions.append(Instruction("COMPARE_OP", op))
                instructions.append(
                    Instruction("JUMP_IF_FALSE", false_label)
                )

            instructions.append(Instruction("LOAD_CONST", True))
            instructions.append(Instruction("JUMP", end_label))
            instructions.append(Instruction("LABEL", false_label))
            instructions.append(Instruction("LOAD_CONST", False))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, BoolOpExpr):
            false_label = self._new_label("bool_false")
            true_label = self._new_label("bool_true")
            end_label = self._new_label("bool_end")

            self._emit_expr(
                expr.left,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("TO_BOOL"))

            if expr.op == "and":
                instructions.append(
                    Instruction("JUMP_IF_FALSE", false_label)
                )
                self._emit_expr(
                    expr.right,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                instructions.append(Instruction("TO_BOOL"))
                instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", false_label))
                instructions.append(Instruction("LOAD_CONST", False))
                instructions.append(Instruction("LABEL", end_label))
                return

            instructions.append(Instruction("JUMP_IF_TRUE", true_label))
            self._emit_expr(
                expr.right,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("TO_BOOL"))
            instructions.append(Instruction("JUMP", end_label))
            instructions.append(Instruction("LABEL", true_label))
            instructions.append(Instruction("LOAD_CONST", True))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, IfExpr):
            else_label = self._new_label("ifexpr_else")
            end_label = self._new_label("ifexpr_end")

            self._emit_expr(
                expr.condition,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("JUMP_IF_FALSE", else_label))
            self._emit_expr(
                expr.body,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("JUMP", end_label))
            instructions.append(Instruction("LABEL", else_label))
            self._emit_expr(
                expr.orelse,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, LambdaExpr):
            lowered = self._lower_function(
                expr.func_def,
                parent_key=parent_key or "<lambda>",
            )

            for default in expr.func_def.defaults:
                self._emit_expr(default, instructions, parent_key, name_bindings)

            kwonly_default_names = [
                name
                for name in expr.func_def.kwonly_params
                if name in expr.func_def.kwonly_defaults
            ]
            for name in kwonly_default_names:
                self._emit_expr(
                    expr.func_def.kwonly_defaults[name],
                    instructions,
                    parent_key,
                    name_bindings,
                )

            instructions.append(
                Instruction(
                    "MAKE_FUNCTION",
                    (
                        lowered.key,
                        len(expr.func_def.defaults),
                        kwonly_default_names,
                    ),
                )
            )
            return

        if isinstance(expr, YieldExpr):
            if expr.value is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(
                    expr.value,
                    instructions,
                    parent_key,
                    name_bindings,
                )
            instructions.append(Instruction("YIELD_VALUE"))
            return

        if isinstance(expr, CallExpr):

            star_flags = [isinstance(arg, StarredExpr) for arg in expr.args]

            for arg in expr.args:
                if isinstance(arg, StarredExpr):
                    self._emit_expr(
                        arg.value,
                        instructions,
                        parent_key,
                        name_bindings,
                    )
                else:
                    self._emit_expr(
                        arg,
                        instructions,
                        parent_key,
                        name_bindings,
                    )

            if any(star_flags):
                instructions.append(
                    Instruction(
                        "EXPAND_ARGS",
                        star_flags,
                    )
                )

            # Keywords: support explicit keyword args + **kwargs splats.
            # Convention:
            #   - emit explicit kwarg values (in kwarg_names order)
            #   - emit each **mapping value
            #   - BUILD_KWARGS consumes those values + metadata and pushes a single kwargs dict
            kwarg_names = list(expr.kwargs.keys())
            for name in kwarg_names:
                self._emit_expr(expr.kwargs[name], instructions, parent_key, name_bindings)

            for part in getattr(expr, "kw_starred", []):
                assert isinstance(part, KwStarredExpr)
                self._emit_expr(part.value, instructions, parent_key, name_bindings)

            if kwarg_names or getattr(expr, "kw_starred", []):
                instructions.append(
                    Instruction(
                        "BUILD_KWARGS",
                        (kwarg_names, len(getattr(expr, "kw_starred", []))),
                    )
                )

            opcode_arg = (
                expr.func_name,
                -1 if any(star_flags) else len(expr.args),
                True,
            ) if (kwarg_names or getattr(expr, "kw_starred", [])) else (
                expr.func_name,
                -1 if any(star_flags) else len(expr.args),
            )

            instructions.append(
                Instruction(
                    "CALL_FUNCTION",
                    opcode_arg,
                )
            )
            return

        if isinstance(expr, CallValueExpr):
            self._emit_expr(
                expr.callee,
                instructions,
                parent_key,
                name_bindings,
            )

            star_flags = [isinstance(arg, StarredExpr) for arg in expr.args]

            for arg in expr.args:
                if isinstance(arg, StarredExpr):
                    self._emit_expr(
                        arg.value,
                        instructions,
                        parent_key,
                        name_bindings,
                    )
                else:
                    self._emit_expr(
                        arg,
                        instructions,
                        parent_key,
                        name_bindings,
                    )

            if any(star_flags):
                instructions.append(Instruction("EXPAND_ARGS", star_flags))

            kwarg_names = list(expr.kwargs.keys())
            for name in kwarg_names:
                self._emit_expr(expr.kwargs[name], instructions, parent_key, name_bindings)

            for part in getattr(expr, "kw_starred", []):
                assert isinstance(part, KwStarredExpr)
                self._emit_expr(part.value, instructions, parent_key, name_bindings)

            if kwarg_names or getattr(expr, "kw_starred", []):
                instructions.append(
                    Instruction(
                        "BUILD_KWARGS",
                        (kwarg_names, len(getattr(expr, "kw_starred", []))),
                    )
                )

            opcode_arg = (
                -1 if any(star_flags) else len(expr.args),
                True,
            ) if (kwarg_names or getattr(expr, "kw_starred", [])) else (-1 if any(star_flags) else len(expr.args))

            instructions.append(
                Instruction("CALL_VALUE", opcode_arg)
            )
            return

        if isinstance(expr, NamedExpr):
            # Evaluate value, store into target, and leave the value on the stack.
            self._emit_expr(expr.value, instructions, parent_key, name_bindings)
            instructions.append(Instruction("DUP_TOP"))
            instructions.append(Instruction("STORE_NAME", expr.target))
            return

        if isinstance(expr, AttributeExpr):
            self._emit_expr(
                expr.object,
                instructions,
                parent_key,
                name_bindings,
            )

            instructions.append(
                Instruction("LOAD_ATTR", expr.attr_name)
            )
            return

        if isinstance(expr, MethodCallExpr):
            self._emit_expr(
                expr.object,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(
                Instruction("LOAD_ATTR", expr.method_name)
            )

            for arg in expr.args:
                self._emit_expr(
                    arg,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            kwarg_names = list(expr.kwargs.keys())
            for name in kwarg_names:
                self._emit_expr(
                    expr.kwargs[name],
                    instructions,
                    parent_key,
                    name_bindings,
                )

            if kwarg_names:
                instructions.append(
                    Instruction(
                        "BUILD_KWARGS",
                        (kwarg_names, 0),
                    )
                )

            opcode_arg = (
                len(expr.args),
                True,
            ) if kwarg_names else len(expr.args)

            instructions.append(
                Instruction("CALL_VALUE", opcode_arg)
            )
            return

        if isinstance(expr, ListExpr):

            for element in expr.elements:
                self._emit_expr(
                    element,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            instructions.append(
                Instruction(
                    "BUILD_LIST",
                    len(expr.elements),
                )
            )
            return

        if isinstance(expr, ListCompExpr):
            temp_name = self._new_temp("listcomp")
            instructions.append(Instruction("LOAD_CONST", []))
            self._emit_store_name(temp_name, instructions)

            def emit_append():
                self._emit_load_name(temp_name, instructions)
                instructions.append(Instruction("LOAD_ATTR", "append"))
                self._emit_expr(
                    expr.element,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                instructions.append(Instruction("CALL_VALUE", 1))
                instructions.append(Instruction("POP_TOP"))

            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                name_bindings,
                emit_append,
            )

            self._emit_load_name(temp_name, instructions)
            return

        if isinstance(expr, TupleExpr):

            for element in expr.elements:
                self._emit_expr(
                    element,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            instructions.append(
                Instruction(
                    "BUILD_TUPLE",
                    len(expr.elements),
                )
            )
            return

        if isinstance(expr, DictExpr):

            for key, value in zip(expr.keys, expr.values):
                self._emit_expr(
                    key,
                    instructions,
                    parent_key,
                    name_bindings,
                )

                self._emit_expr(
                    value,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            instructions.append(
                Instruction(
                    "BUILD_MAP",
                    len(expr.keys),
                )
            )
            return

        if isinstance(expr, DictCompExpr):
            temp_name = self._new_temp("dictcomp")
            instructions.append(Instruction("LOAD_CONST", {}))
            self._emit_store_name(temp_name, instructions)

            def emit_store():
                self._emit_load_name(temp_name, instructions)
                self._emit_expr(
                    expr.key,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                self._emit_expr(
                    expr.value,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                instructions.append(Instruction("STORE_SUBSCR"))

            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                name_bindings,
                emit_store,
            )

            self._emit_load_name(temp_name, instructions)
            return

        if isinstance(expr, SetExpr):

            for element in expr.elements:
                self._emit_expr(
                    element,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            instructions.append(
                Instruction(
                    "BUILD_SET",
                    len(expr.elements),
                )
            )
            return

        if isinstance(expr, SetCompExpr):
            temp_name = self._new_temp("setcomp")
            instructions.append(Instruction("LOAD_CONST", set()))
            self._emit_store_name(temp_name, instructions)

            def emit_add():
                self._emit_load_name(temp_name, instructions)
                instructions.append(Instruction("LOAD_ATTR", "add"))
                self._emit_expr(
                    expr.element,
                    instructions,
                    parent_key,
                    name_bindings,
                )
                instructions.append(Instruction("CALL_VALUE", 1))
                instructions.append(Instruction("POP_TOP"))

            self._emit_comprehension(
                expr.generators,
                instructions,
                parent_key,
                name_bindings,
                emit_add,
            )

            self._emit_load_name(temp_name, instructions)
            return

        if isinstance(expr, IndexExpr):
            self._emit_expr(
                expr.collection,
                instructions,
                parent_key,
                name_bindings,
            )
            self._emit_expr(
                expr.index,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("BINARY_SUBSCR"))
            return

        if isinstance(expr, SliceExpr):
            if expr.lower is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(
                    expr.lower,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            if expr.upper is None:
                instructions.append(Instruction("LOAD_CONST", None))
            else:
                self._emit_expr(
                    expr.upper,
                    instructions,
                    parent_key,
                    name_bindings,
                )

            if expr.step is None:
                instructions.append(Instruction("BUILD_SLICE", 2))
                return

            self._emit_expr(
                expr.step,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(Instruction("BUILD_SLICE", 3))
            return

        instructions.append(
            Instruction("LOAD_CONST", None)
        )

    def _function_uses_yield(self, body: list[object]) -> bool:
        return any(self._statement_uses_yield(statement) for statement in body)

    def _statement_uses_yield(self, statement) -> bool:
        if isinstance(statement, FunctionDef):
            return False
        if isinstance(statement, ClassDef):
            return any(self._statement_uses_yield(method) for method in statement.methods)
        if isinstance(statement, AssignStmt):
            return self._expr_uses_yield(statement.value)
        if isinstance(statement, UnpackAssignStmt):
            return self._expr_uses_yield(statement.value)
        if isinstance(statement, StarUnpackAssignStmt):
            return self._expr_uses_yield(statement.value)
        if isinstance(statement, AttributeAssignStmt):
            return self._expr_uses_yield(statement.object) or self._expr_uses_yield(statement.value)
        if isinstance(statement, DeleteStmt):
            return any(self._expr_uses_yield(target) for target in statement.targets)
        if isinstance(statement, PrintStmt):
            return any(self._expr_uses_yield(value) for value in statement.values) or (
                statement.sep is not None and self._expr_uses_yield(statement.sep)
            ) or (
                statement.end is not None and self._expr_uses_yield(statement.end)
            )
        if isinstance(statement, ExprStmt):
            return self._expr_uses_yield(statement.expr)
        if isinstance(statement, ReturnStmt):
            return statement.value is not None and self._expr_uses_yield(statement.value)
        if isinstance(statement, IfStmt):
            return self._expr_uses_yield(statement.condition) or any(
                self._statement_uses_yield(child) for child in statement.body + statement.orelse
            )
        if isinstance(statement, WhileStmt):
            return self._expr_uses_yield(statement.condition) or any(
                self._statement_uses_yield(child) for child in statement.body + statement.orelse
            )
        if isinstance(statement, ForStmt):
            return self._expr_uses_yield(statement.iterator) or any(
                self._statement_uses_yield(child) for child in statement.body + statement.orelse
            )
        if isinstance(statement, RaiseStmt):
            return (
                statement.value is not None and self._expr_uses_yield(statement.value)
            ) or (
                statement.cause is not None and self._expr_uses_yield(statement.cause)
            )
        if isinstance(statement, TryStmt):
            return any(self._statement_uses_yield(child) for child in statement.body + statement.orelse + statement.finalbody) or any(
                self._statement_uses_yield(child)
                for handler in statement.handlers
                for child in handler.body
            )
        if isinstance(statement, WithStmt):
            return self._expr_uses_yield(statement.context_expr) or any(
                self._statement_uses_yield(child) for child in statement.body
            )
        return False

    def _expr_uses_yield(self, expr) -> bool:
        if isinstance(expr, YieldExpr):
            return True
        if isinstance(expr, BinaryExpr):
            return self._expr_uses_yield(expr.left) or self._expr_uses_yield(expr.right)
        if isinstance(expr, UnaryExpr):
            return self._expr_uses_yield(expr.operand)
        if isinstance(expr, CompareExpr):
            return self._expr_uses_yield(expr.left) or self._expr_uses_yield(expr.right)
        if isinstance(expr, CompareChainExpr):
            return any(self._expr_uses_yield(operand) for operand in expr.operands)
        if isinstance(expr, BoolOpExpr):
            return self._expr_uses_yield(expr.left) or self._expr_uses_yield(expr.right)
        if isinstance(expr, IfExpr):
            return any(
                self._expr_uses_yield(part)
                for part in (expr.condition, expr.body, expr.orelse)
            )
        if isinstance(expr, LambdaExpr):
            return False
        if isinstance(expr, CallExpr):
            return any(self._expr_uses_yield(arg.value) if isinstance(arg, StarredExpr) else self._expr_uses_yield(arg) for arg in expr.args) or any(
                self._expr_uses_yield(arg) for arg in expr.kwargs.values()
            ) or any(self._expr_uses_yield(part.value) for part in getattr(expr, "kw_starred", []))
        if isinstance(expr, CallValueExpr):
            return self._expr_uses_yield(expr.callee) or any(
                self._expr_uses_yield(arg.value) if isinstance(arg, StarredExpr) else self._expr_uses_yield(arg)
                for arg in expr.args
            ) or any(self._expr_uses_yield(arg) for arg in expr.kwargs.values()) or any(
                self._expr_uses_yield(part.value) for part in getattr(expr, "kw_starred", [])
            )
        if isinstance(expr, AttributeExpr):
            return self._expr_uses_yield(expr.object)
        if isinstance(expr, MethodCallExpr):
            return self._expr_uses_yield(expr.object) or any(self._expr_uses_yield(arg) for arg in expr.args) or any(
                self._expr_uses_yield(arg) for arg in expr.kwargs.values()
            ) or any(self._expr_uses_yield(part.value) for part in getattr(expr, "kw_starred", []))
        if isinstance(expr, ListExpr):
            return any(self._expr_uses_yield(element) for element in expr.elements)
        if isinstance(expr, TupleExpr):
            return any(self._expr_uses_yield(element) for element in expr.elements)
        if isinstance(expr, DictExpr):
            return any(self._expr_uses_yield(key) for key in expr.keys) or any(
                self._expr_uses_yield(value) for value in expr.values
            )
        if isinstance(expr, SetExpr):
            return any(self._expr_uses_yield(element) for element in expr.elements)
        if isinstance(expr, ListCompExpr):
            return self._expr_uses_yield(expr.element) or any(
                self._expr_uses_yield(generator.iterator) or any(self._expr_uses_yield(cond) for cond in generator.ifs)
                for generator in expr.generators
            )
        if isinstance(expr, SetCompExpr):
            return self._expr_uses_yield(expr.element) or any(
                self._expr_uses_yield(generator.iterator) or any(self._expr_uses_yield(cond) for cond in generator.ifs)
                for generator in expr.generators
            )
        if isinstance(expr, DictCompExpr):
            return self._expr_uses_yield(expr.key) or self._expr_uses_yield(expr.value) or any(
                self._expr_uses_yield(generator.iterator) or any(self._expr_uses_yield(cond) for cond in generator.ifs)
                for generator in expr.generators
            )
        if isinstance(expr, IndexExpr):
            return self._expr_uses_yield(expr.collection) or self._expr_uses_yield(expr.index)
        if isinstance(expr, SliceExpr):
            return any(
                part is not None and self._expr_uses_yield(part)
                for part in (expr.lower, expr.upper, expr.step)
            )
        if isinstance(expr, NamedExpr):
            return self._expr_uses_yield(expr.value)
        if isinstance(expr, StarredExpr):
            return self._expr_uses_yield(expr.value)
        if isinstance(expr, KwStarredExpr):
            return self._expr_uses_yield(expr.value)
        return False

    def _emit_comprehension(
        self,
        generators: list[Comprehension],
        instructions: list[Instruction],
        parent_key: str,
        name_bindings: dict[str, str],
        emit_element,
    ) -> None:

        if not generators:
            emit_element()
            return

        generator = generators[0]

        self._emit_expr(
            generator.iterator,
            instructions,
            parent_key,
            name_bindings,
        )
        instructions.append(Instruction("GET_ITER"))

        loop_start = self._new_label("comp_start")
        loop_end = self._new_label("comp_end")

        instructions.append(Instruction("LABEL", loop_start))
        instructions.append(Instruction("FOR_ITER", loop_end))

        self._emit_store_name(generator.target, instructions)

        for predicate in generator.ifs:
            self._emit_expr(
                predicate,
                instructions,
                parent_key,
                name_bindings,
            )
            instructions.append(
                Instruction("JUMP_IF_FALSE", loop_start)
            )

        self._emit_comprehension(
            generators[1:],
            instructions,
            parent_key,
            name_bindings,
            emit_element,
        )

        instructions.append(Instruction("JUMP", loop_start))
        instructions.append(Instruction("LABEL", loop_end))

    @staticmethod
    def _collect_scope_declarations(
        body: list[object],
    ) -> tuple[set[str], set[str]]:

        global_names: set[str] = set()
        nonlocal_names: set[str] = set()

        for statement in body:

            if isinstance(statement, GlobalStmt):
                global_names.update(statement.names)

            elif isinstance(statement, NonlocalStmt):
                nonlocal_names.update(statement.names)

        return global_names, nonlocal_names

    def _emit_load_name(
        self,
        name: str,
        instructions: list[Instruction],
    ) -> None:

        if self._declares_global(name):
            instructions.append(
                Instruction("LOAD_GLOBAL", name)
            )
            return

        if self._declares_nonlocal(name):
            instructions.append(
                Instruction("LOAD_DEREF", name)
            )
            return

        instructions.append(
            Instruction("LOAD_NAME", name)
        )

    def _emit_store_name(
        self,
        name: str,
        instructions: list[Instruction],
    ) -> None:

        if self._declares_global(name):
            instructions.append(
                Instruction("STORE_GLOBAL", name)
            )
            return

        if self._declares_nonlocal(name):
            instructions.append(
                Instruction("STORE_DEREF", name)
            )
            return

        instructions.append(
            Instruction("STORE_NAME", name)
        )

    def _declares_global(self, name: str) -> bool:
        return bool(
            self.scope_stack
            and name in self.scope_stack[-1][0]
        )

    def _declares_nonlocal(self, name: str) -> bool:
        return bool(
            self.scope_stack
            and name in self.scope_stack[-1][1]
        )

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
            return [
                self._literal_default(element)
                for element in expr.elements
            ]

        if isinstance(expr, TupleExpr):
            return tuple(
                self._literal_default(element)
                for element in expr.elements
            )

        if isinstance(expr, DictExpr):
            return {
                self._literal_default(key):
                self._literal_default(value)
                for key, value in zip(expr.keys, expr.values)
            }

        if isinstance(expr, SetExpr):
            return {
                self._literal_default(element)
                for element in expr.elements
            }

        return None

    def _new_label(self, prefix: str) -> str:
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def _new_function_key(
        self,
        parent_key: str,
        name: str,
    ) -> str:

        self.function_counter += 1
        return f"{parent_key}.{name}#{self.function_counter}"

    @staticmethod
    def _resolve_labels(
        instructions: list[Instruction],
    ) -> list[Instruction]:

        label_positions: dict[str, int] = {}
        lowered: list[Instruction] = []

        for instruction in instructions:

            if instruction.opcode == "LABEL":
                label_positions[instruction.arg] = len(lowered)
                continue

            lowered.append(instruction)

        for instruction in lowered:

            if instruction.opcode in {
                "JUMP",
                "JUMP_IF_FALSE",
                "JUMP_IF_TRUE",
                "FOR_ITER",
            }:
                instruction.arg = label_positions[instruction.arg]

            elif instruction.opcode == "TRY_FINALLY":
                instruction.arg = label_positions[instruction.arg]

            elif instruction.opcode == "TRY_EXCEPT":
                instruction.arg = [
                    (
                        label_positions[label],
                        type_name,
                        bind_name,
                    )
                    for label, type_name, bind_name
                    in instruction.arg
                ]

        return lowered
