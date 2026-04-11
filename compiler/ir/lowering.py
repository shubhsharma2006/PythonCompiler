from __future__ import annotations

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
    NameExpr,
    PrintStmt,
    Program,
    ReturnStmt,
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
from compiler.semantic import SemanticModel


class CFGLowering:
    def __init__(self, semantic: SemanticModel):
        self.semantic = semantic
        self.temp_counter = 0
        self.block_counter = 0
        self.current_function: CFGFunction | None = None
        self.current_block: BasicBlock | None = None
        self.loop_stack: list[tuple[str, str]] = []

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
        return CFGFunction(name=name, params=params, return_type=return_type, locals=dict(locals or {}))

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
            self.loop_stack.append((cond_block.name, break_target))
            for child in statement.body:
                self._emit_statement(child)
            self.loop_stack.pop()

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
                self._terminate(JumpTerminator(self.loop_stack[-1][1]))
            return

        if isinstance(statement, ContinueStmt):
            if self.loop_stack:
                self._terminate(JumpTerminator(self.loop_stack[-1][0]))
            return

        if isinstance(statement, ReturnStmt):
            value_name = None if statement.value is None else self._emit_expr(statement.value)[0]
            self._terminate(ReturnTerminator(value_name))

    def _emit_expr(self, expr, discard_result: bool = False) -> tuple[str, ValueType]:
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

        if isinstance(expr, CompareExpr):
            left_name, _ = self._emit_expr(expr.left)
            right_name, _ = self._emit_expr(expr.right)
            temp = self._new_temp(ValueType.BOOL)
            self._emit(BinaryOp(temp, expr.op, left_name, right_name, ValueType.BOOL))
            return temp, ValueType.BOOL

        if isinstance(expr, BoolOpExpr):
            return self._emit_short_circuit(expr)

        if isinstance(expr, CallExpr):
            args = [self._emit_expr(arg)[0] for arg in expr.args]
            value_type = self._runtime_type(expr)
            target = None if discard_result or value_type == ValueType.VOID else self._new_temp(value_type)
            self._emit(Call(target, expr.func_name, args, value_type))
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
