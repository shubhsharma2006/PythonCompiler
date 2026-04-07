"""
ast_nodes.py — Abstract Syntax Tree Node Definitions (Enhanced)
================================================================
Supports: assignments, arithmetic, comparisons, if/else, while loops,
function definitions, function calls, return, print, strings, unary ops.
"""


class ASTNode:
    """Base class for all AST nodes."""
    pass


class ProgramNode(ASTNode):
    """Root node — contains all top-level statements."""
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        stmts = "\n  ".join(repr(s) for s in self.statements)
        return f"Program(\n  {stmts}\n)"


# ── Statements ──────────────────────────────────────────────────

class AssignNode(ASTNode):
    """Variable assignment:  name = value"""
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return f"Assign({self.name!r}, {self.value!r})"


class PrintNode(ASTNode):
    """print(expression)"""
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"Print({self.expr!r})"


class IfNode(ASTNode):
    """if condition { body } [else { else_body }]"""
    def __init__(self, condition, if_body, else_body=None):
        self.condition = condition
        self.if_body = if_body
        self.else_body = else_body

    def __repr__(self):
        if self.else_body:
            return f"If({self.condition!r}, then={self.if_body!r}, else={self.else_body!r})"
        return f"If({self.condition!r}, then={self.if_body!r})"


class WhileNode(ASTNode):
    """while condition { body }"""
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def __repr__(self):
        return f"While({self.condition!r}, {self.body!r})"


class BlockNode(ASTNode):
    """A braced block of statements: { stmt1; stmt2; ... }"""
    def __init__(self, statements):
        self.statements = statements

    def __repr__(self):
        stmts = ", ".join(repr(s) for s in self.statements)
        return f"Block([{stmts}])"


class FuncDefNode(ASTNode):
    """def name(params) { body }"""
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body

    def __repr__(self):
        return f"FuncDef({self.name!r}, {self.params!r}, {self.body!r})"


class ReturnNode(ASTNode):
    """return expression"""
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return f"Return({self.expr!r})"


# ── Expressions ─────────────────────────────────────────────────

class BinOpNode(ASTNode):
    """Binary arithmetic: left OP right  (+ - * /)"""
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def __repr__(self):
        return f"BinOp({self.op!r}, {self.left!r}, {self.right!r})"


class CompareNode(ASTNode):
    """Comparison: left OP right  (== != < > <= >=)"""
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def __repr__(self):
        return f"Compare({self.op!r}, {self.left!r}, {self.right!r})"


class UnaryOpNode(ASTNode):
    """Unary operation: -expr"""
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"UnaryOp({self.op!r}, {self.operand!r})"


class NumNode(ASTNode):
    """Numeric literal: 42, 3.14"""
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Num({self.value})"


class StringNode(ASTNode):
    """String literal: "hello" """
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"String({self.value!r})"


class VarNode(ASTNode):
    """Variable reference: x"""
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Var({self.name!r})"


class FuncCallNode(ASTNode):
    """Function call: name(arg1, arg2, ...)"""
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def __repr__(self):
        return f"Call({self.name!r}, {self.args!r})"
