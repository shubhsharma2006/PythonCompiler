"""
optimizer.py — AST Optimization Pass
======================================
Constant folding: evaluates expressions with known values at compile time.
Dead code elimination: removes code after return statements.
"""

import operator
from ast_nodes import *

# Map operator strings to Python functions
OPS = {
    '+': operator.add, '-': operator.sub,
    '*': operator.mul, '/': operator.truediv,
    '%': operator.mod,
}

CMP_OPS = {
    '==': operator.eq, '!=': operator.ne,
    '<': operator.lt,  '>': operator.gt,
    '<=': operator.le, '>=': operator.ge,
}


class Optimizer:
    """
    Performs compile-time optimizations on the AST.

    Passes:
      1. Constant folding  — 2 + 3 → 5 at compile time
      2. Dead code removal — statements after 'return' are dropped
    """

    def __init__(self):
        self.folded_count = 0
        self.removed_count = 0

    def optimize(self, node):
        """Optimize the entire AST. Returns the optimized tree."""
        return self._visit(node)

    def _visit(self, node):
        method = f'_visit_{type(node).__name__}'
        return getattr(self, method, lambda n: n)(node)

    def _visit_ProgramNode(self, node):
        node.statements = self._optimize_stmts(node.statements)
        return node

    def _visit_AssignNode(self, node):
        node.value = self._visit(node.value)
        return node

    def _visit_PrintNode(self, node):
        node.expr = self._visit(node.expr)
        return node

    def _visit_BinOpNode(self, node):
        node.left = self._visit(node.left)
        node.right = self._visit(node.right)
        # Constant fold: both sides are numbers
        if isinstance(node.left, NumNode) and isinstance(node.right, NumNode):
            if node.op in OPS:
                if node.op == '/' and node.right.value == 0:
                    return node  # don't fold division by zero
                result = OPS[node.op](node.left.value, node.right.value)
                # Keep as int if both inputs were int and result is whole
                if isinstance(node.left.value, int) and isinstance(node.right.value, int):
                    if node.op != '/':
                        result = int(result)
                self.folded_count += 1
                return NumNode(result)
        return node

    def _visit_CompareNode(self, node):
        node.left = self._visit(node.left)
        node.right = self._visit(node.right)
        if isinstance(node.left, NumNode) and isinstance(node.right, NumNode):
            if node.op in CMP_OPS:
                result = 1 if CMP_OPS[node.op](node.left.value, node.right.value) else 0
                self.folded_count += 1
                return NumNode(result)
        return node

    def _visit_UnaryOpNode(self, node):
        node.operand = self._visit(node.operand)
        if isinstance(node.operand, NumNode) and node.op == '-':
            self.folded_count += 1
            return NumNode(-node.operand.value)
        return node

    def _visit_IfNode(self, node):
        node.condition = self._visit(node.condition)
        node.if_body = self._visit(node.if_body)
        if node.else_body:
            node.else_body = self._visit(node.else_body)
        return node

    def _visit_WhileNode(self, node):
        node.condition = self._visit(node.condition)
        node.body = self._visit(node.body)
        return node

    def _visit_BlockNode(self, node):
        node.statements = self._optimize_stmts(node.statements)
        return node

    def _visit_FuncDefNode(self, node):
        node.body = self._visit(node.body)
        return node

    def _visit_ReturnNode(self, node):
        node.expr = self._visit(node.expr)
        return node

    def _visit_FuncCallNode(self, node):
        node.args = [self._visit(a) for a in node.args]
        return node

    def _visit_NumNode(self, node):
        return node

    def _visit_StringNode(self, node):
        return node

    def _visit_VarNode(self, node):
        return node

    def _optimize_stmts(self, stmts):
        """Optimize a list of statements. Removes dead code after return."""
        result = []
        for stmt in stmts:
            opt = self._visit(stmt)
            result.append(opt)
            if isinstance(opt, ReturnNode):
                # Everything after return is dead code
                removed = len(stmts) - len(result)
                if removed > 0:
                    self.removed_count += removed
                break
        return result
