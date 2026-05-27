from __future__ import annotations

from dataclasses import dataclass, field

from compiler.core.ast import (
    AssignStmt,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    CompareExpr,
    ConstantExpr,
    ExprStmt,
    ForStmt,
    FunctionDef,
    IfStmt,
    IfExpr,
    IndexExpr,
    IndexAssignStmt,
    NameExpr,
    LambdaExpr,
    ListExpr,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    TryStmt,
    TupleExpr,
    SliceExpr,
    UnaryExpr,
    WhileStmt,
    BreakStmt,
    ContinueStmt,
)
from compiler.core.types import ValueType
from compiler.ir.cfg import (
    Assign,
    BasicBlock,
    BinaryOp,
    BranchTerminator,
    Call,
    CFGFunction,
    CFGModule,
    JumpTerminator,
    LoadConst,
    Print,
    ReturnTerminator,
    UnaryOp,
)
from compiler.ir.ownership import OwnerKind, default_value_info
from compiler.semantic import SemanticModel


@dataclass
class _FinallyContext:
    block_name: str
    normal_target: str
    action_var: str
    return_var: str | None
    action_targets: dict[int, tuple[str, str | None]] = field(default_factory=dict)
    action_codes: dict[tuple[str, str | None], int] = field(default_factory=dict)
    next_action_code: int = 1

    def code_for(self, kind: str, target: str | None = None) -> int:
        key = (kind, target)
        existing = self.action_codes.get(key)
        if existing is not None:
            return existing
        code = self.next_action_code
        self.next_action_code += 1
        self.action_codes[key] = code
        self.action_targets[code] = key
        return code


class CFGLowering:
    def __init__(self, semantic: SemanticModel):
        self.semantic = semantic
        self.temp_counter = 0
        self.block_counter = 0
        self.current_function: CFGFunction | None = None
        self.current_block: BasicBlock | None = None
        self.loop_stack: list[tuple[str, str]] = []
        self.exception_target_stack: list[str] = []
        self.finally_stack: list[_FinallyContext] = []

    def generate(self, program: Program) -> CFGModule:
        main_function = self._new_function("main", [], ValueType.INT)
        self.current_function = main_function
        self.current_block = self._new_block("entry")
        main_function.entry_block = self.current_block.name

        for statement in program.body:
            if isinstance(statement, FunctionDef):
                continue
            self._emit_statement(statement)

        self._ensure_fallthrough_return(main_function)

        functions: list[CFGFunction] = []
        for statement in program.body:
            if not isinstance(statement, FunctionDef):
                continue
            function_type = self.semantic.functions[statement.name]
            function = self._new_function(
                statement.name,
                list(zip(function_type.param_names, function_type.param_types)),
                function_type.return_type,
                locals={name: value for name, value in function_type.local_types.items() if name not in function_type.param_names},
            )
            self.current_function = function
            self.current_block = self._new_block("entry")
            function.entry_block = self.current_block.name
            for child in statement.body:
                self._emit_statement(child)
            self._ensure_fallthrough_return(function)
            functions.append(function)

        captured_globals = set().union(*(function.globals_read for function in functions)) if functions else set()
        main_only_globals = {
            name: value_type
            for name, value_type in self.semantic.globals.items()
            if name not in captured_globals
        }
        main_function.locals.update(main_only_globals)
        module_globals = {
            name: value_type
            for name, value_type in self.semantic.globals.items()
            if name in captured_globals
        }

        return CFGModule(
            globals=module_globals,
            functions=functions,
            main=main_function,
            function_types=self.semantic.functions,
        )

    def _new_function(self, name: str, params, return_type: ValueType, locals: dict[str, ValueType] | None = None) -> CFGFunction:
        function = CFGFunction(name=name, params=params, return_type=return_type, locals=dict(locals or {}))
        for param_name, param_type in params:
            function.ownership[param_name] = default_value_info(param_name, param_type, OwnerKind.BORROWED)
        for local_name, local_type in function.locals.items():
            function.ownership[local_name] = default_value_info(local_name, local_type, OwnerKind.OWNED)
        return function

    def _new_block(self, prefix: str) -> BasicBlock:
        self.block_counter += 1
        block = BasicBlock(name=f"{prefix}_{self.block_counter}")
        self.current_function.blocks.append(block)
        return block

    def _switch_to(self, block: BasicBlock) -> None:
        self.current_block = block

    def _emit(self, instruction) -> None:
        self.current_block.instructions.append(instruction)

    def _terminate(self, terminator) -> None:
        if self.current_block.terminator is not None:
            return
        self.current_block.terminator = terminator
        if isinstance(terminator, JumpTerminator):
            self.current_block.successors.add(terminator.target)
            self._lookup_block(terminator.target).predecessors.add(self.current_block.name)
        elif isinstance(terminator, BranchTerminator):
            for target in (terminator.true_target, terminator.false_target):
                self.current_block.successors.add(target)
                self._lookup_block(target).predecessors.add(self.current_block.name)

    def _lookup_block(self, name: str) -> BasicBlock:
        for block in self.current_function.blocks:
            if block.name == name:
                return block
        raise KeyError(name)

    def _ensure_fallthrough_return(self, function: CFGFunction) -> None:
        if self.current_block is None or self.current_block.terminator is not None:
            return
        if function.name == "main":
            self._terminate(ReturnTerminator("0"))
        elif function.return_type == ValueType.VOID:
            self._terminate(ReturnTerminator(None))
        else:
            self._terminate(ReturnTerminator(self._default_value_name(function.return_type)))

    def _default_value_name(self, value_type: ValueType) -> str:
        temp = self._new_temp(value_type)
        default = 0.0 if value_type == ValueType.FLOAT else ("" if value_type == ValueType.STRING else 0)
        self._emit(LoadConst(temp, default, value_type))
        return temp

    def _emit_statement(self, statement) -> None:
        if self.current_block.terminator is not None:
            self._switch_to(self._new_block("dead"))

        if isinstance(statement, AssignStmt):
            value_name, _ = self._emit_expr(statement.value)
            self._emit(Assign(statement.name, value_name))
            return

        if isinstance(statement, IndexAssignStmt):
            collection_name, collection_type = self._emit_expr(statement.collection)
            index_name, _ = self._emit_expr(statement.index)
            value_name, value_type = self._emit_expr(statement.value)
            if collection_type == ValueType.LIST:
                elem_type = self._index_elem_type(statement.collection)
                if elem_type == ValueType.UNKNOWN:
                    elem_type = value_type
                suffix = self._container_suffix(elem_type)
                exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
                self._emit(
                    Call(
                        None,
                        f"py_list_set_{suffix}",
                        [collection_name, index_name, value_name],
                        ValueType.VOID,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
            return

        if isinstance(statement, PrintStmt):
            for i, value_expr in enumerate(statement.values):
                value_name, value_type = self._emit_expr(value_expr)
                self._emit(Print(value_name, value_type, newline=False))
                if i < len(statement.values) - 1:
                    if statement.sep is not None:
                        sep_name, sep_type = self._emit_expr(statement.sep)
                        self._emit(Print(sep_name, sep_type, newline=False))
                    else:
                        sep_temp = self._new_temp(ValueType.STRING)
                        self._emit(LoadConst(sep_temp, " ", ValueType.STRING))
                        self._emit(Print(sep_temp, ValueType.STRING, newline=False))
            if statement.end is not None:
                end_name, end_type = self._emit_expr(statement.end)
                self._emit(Print(end_name, end_type, newline=False))
            else:
                end_temp = self._new_temp(ValueType.STRING)
                self._emit(LoadConst(end_temp, "\n", ValueType.STRING))
                self._emit(Print(end_temp, ValueType.STRING, newline=False))
            return

        if isinstance(statement, ExprStmt):
            self._emit_expr(statement.expr, discard_result=True)
            return

        if isinstance(statement, IfStmt):
            condition_name, _ = self._emit_expr(statement.condition)
            then_block = self._new_block("then")
            merge_block = self._new_block("merge")
            else_block = self._new_block("else") if statement.orelse else merge_block
            self._terminate(BranchTerminator(condition_name, then_block.name, else_block.name))

            self._switch_to(then_block)
            for child in statement.body:
                self._emit_statement(child)
            if self.current_block.terminator is None:
                self._terminate(JumpTerminator(merge_block.name))

            if statement.orelse:
                self._switch_to(else_block)
                for child in statement.orelse:
                    self._emit_statement(child)
                if self.current_block.terminator is None:
                    self._terminate(JumpTerminator(merge_block.name))

            self._switch_to(merge_block)
            return

        if isinstance(statement, WhileStmt):
            cond_block = self._new_block("while_cond")
            body_block = self._new_block("while_body")
            if statement.orelse:
                orelse_block = self._new_block("while_else")
                exit_block = self._new_block("while_exit")
                false_target = orelse_block.name
                break_target = exit_block.name
            else:
                exit_block = self._new_block("while_exit")
                false_target = exit_block.name
                break_target = exit_block.name
            self._terminate(JumpTerminator(cond_block.name))

            self._switch_to(cond_block)
            condition_name, _ = self._emit_expr(statement.condition)
            self._terminate(BranchTerminator(condition_name, body_block.name, false_target))

            self._switch_to(body_block)
            self.loop_stack.append((cond_block.name, break_target))
            for child in statement.body:
                self._emit_statement(child)
            self.loop_stack.pop()
            if self.current_block.terminator is None:
                self._terminate(JumpTerminator(cond_block.name))

            if statement.orelse:
                self._switch_to(orelse_block)
                for child in statement.orelse:
                    self._emit_statement(child)
                if self.current_block.terminator is None:
                    self._terminate(JumpTerminator(exit_block.name))

            self._switch_to(exit_block)
            return

        if isinstance(statement, ForStmt):
            if not isinstance(statement.iterator, CallExpr) or statement.iterator.func_name != "range":
                return
            range_args = statement.iterator.args
            if len(range_args) == 1:
                start_temp = self._new_temp(ValueType.INT)
                self._emit(LoadConst(start_temp, 0, ValueType.INT))
                stop_name, _ = self._emit_expr(range_args[0])
                step_val = 1
            elif len(range_args) == 2:
                start_temp, _ = self._emit_expr(range_args[0])
                stop_name, _ = self._emit_expr(range_args[1])
                step_val = 1
            else:
                start_temp, _ = self._emit_expr(range_args[0])
                stop_name, _ = self._emit_expr(range_args[1])
                step_val = range_args[2].value if isinstance(range_args[2], ConstantExpr) else 1

            iter_var = statement.target
            if iter_var not in self.current_function.locals:
                self.current_function.locals[iter_var] = ValueType.INT
            self._emit(Assign(iter_var, start_temp))

            cond_block = self._new_block("for_cond")
            body_block = self._new_block("for_body")
            step_block = self._new_block("for_step")
            if statement.orelse:
                orelse_block = self._new_block("for_else")
                exit_block = self._new_block("for_exit")
                false_target = orelse_block.name
                break_target = exit_block.name
            else:
                exit_block = self._new_block("for_exit")
                false_target = exit_block.name
                break_target = exit_block.name
            self._terminate(JumpTerminator(cond_block.name))

            self._switch_to(cond_block)
            cond_temp = self._new_temp(ValueType.BOOL)
            compare_op = ">" if isinstance(step_val, (int, float)) and step_val < 0 else "<"
            self._emit(BinaryOp(cond_temp, compare_op, iter_var, stop_name, ValueType.BOOL))
            self._terminate(BranchTerminator(cond_temp, body_block.name, false_target))

            self._switch_to(body_block)
            self.loop_stack.append((step_block.name, break_target))
            for child in statement.body:
                self._emit_statement(child)
            self.loop_stack.pop()
            if self.current_block.terminator is None:
                self._terminate(JumpTerminator(step_block.name))

            self._switch_to(step_block)
            if len(range_args) == 3:
                step_name, _ = self._emit_expr(range_args[2])
            else:
                step_name = self._new_temp(ValueType.INT)
                self._emit(LoadConst(step_name, 1, ValueType.INT))
            step_result = self._new_temp(ValueType.INT)
            self._emit(BinaryOp(step_result, "+", iter_var, step_name, ValueType.INT))
            self._emit(Assign(iter_var, step_result))
            if self.current_block.terminator is None:
                self._terminate(JumpTerminator(cond_block.name))

            if statement.orelse:
                self._switch_to(orelse_block)
                for child in statement.orelse:
                    self._emit_statement(child)
                if self.current_block.terminator is None:
                    self._terminate(JumpTerminator(exit_block.name))

            self._switch_to(exit_block)
            return

        if isinstance(statement, BreakStmt):
            if self.loop_stack:
                self._emit_control_transfer("break", target=self.loop_stack[-1][1])
            return

        if isinstance(statement, ContinueStmt):
            if self.loop_stack:
                self._emit_control_transfer("continue", target=self.loop_stack[-1][0])
            return

        if isinstance(statement, ReturnStmt):
            value_name = None if statement.value is None else self._emit_expr(statement.value)[0]
            self._emit_control_transfer("return", value_name=value_name)
            return

        if isinstance(statement, RaiseStmt):
            error_type = self._new_temp(ValueType.STRING)
            self._emit(LoadConst(error_type, "Exception", ValueType.STRING))
            if statement.value is None:
                error_msg = self._new_temp(ValueType.STRING)
                self._emit(LoadConst(error_msg, "", ValueType.STRING))
            else:
                error_msg, _ = self._emit_expr(statement.value)
            self._emit(Call(None, "py_set_error", [error_type, error_msg], ValueType.VOID))

            if self.exception_target_stack:
                self._terminate(JumpTerminator(self.exception_target_stack[-1]))
            else:
                self._terminate(ReturnTerminator(None))
            return

        if isinstance(statement, TryStmt):
            handler_block = self._new_block("except")
            merge_block = self._new_block("try_merge")
            final_block = self._new_block("try_finally") if statement.finalbody else None
            orelse_block = self._new_block("try_orelse") if statement.orelse else None
            outer_target = self.exception_target_stack[-1] if self.exception_target_stack else None
            final_context = self._make_finally_context(final_block.name, merge_block.name) if final_block is not None else None

            # During the try body, exceptions should dispatch to the handler_block
            if final_context is not None:
                self.finally_stack.append(final_context)
            self.exception_target_stack.append(handler_block.name)
            for child in statement.body:
                self._emit_statement(child)
            # Normal fallthrough: run orelse (if present) then final, otherwise go to final or merge
            if self.current_block.terminator is None:
                if orelse_block is not None:
                    self._terminate(JumpTerminator(orelse_block.name))
                elif final_block is not None:
                    self._emit_normal_finally_jump(final_context)
                else:
                    self._terminate(JumpTerminator(merge_block.name))
            self.exception_target_stack.pop()

            # Emit orelse body which then goes to final (if final exists) or merge
            if orelse_block is not None:
                self._switch_to(orelse_block)
                for child in statement.orelse:
                    self._emit_statement(child)
                if self.current_block.terminator is None:
                    if final_block is not None:
                        self._emit_normal_finally_jump(final_context)
                    else:
                        self._terminate(JumpTerminator(merge_block.name))

            # Dispatch handlers. If a handler matches, run it then go to final (if present) or merge.
            dispatch_block = handler_block
            next_dispatch = None

            for handler in statement.handlers:
                handler_body = self._new_block("except_handler")
                self._switch_to(dispatch_block)

                if handler.type_name is None:
                    self._terminate(JumpTerminator(handler_body.name))
                    next_dispatch = None
                else:
                    type_temp = self._new_temp(ValueType.STRING)
                    self._emit(LoadConst(type_temp, handler.type_name, ValueType.STRING))
                    match_temp = self._new_temp(ValueType.BOOL)
                    self._emit(Call(match_temp, "py_error_matches", [type_temp], ValueType.BOOL))
                    next_dispatch = self._new_block("except_next")
                    self._terminate(BranchTerminator(match_temp, handler_body.name, next_dispatch.name))

                self._switch_to(handler_body)
                if handler.name:
                    if handler.name not in self.current_function.locals:
                        self.current_function.locals[handler.name] = ValueType.STRING
                    msg_temp = self._new_temp(ValueType.STRING)
                    self._emit(Call(msg_temp, "py_error_message", [], ValueType.STRING))
                    self._emit(Assign(handler.name, msg_temp))
                self._emit(Call(None, "py_clear_error", [], ValueType.VOID))
                for child in handler.body:
                    self._emit_statement(child)
                if self.current_block.terminator is None:
                    if final_block is not None:
                        self._emit_normal_finally_jump(final_context)
                    else:
                        self._terminate(JumpTerminator(merge_block.name))

                if next_dispatch is None:
                    dispatch_block = None
                    break
                dispatch_block = next_dispatch

            # If no handler matched, run final (if present) then propagate to outer_target; otherwise re-raise
            if dispatch_block is not None:
                self._switch_to(dispatch_block)
                if self.current_block.terminator is None:
                    if final_block is not None:
                        self._terminate(JumpTerminator(final_block.name))
                    else:
                        if outer_target:
                            self._terminate(JumpTerminator(outer_target))
                        else:
                            self._terminate(ReturnTerminator(None))

            # Emit finalbody: run finalbody, then either propagate active error or continue to merge
            if final_block is not None:
                assert final_context is not None
                self.finally_stack.pop()
                self._switch_to(final_block)
                for child in statement.finalbody:
                    self._emit_statement(child)
                # After finalbody, emit an explicit py_error_occurred check to decide whether to propagate
                if self.current_block.terminator is None:
                    error_check = self._new_temp(ValueType.BOOL)
                    self._emit(Call(error_check, "py_error_occurred", [], ValueType.BOOL))
                    dispatch_block = None
                    success_target = merge_block.name
                    if final_context.action_targets:
                        dispatch_block = self._new_block("finally_dispatch")
                        success_target = dispatch_block.name
                    if outer_target:
                        self._terminate(BranchTerminator(error_check, outer_target, success_target))
                    else:
                        error_block = self._new_block("try_finally_error")
                        self._terminate(BranchTerminator(error_check, error_block.name, success_target))
                        self._switch_to(error_block)
                        self._terminate(ReturnTerminator(None))
                    if dispatch_block is not None:
                        self._switch_to(dispatch_block)
                        self._emit_finally_dispatch(final_context)

            self._switch_to(merge_block)
            return

    def _emit_expr(self, expr, discard_result: bool = False) -> tuple[str, ValueType]:
        if isinstance(expr, IfExpr):
            condition_name, _ = self._emit_expr(expr.condition)
            result_type = self._runtime_type(expr.body)
            result = self._new_temp(result_type)
            
            true_block = self._new_block("ifexpr_true")
            false_block = self._new_block("ifexpr_false")
            merge_block = self._new_block("ifexpr_merge")
            
            self._terminate(BranchTerminator(condition_name, true_block.name, false_block.name))
            
            self._switch_to(true_block)
            body_name, _ = self._emit_expr(expr.body)
            self._emit(Assign(result, body_name))
            self._terminate(JumpTerminator(merge_block.name))
            
            self._switch_to(false_block)
            orelse_name, _ = self._emit_expr(expr.orelse)
            self._emit(Assign(result, orelse_name))
            self._terminate(JumpTerminator(merge_block.name))
            
            self._switch_to(merge_block)
            return result, result_type

        if isinstance(expr, LambdaExpr):
            return "0", ValueType.UNKNOWN

        if isinstance(expr, ConstantExpr):
            value_type = self._runtime_type(expr)
            temp = self._new_temp(value_type)
            self._emit(LoadConst(temp, expr.value, value_type))
            return temp, value_type

        if isinstance(expr, NameExpr):
            if expr.name in self.semantic.globals and self.current_function.name != "main":
                self.current_function.globals_read.add(expr.name)
            return expr.name, self._runtime_type(expr)

        if isinstance(expr, UnaryExpr):
            operand_name, _ = self._emit_expr(expr.operand)
            value_type = self._runtime_type(expr)
            temp = self._new_temp(value_type)
            op = "!" if expr.op == "not" else expr.op
            self._emit(UnaryOp(temp, op, operand_name, value_type))
            return temp, value_type

        if isinstance(expr, BinaryExpr):
            left_name, _ = self._emit_expr(expr.left)
            right_name, _ = self._emit_expr(expr.right)
            value_type = self._runtime_type(expr)
            temp = self._new_temp(value_type)
            self._emit(BinaryOp(temp, expr.op, left_name, right_name, value_type))
            return temp, value_type

        if isinstance(expr, ListExpr):
            element_names: list[str] = []
            element_types: list[ValueType] = []
            for element in expr.elements:
                name, elem_type = self._emit_expr(element)
                element_names.append(name)
                element_types.append(elem_type)
            elem_type = element_types[0] if element_types else ValueType.INT
            suffix = self._container_suffix(elem_type)
            size_temp = self._new_temp(ValueType.INT)
            self._emit(LoadConst(size_temp, len(element_names), ValueType.INT))
            target = self._new_temp(ValueType.LIST)
            exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
            self._emit(
                Call(
                    target,
                    f"py_list_new_{suffix}",
                    [size_temp],
                    ValueType.LIST,
                    can_raise=True,
                    exception_target=exception_target,
                )
            )
            for index, element_name in enumerate(element_names):
                index_temp = self._new_temp(ValueType.INT)
                self._emit(LoadConst(index_temp, index, ValueType.INT))
                self._emit(
                    Call(
                        None,
                        f"py_list_set_{suffix}",
                        [target, index_temp, element_name],
                        ValueType.VOID,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
            return target, ValueType.LIST

        if isinstance(expr, TupleExpr):
            element_names: list[str] = []
            element_types: list[ValueType] = []
            for element in expr.elements:
                name, elem_type = self._emit_expr(element)
                element_names.append(name)
                element_types.append(elem_type)
            elem_type = element_types[0] if element_types else ValueType.INT
            suffix = self._container_suffix(elem_type)
            size_temp = self._new_temp(ValueType.INT)
            self._emit(LoadConst(size_temp, len(element_names), ValueType.INT))
            target = self._new_temp(ValueType.TUPLE)
            exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
            self._emit(
                Call(
                    target,
                    f"py_tuple_new_{suffix}",
                    [size_temp],
                    ValueType.TUPLE,
                    can_raise=True,
                    exception_target=exception_target,
                )
            )
            for index, element_name in enumerate(element_names):
                index_temp = self._new_temp(ValueType.INT)
                self._emit(LoadConst(index_temp, index, ValueType.INT))
                self._emit(
                    Call(
                        None,
                        f"py_tuple_set_{suffix}",
                        [target, index_temp, element_name],
                        ValueType.VOID,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
            return target, ValueType.TUPLE

        if isinstance(expr, CompareExpr):
            left_name, _ = self._emit_expr(expr.left)
            right_name, _ = self._emit_expr(expr.right)
            temp = self._new_temp(ValueType.BOOL)
            self._emit(BinaryOp(temp, expr.op, left_name, right_name, ValueType.BOOL))
            return temp, ValueType.BOOL

        if isinstance(expr, BoolOpExpr):
            return self._emit_short_circuit(expr)

        if isinstance(expr, IndexExpr):
            collection_name, collection_type = self._emit_expr(expr.collection)
            exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
            if isinstance(expr.index, SliceExpr) and collection_type == ValueType.STRING:
                start_name, has_start = self._emit_slice_part(expr.index.lower)
                end_name, has_end = self._emit_slice_part(expr.index.upper)
                has_start_name = self._new_temp(ValueType.INT)
                has_end_name = self._new_temp(ValueType.INT)
                self._emit(LoadConst(has_start_name, has_start, ValueType.INT))
                self._emit(LoadConst(has_end_name, has_end, ValueType.INT))
                target = self._new_temp(ValueType.STRING)
                self._emit(
                    Call(
                        target,
                        "py_str_slice",
                        [collection_name, start_name, end_name, has_start_name, has_end_name],
                        ValueType.STRING,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
                return target, ValueType.STRING
            index_name, _ = self._emit_expr(expr.index)
            if collection_type == ValueType.LIST:
                elem_type = self._index_elem_type(expr.collection)
                suffix = self._container_suffix(elem_type)
                target = self._new_temp(elem_type)
                self._emit(
                    Call(
                        target,
                        f"py_list_get_{suffix}",
                        [collection_name, index_name],
                        elem_type,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
                return target, elem_type
            if collection_type == ValueType.TUPLE:
                elem_type = self._index_elem_type(expr.collection)
                suffix = self._container_suffix(elem_type)
                target = self._new_temp(elem_type)
                self._emit(
                    Call(
                        target,
                        f"py_tuple_get_{suffix}",
                        [collection_name, index_name],
                        elem_type,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
                return target, elem_type
            if collection_type == ValueType.STRING:
                target = self._new_temp(ValueType.STRING)
                self._emit(
                    Call(
                        target,
                        "py_str_get_index",
                        [collection_name, index_name],
                        ValueType.STRING,
                        can_raise=True,
                        exception_target=exception_target,
                    )
                )
                return target, ValueType.STRING
            return "0", ValueType.UNKNOWN

        if isinstance(expr, CallExpr):
            if expr.func_name == "len" and expr.args:
                arg_name, arg_type = self._emit_expr(expr.args[0])
                target = None if discard_result else self._new_temp(ValueType.INT)
                exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
                if arg_type == ValueType.LIST:
                    func_name = "py_list_len"
                elif arg_type == ValueType.TUPLE:
                    func_name = "py_tuple_len"
                else:
                    func_name = "py_len_str"
                self._emit(Call(target, func_name, [arg_name], ValueType.INT, can_raise=False, exception_target=exception_target))
                return target or "0", ValueType.INT

            args = [self._emit_expr(arg)[0] for arg in expr.args]
            value_type = self._runtime_type(expr)
            target = None if discard_result or value_type == ValueType.VOID else self._new_temp(value_type)
            exception_target = self.exception_target_stack[-1] if self.exception_target_stack else "cleanup"
            self._emit(Call(target, expr.func_name, args, value_type, can_raise=True, exception_target=exception_target))
            return target or "0", value_type

        return "0", ValueType.INT

    def _emit_short_circuit(self, expr: BoolOpExpr) -> tuple[str, ValueType]:
        result = self._new_temp(ValueType.BOOL)
        left_name, _ = self._emit_expr(expr.left)
        rhs_block = self._new_block(f"{expr.op}_rhs")
        shortcut_block = self._new_block(f"{expr.op}_shortcut")
        end_block = self._new_block(f"{expr.op}_end")

        if expr.op == "and":
            self._terminate(BranchTerminator(left_name, rhs_block.name, shortcut_block.name))
            self._switch_to(shortcut_block)
            self._emit(LoadConst(result, False, ValueType.BOOL))
            self._terminate(JumpTerminator(end_block.name))
        else:
            self._terminate(BranchTerminator(left_name, shortcut_block.name, rhs_block.name))
            self._switch_to(shortcut_block)
            self._emit(LoadConst(result, True, ValueType.BOOL))
            self._terminate(JumpTerminator(end_block.name))

        self._switch_to(rhs_block)
        right_name, _ = self._emit_expr(expr.right)
        self._emit(Assign(result, right_name))
        self._terminate(JumpTerminator(end_block.name))

        self._switch_to(end_block)
        return result, ValueType.BOOL

    def _new_temp(self, value_type: ValueType) -> str:
        self.temp_counter += 1
        name = f"_t{self.temp_counter}"
        self.current_function.locals[name] = value_type
        return name

    def _make_finally_context(self, block_name: str, normal_target: str) -> _FinallyContext:
        action_var = self._new_temp(ValueType.INT)
        return_var = None
        if self.current_function.return_type != ValueType.VOID:
            return_var = self._new_temp(self.current_function.return_type)
        return _FinallyContext(
            block_name=block_name,
            normal_target=normal_target,
            action_var=action_var,
            return_var=return_var,
        )

    def _emit_assign_const(self, target: str, value: object, value_type: ValueType) -> None:
        temp = self._new_temp(value_type)
        self._emit(LoadConst(temp, value, value_type))
        self._emit(Assign(target, temp))

    def _emit_normal_finally_jump(self, context: _FinallyContext | None) -> None:
        if context is None:
            return
        self._emit_assign_const(context.action_var, 0, ValueType.INT)
        self._terminate(JumpTerminator(context.block_name))

    def _emit_control_transfer(
        self,
        kind: str,
        *,
        target: str | None = None,
        value_name: str | None = None,
    ) -> None:
        if self.finally_stack:
            context = self.finally_stack[-1]
            code = context.code_for(kind, target)
            self._emit_assign_const(context.action_var, code, ValueType.INT)
            if kind == "return" and context.return_var is not None and value_name is not None:
                self._emit(Assign(context.return_var, value_name))
            self._terminate(JumpTerminator(context.block_name))
            return

        if kind in {"break", "continue"}:
            assert target is not None
            self._terminate(JumpTerminator(target))
            return

        self._terminate(ReturnTerminator(value_name))

    def _emit_finally_dispatch(self, context: _FinallyContext) -> None:
        actions = sorted(context.action_targets.items())
        if not actions:
            self._terminate(JumpTerminator(context.normal_target))
            return

        for index, (code, (kind, target)) in enumerate(actions):
            action_block = self._new_block("finally_action")
            next_check = self._new_block("finally_dispatch_next") if index < len(actions) - 1 else None
            code_temp = self._new_temp(ValueType.INT)
            self._emit(LoadConst(code_temp, code, ValueType.INT))
            match_temp = self._new_temp(ValueType.BOOL)
            self._emit(BinaryOp(match_temp, "==", context.action_var, code_temp, ValueType.BOOL))
            false_target = next_check.name if next_check is not None else context.normal_target
            self._terminate(BranchTerminator(match_temp, action_block.name, false_target))

            self._switch_to(action_block)
            if kind == "return":
                self._emit_control_transfer("return", value_name=context.return_var)
            else:
                self._emit_control_transfer(kind, target=target)

            if next_check is None:
                return
            self._switch_to(next_check)

    def _runtime_type(self, expr) -> ValueType:
        if isinstance(expr, NameExpr):
            for name, value_type in self.current_function.params:
                if name == expr.name:
                    return value_type
            if expr.name in self.current_function.locals:
                return self.current_function.locals[expr.name]
            if expr.name in self.semantic.globals:
                return self.semantic.globals[expr.name]
            return self.semantic.expr_type(expr)

        if isinstance(expr, ConstantExpr):
            return self.semantic.expr_type(expr)

        if isinstance(expr, UnaryExpr):
            if expr.op == "not":
                return ValueType.BOOL
            return self._runtime_type(expr.operand)

        if isinstance(expr, BinaryExpr):
            if expr.op == "/":
                return ValueType.FLOAT
            left_type = self._runtime_type(expr.left)
            right_type = self._runtime_type(expr.right)
            if ValueType.FLOAT in (left_type, right_type):
                return ValueType.FLOAT
            return self.semantic.expr_type(expr)

        if isinstance(expr, CompareExpr):
            return ValueType.BOOL

        if isinstance(expr, BoolOpExpr):
            return ValueType.BOOL

        if isinstance(expr, CallExpr) and expr.func_name in self.semantic.functions:
            return self.semantic.functions[expr.func_name].return_type

        return self.semantic.expr_type(expr)

    @staticmethod
    def _container_suffix(value_type: ValueType) -> str:
        if value_type == ValueType.FLOAT:
            return "float"
        if value_type == ValueType.BOOL:
            return "bool"
        if value_type == ValueType.STRING:
            return "str"
        return "int"

    def _index_elem_type(self, collection_expr) -> ValueType:
        if isinstance(collection_expr, NameExpr):
            return self.semantic.container_var_elem_types.get(collection_expr.name, ValueType.UNKNOWN)
        return self.semantic.container_elem_types.get(id(collection_expr), ValueType.UNKNOWN)

    def _emit_slice_part(self, expr) -> tuple[str, int]:
        if expr is None:
            temp = self._new_temp(ValueType.INT)
            self._emit(LoadConst(temp, 0, ValueType.INT))
            return temp, 0
        name, _ = self._emit_expr(expr)
        return name, 1
