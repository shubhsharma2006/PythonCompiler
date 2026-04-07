"""
visitor.py — Base Visitor pattern for AST traversal.
All analysis/transform passes inherit from this.
"""


class ASTVisitor:
    """
    Base visitor class implementing the Visitor Pattern.
    Subclasses override visit_<ClassName> methods for each AST node type.
    """

    def visit(self, node):
        """Dispatch to the correct visit_* method based on node class name."""
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Called when no specific visitor exists. Override for custom fallback."""
        raise NotImplementedError(
            f"{self.__class__.__name__} has no visit_{type(node).__name__} method"
        )


class ASTTransformer(ASTVisitor):
    """
    A visitor that returns transformed nodes.
    Used for optimization passes that modify the AST.
    """

    def visit_children(self, node):
        """Visit all child nodes listed in node.children (if defined)."""
        for attr in getattr(node, '_child_attrs', []):
            child = getattr(node, attr)
            if isinstance(child, list):
                setattr(node, attr, [self.visit(c) for c in child])
            elif child is not None:
                setattr(node, attr, self.visit(child))
        return node
