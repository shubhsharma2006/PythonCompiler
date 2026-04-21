from __future__ import annotations

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    CompareExpr,
    ConstantExpr,
    DeleteStmt,
    ExprStmt,
    ClassDef,
    FunctionDef,
    ForStmt,
    GlobalStmt,
    IfStmt,
    IfExpr,
    IndexExpr,
    DictExpr,
    LambdaExpr,
    ListExpr,
    MethodCallExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    ReturnStmt,
    SetExpr,
    SliceExpr,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    WhileStmt,
    WithStmt,
)


class ConstantFolder:
    def optimize(self, program: Program) -> Program:
        program.body = self._optimize_statements(program.body)
        return program

    def _optimize_statements(self, statements):
        optimized = []
        for statement in statements:
            optimized.append(self._optimize_statement(statement))
            if isinstance(optimized[-1], ReturnStmt):
                break
        return optimized

    def _optimize_statement(self, statement):
        if isinstance(statement, AssignStmt):
            statement.value = self._optimize_expr(statement.value)
        elif isinstance(statement, UnpackAssignStmt):
            statement.value = self._optimize_expr(statement.value)
        elif isinstance(statement, AttributeAssignStmt):
            statement.object = self._optimize_expr(statement.object)
            statement.value = self._optimize_expr(statement.value)
        elif isinstance(statement, DeleteStmt):
            statement.targets = [self._optimize_expr(target) for target in statement.targets]
        elif isinstance(statement, (PassStmt, GlobalStmt, NonlocalStmt)):
            return statement
        elif isinstance(statement, PrintStmt):
            statement.values = [self._optimize_expr(value) for value in statement.values]
            if statement.sep is not None:
                statement.sep = self._optimize_expr(statement.sep)
            if statement.end is not None:
                statement.end = self._optimize_expr(statement.end)
        elif isinstance(statement, ExprStmt):
            statement.expr = self._optimize_expr(statement.expr)
        elif isinstance(statement, IfStmt):
            statement.condition = self._optimize_expr(statement.condition)
            statement.body = self._optimize_statements(statement.body)
            statement.orelse = self._optimize_statements(statement.orelse)
        elif isinstance(statement, WhileStmt):
            statement.condition = self._optimize_expr(statement.condition)
            statement.body = self._optimize_statements(statement.body)
            statement.orelse = self._optimize_statements(statement.orelse)
        elif isinstance(statement, ForStmt):
            statement.iterator = self._optimize_expr(statement.iterator)
            statement.body = self._optimize_statements(statement.body)
            statement.orelse = self._optimize_statements(statement.orelse)
        elif isinstance(statement, WithStmt):
            statement.context_expr = self._optimize_expr(statement.context_expr)
            statement.body = self._optimize_statements(statement.body)
        elif isinstance(statement, FunctionDef):
            statement.defaults = [self._optimize_expr(default) for default in statement.defaults]
            statement.body = self._optimize_statements(statement.body)
        elif isinstance(statement, ClassDef):
            for method in statement.methods:
                method.defaults = [self._optimize_expr(default) for default in method.defaults]
                method.body = self._optimize_statements(method.body)
        elif isinstance(statement, ReturnStmt) and statement.value is not None:
            statement.value = self._optimize_expr(statement.value)
        return statement

    def _optimize_expr(self, expr):
        if isinstance(expr, BinaryExpr):
            expr.left = self._optimize_expr(expr.left)
            expr.right = self._optimize_expr(expr.right)
            if isinstance(expr.left, ConstantExpr) and isinstance(expr.right, ConstantExpr):
                if expr.op == "+" and isinstance(expr.left.value, str) and isinstance(expr.right.value, str):
                    return ConstantExpr(span=expr.span, value=expr.left.value + expr.right.value)
                if isinstance(expr.left.value, (int, float)) and isinstance(expr.right.value, (int, float)):
                    if expr.op == "+":
                        return ConstantExpr(span=expr.span, value=expr.left.value + expr.right.value)
                    if expr.op == "-":
                        return ConstantExpr(span=expr.span, value=expr.left.value - expr.right.value)
                    if expr.op == "*":
                        return ConstantExpr(span=expr.span, value=expr.left.value * expr.right.value)
                    if expr.op == "/" and expr.right.value != 0:
                        return ConstantExpr(span=expr.span, value=expr.left.value / expr.right.value)
                    if expr.op == "%" and expr.right.value != 0:
                        return ConstantExpr(span=expr.span, value=expr.left.value % expr.right.value)
            return expr

        if isinstance(expr, UnaryExpr):
            expr.operand = self._optimize_expr(expr.operand)
            if isinstance(expr.operand, ConstantExpr):
                if expr.op == "-" and isinstance(expr.operand.value, (int, float)):
                    return ConstantExpr(span=expr.span, value=-expr.operand.value)
                if expr.op == "not":
                    return ConstantExpr(span=expr.span, value=not bool(expr.operand.value))
            return expr

        if isinstance(expr, CompareExpr):
            expr.left = self._optimize_expr(expr.left)
            expr.right = self._optimize_expr(expr.right)
            if isinstance(expr.left, ConstantExpr) and isinstance(expr.right, ConstantExpr):
                try:
                    mapping = {
                        "==": expr.left.value == expr.right.value,
                        "!=": expr.left.value != expr.right.value,
                        "<": expr.left.value < expr.right.value,
                        "<=": expr.left.value <= expr.right.value,
                        ">": expr.left.value > expr.right.value,
                        ">=": expr.left.value >= expr.right.value,
                        "in": expr.left.value in expr.right.value,
                        "not in": expr.left.value not in expr.right.value,
                        "is": expr.left.value is expr.right.value,
                        "is not": expr.left.value is not expr.right.value,
                    }
                except Exception:
                    return expr
                return ConstantExpr(span=expr.span, value=mapping[expr.op])
            return expr

        if isinstance(expr, BoolOpExpr):
            expr.left = self._optimize_expr(expr.left)
            expr.right = self._optimize_expr(expr.right)
            if isinstance(expr.left, ConstantExpr) and isinstance(expr.right, ConstantExpr):
                left = bool(expr.left.value)
                if expr.op == "and":
                    return ConstantExpr(span=expr.span, value=left and bool(expr.right.value))
                return ConstantExpr(span=expr.span, value=left or bool(expr.right.value))
            return expr

        if isinstance(expr, ListExpr):
            expr.elements = [self._optimize_expr(element) for element in expr.elements]
            return expr

        if isinstance(expr, TupleExpr):
            expr.elements = [self._optimize_expr(element) for element in expr.elements]
            return expr

        if isinstance(expr, DictExpr):
            expr.keys = [self._optimize_expr(key) for key in expr.keys]
            expr.values = [self._optimize_expr(value) for value in expr.values]
            return expr

        if isinstance(expr, SetExpr):
            expr.elements = [self._optimize_expr(element) for element in expr.elements]
            return expr

        if isinstance(expr, IfExpr):
            expr.condition = self._optimize_expr(expr.condition)
            expr.body = self._optimize_expr(expr.body)
            expr.orelse = self._optimize_expr(expr.orelse)
            if isinstance(expr.condition, ConstantExpr):
                return expr.body if bool(expr.condition.value) else expr.orelse
            return expr

        if isinstance(expr, LambdaExpr):
            expr.func_def.body = self._optimize_statements(expr.func_def.body)
            return expr

        if isinstance(expr, IndexExpr):
            expr.collection = self._optimize_expr(expr.collection)
            expr.index = self._optimize_expr(expr.index)
            return expr

        if isinstance(expr, SliceExpr):
            if expr.lower is not None:
                expr.lower = self._optimize_expr(expr.lower)
            if expr.upper is not None:
                expr.upper = self._optimize_expr(expr.upper)
            if expr.step is not None:
                expr.step = self._optimize_expr(expr.step)
            return expr

        if isinstance(expr, AttributeExpr):
            expr.object = self._optimize_expr(expr.object)
            return expr

        if isinstance(expr, MethodCallExpr):
            expr.object = self._optimize_expr(expr.object)
            expr.args = [self._optimize_expr(arg) for arg in expr.args]
            expr.kwargs = {name: self._optimize_expr(arg) for name, arg in expr.kwargs.items()}
            return expr

        if isinstance(expr, CallExpr):
            expr.args = [self._optimize_expr(arg) for arg in expr.args]
            expr.kwargs = {name: self._optimize_expr(arg) for name, arg in expr.kwargs.items()}
            return expr

        return expr
