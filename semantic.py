"""
semantic.py — Semantic Analyser (Enhanced)
===========================================
Scoped symbol table, function signature tracking, undefined variable
and function checks, parameter count validation.
"""

from ast_nodes import *


class SemanticError(Exception):
    pass


class SymbolTable:
    """Stack-based scoped symbol table."""

    def __init__(self):
        self._scopes = [set()]  # start with global scope
        self.functions = {}     # name → param_count

    def enter_scope(self):
        self._scopes.append(set())

    def exit_scope(self):
        self._scopes.pop()

    def define(self, name):
        self._scopes[-1].add(name)

    def is_defined(self, name):
        for scope in reversed(self._scopes):
            if name in scope:
                return True
        return False

    def define_function(self, name, param_count):
        self.functions[name] = param_count

    def all_defined(self):
        """Return all variable names across all scopes."""
        result = set()
        for scope in self._scopes:
            result |= scope
        return result


class SemanticAnalyser:
    """Walks the AST and validates semantics."""

    def __init__(self):
        self.symbols = SymbolTable()
        self.defined_vars = set()  # for backward compat with main.py
        self.warnings = []

    def analyse(self, node):
        self._visit(node)
        self.defined_vars = self.symbols.all_defined()

    def _visit(self, node):
        method = f'_visit_{type(node).__name__}'
        visitor = getattr(self, method, self._generic_visit)
        visitor(node)

    def _visit_ProgramNode(self, node):
        for stmt in node.statements:
            self._visit(stmt)

    def _visit_AssignNode(self, node):
        self._visit(node.value)
        self.symbols.define(node.name)

    def _visit_BinOpNode(self, node):
        self._visit(node.left)
        self._visit(node.right)

    def _visit_CompareNode(self, node):
        self._visit(node.left)
        self._visit(node.right)

    def _visit_UnaryOpNode(self, node):
        self._visit(node.operand)

    def _visit_NumNode(self, _):
        pass

    def _visit_StringNode(self, _):
        pass

    def _visit_VarNode(self, node):
        if not self.symbols.is_defined(node.name):
            raise SemanticError(f"Undefined variable {node.name!r}")

    def _visit_PrintNode(self, node):
        self._visit(node.expr)

    def _visit_IfNode(self, node):
        self._visit(node.condition)
        self._visit(node.if_body)
        if node.else_body:
            self._visit(node.else_body)

    def _visit_WhileNode(self, node):
        self._visit(node.condition)
        self._visit(node.body)

    def _visit_BlockNode(self, node):
        self.symbols.enter_scope()
        for stmt in node.statements:
            self._visit(stmt)
        self.symbols.exit_scope()

    def _visit_FuncDefNode(self, node):
        self.symbols.define_function(node.name, len(node.params))
        self.symbols.define(node.name)
        self.symbols.enter_scope()
        for p in node.params:
            self.symbols.define(p)
        self._visit(node.body)
        self.symbols.exit_scope()

    def _visit_ReturnNode(self, node):
        self._visit(node.expr)

    def _visit_FuncCallNode(self, node):
        if node.name not in self.symbols.functions:
            if not self.symbols.is_defined(node.name):
                raise SemanticError(f"Undefined function {node.name!r}")
        else:
            expected = self.symbols.functions[node.name]
            if len(node.args) != expected:
                raise SemanticError(
                    f"Function {node.name!r} expects {expected} args, "
                    f"got {len(node.args)}"
                )
        for arg in node.args:
            self._visit(arg)

    def _generic_visit(self, node):
        raise NotImplementedError(f"No visitor for {type(node).__name__}")
