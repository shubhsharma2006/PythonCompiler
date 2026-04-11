from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    ClassDef,
    CompareExpr,
    ConstantExpr,
    DictExpr,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    IfStmt,
    IndexExpr,
    ImportStmt,
    ListExpr,
    MethodCallExpr,
    NameExpr,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    WhileStmt,
    BreakStmt,
    ContinueStmt,
)
from compiler.vm.bytecode import BytecodeFunction, BytecodeModule, Instruction


class BytecodeLowerer:
    def __init__(self) -> None:
        self.label_counter = 0
        self.function_counter = 0
        self.functions: dict[str, BytecodeFunction] = {}
        self.loop_stack: list[tuple[str, str]] = []

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

    def _lower_function(self, function: FunctionDef, *, parent_key: str) -> BytecodeFunction:
        function_key = self._new_function_key(parent_key, function.name)
        lowered = self._lower_body(function.name, function.params, function.body, parent_key=function_key)
        lowered.key = function_key
        lowered.defaults = [self._literal_default(default) for default in function.defaults]
        self.functions[function_key] = lowered
        return lowered

    def _lower_body(self, name: str, params: list[str], body: list[object], parent_key: str | None = None) -> BytecodeFunction:
        instructions: list[Instruction] = []
        for statement in body:
            self._emit_statement(statement, instructions, parent_key or name)
        instructions.append(Instruction("LOAD_CONST", None))
        instructions.append(Instruction("RETURN_VALUE"))
        return BytecodeFunction(key="", name=name, params=list(params), instructions=self._resolve_labels(instructions))

    def _emit_statement(self, statement, instructions: list[Instruction], parent_key: str) -> None:
        if isinstance(statement, FunctionDef):
            lowered = self._lower_function(statement, parent_key=parent_key)
            for default in statement.defaults:
                self._emit_expr(default, instructions)
            instructions.append(Instruction("MAKE_FUNCTION", (lowered.key, len(statement.defaults))))
            instructions.append(Instruction("STORE_NAME", statement.name))
            return

        if isinstance(statement, ClassDef):
            method_specs = []
            class_parent = self._new_function_key(parent_key, statement.name)
            for method in statement.methods:
                lowered = self._lower_function(method, parent_key=class_parent)
                method_specs.append((method.name, lowered.key))
            instructions.append(Instruction("BUILD_CLASS", (statement.name, method_specs)))
            instructions.append(Instruction("STORE_NAME", statement.name))
            return

        if isinstance(statement, AssignStmt):
            self._emit_expr(statement.value, instructions)
            instructions.append(Instruction("STORE_NAME", statement.name))
            return

        if isinstance(statement, AttributeAssignStmt):
            self._emit_expr(statement.object, instructions)
            self._emit_expr(statement.value, instructions)
            instructions.append(Instruction("STORE_ATTR", statement.attr_name))
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
            self._emit_expr(statement.value, instructions)
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

        if isinstance(statement, ImportStmt):
            instructions.append(Instruction("IMPORT_MODULE", statement.module))
            instructions.append(Instruction("STORE_NAME", statement.alias or statement.module))
            return

        if isinstance(statement, FromImportStmt):
            instructions.append(Instruction("IMPORT_FROM", (statement.module, statement.name)))
            instructions.append(Instruction("STORE_NAME", statement.alias or statement.name))
            return

        if isinstance(statement, ExprStmt):
            self._emit_expr(statement.expr, instructions)
            instructions.append(Instruction("POP_TOP"))
            return

        if isinstance(statement, IfStmt):
            else_label = self._new_label("if_else")
            end_label = self._new_label("if_end")
            self._emit_expr(statement.condition, instructions)
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
            self._emit_expr(statement.condition, instructions)
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
            self._emit_expr(statement.iterator, instructions)
            instructions.append(Instruction("GET_ITER"))
            instructions.append(Instruction("LABEL", start_label))
            instructions.append(Instruction("FOR_ITER", false_target))
            instructions.append(Instruction("STORE_NAME", statement.target))
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
                self._emit_expr(statement.value, instructions)
            instructions.append(Instruction("RETURN_VALUE"))

    def _emit_expr(self, expr, instructions: list[Instruction]) -> None:
        if isinstance(expr, ConstantExpr):
            instructions.append(Instruction("LOAD_CONST", expr.value))
            return

        if isinstance(expr, NameExpr):
            instructions.append(Instruction("LOAD_NAME", expr.name))
            return

        if isinstance(expr, BinaryExpr):
            self._emit_expr(expr.left, instructions)
            self._emit_expr(expr.right, instructions)
            instructions.append(Instruction("BINARY_OP", expr.op))
            return

        if isinstance(expr, CompareExpr):
            self._emit_expr(expr.left, instructions)
            self._emit_expr(expr.right, instructions)
            instructions.append(Instruction("COMPARE_OP", expr.op))
            return

        if isinstance(expr, UnaryExpr):
            self._emit_expr(expr.operand, instructions)
            instructions.append(Instruction("UNARY_OP", expr.op))
            return

        if isinstance(expr, BoolOpExpr):
            end_label = self._new_label("bool_end")
            short_label = self._new_label("bool_short")
            self._emit_expr(expr.left, instructions)
            if expr.op == "and":
                instructions.append(Instruction("JUMP_IF_FALSE", short_label))
                self._emit_expr(expr.right, instructions)
                instructions.append(Instruction("TO_BOOL"))
                instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", short_label))
                instructions.append(Instruction("LOAD_CONST", False))
            else:
                instructions.append(Instruction("JUMP_IF_TRUE", short_label))
                self._emit_expr(expr.right, instructions)
                instructions.append(Instruction("TO_BOOL"))
                instructions.append(Instruction("JUMP", end_label))
                instructions.append(Instruction("LABEL", short_label))
                instructions.append(Instruction("LOAD_CONST", True))
            instructions.append(Instruction("LABEL", end_label))
            return

        if isinstance(expr, CallExpr):
            for arg in expr.args:
                self._emit_expr(arg, instructions)
            if expr.kwargs:
                for value in expr.kwargs.values():
                    self._emit_expr(value, instructions)
                instructions.append(Instruction("CALL_FUNCTION_KW", (expr.func_name, len(expr.args), list(expr.kwargs.keys()))))
            else:
                instructions.append(Instruction("CALL_FUNCTION", (expr.func_name, len(expr.args))))
            return

        if isinstance(expr, ListExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions)
            instructions.append(Instruction("BUILD_LIST", len(expr.elements)))
            return

        if isinstance(expr, TupleExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions)
            instructions.append(Instruction("BUILD_TUPLE", len(expr.elements)))
            return

        if isinstance(expr, DictExpr):
            for key, value in zip(expr.keys, expr.values):
                self._emit_expr(key, instructions)
                self._emit_expr(value, instructions)
            instructions.append(Instruction("BUILD_MAP", len(expr.keys)))
            return

        if isinstance(expr, SetExpr):
            for element in expr.elements:
                self._emit_expr(element, instructions)
            instructions.append(Instruction("BUILD_SET", len(expr.elements)))
            return

        if isinstance(expr, IndexExpr):
            self._emit_expr(expr.collection, instructions)
            self._emit_expr(expr.index, instructions)
            instructions.append(Instruction("BINARY_SUBSCR"))
            return

        if isinstance(expr, AttributeExpr):
            self._emit_expr(expr.object, instructions)
            instructions.append(Instruction("LOAD_ATTR", expr.attr_name))
            return

        if isinstance(expr, MethodCallExpr):
            self._emit_expr(expr.object, instructions)
            for arg in expr.args:
                self._emit_expr(arg, instructions)
            if expr.kwargs:
                for value in expr.kwargs.values():
                    self._emit_expr(value, instructions)
                instructions.append(Instruction("CALL_METHOD_KW", (expr.method_name, len(expr.args), list(expr.kwargs.keys()))))
            else:
                instructions.append(Instruction("CALL_METHOD", (expr.method_name, len(expr.args))))
            return

        instructions.append(Instruction("LOAD_CONST", None))

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
