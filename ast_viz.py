"""
ast_viz.py — AST Visualisation with Graphviz (Enhanced)
========================================================
Colour-coded diagram of the full AST including control flow nodes.
"""

try:
    import graphviz
    HAS_GRAPHVIZ = True
except ImportError:
    HAS_GRAPHVIZ = False

from ast_nodes import *

# Node styles: type → graphviz attributes
_STYLES = {
    ProgramNode:  dict(shape='doubleoctagon', style='filled', fillcolor='#2c3e50', fontcolor='white'),
    AssignNode:   dict(shape='box',           style='filled', fillcolor='#16a085', fontcolor='white'),
    PrintNode:    dict(shape='box',           style='filled', fillcolor='#8e44ad', fontcolor='white'),
    IfNode:       dict(shape='diamond',       style='filled', fillcolor='#e74c3c', fontcolor='white'),
    WhileNode:    dict(shape='diamond',       style='filled', fillcolor='#e67e22', fontcolor='white'),
    FuncDefNode:  dict(shape='box3d',         style='filled', fillcolor='#2980b9', fontcolor='white'),
    ReturnNode:   dict(shape='box',           style='filled', fillcolor='#1abc9c', fontcolor='white'),
    BlockNode:    dict(shape='record',        style='filled', fillcolor='#34495e', fontcolor='white'),
    BinOpNode:    dict(shape='ellipse',       style='filled', fillcolor='#e67e22', fontcolor='white'),
    CompareNode:  dict(shape='ellipse',       style='filled', fillcolor='#c0392b', fontcolor='white'),
    UnaryOpNode:  dict(shape='ellipse',       style='filled', fillcolor='#d35400', fontcolor='white'),
    FuncCallNode: dict(shape='box',           style='filled,rounded', fillcolor='#9b59b6', fontcolor='white'),
    NumNode:      dict(shape='circle',        style='filled', fillcolor='#27ae60', fontcolor='white'),
    StringNode:   dict(shape='note',          style='filled', fillcolor='#f39c12', fontcolor='black'),
    VarNode:      dict(shape='circle',        style='filled', fillcolor='#f1c40f', fontcolor='black'),
}


class ASTVisualiser:
    def __init__(self):
        self._counter = 0

    def _id(self):
        self._counter += 1
        return f'n{self._counter}'

    def build(self, root):
        if not HAS_GRAPHVIZ:
            return None
        dot = graphviz.Digraph(
            'AST',
            graph_attr={'rankdir': 'TB', 'bgcolor': '#1a1a2e', 'fontname': 'Helvetica'},
            node_attr={'fontname': 'Helvetica', 'fontsize': '11'},
            edge_attr={'color': '#95a5a6', 'arrowsize': '0.7'},
        )
        self._visit(root, dot, None)
        return dot

    def _node(self, dot, label, obj):
        nid = self._id()
        dot.node(nid, label=label, **_STYLES.get(type(obj), {}))
        return nid

    def _visit(self, node, dot, pid, elabel=''):
        method = f'_v_{type(node).__name__}'
        getattr(self, method, self._v_unknown)(node, dot, pid, elabel)

    def _edge(self, dot, pid, cid, label=''):
        if pid:
            dot.edge(pid, cid, label=label)

    # ── Visitors ──
    def _v_ProgramNode(self, n, d, pid, el):
        nid = self._node(d, 'Program', n); self._edge(d, pid, nid, el)
        for i, s in enumerate(n.statements):
            self._visit(s, d, nid, f's{i+1}')

    def _v_AssignNode(self, n, d, pid, el):
        nid = self._node(d, f'Assign\\n{n.name!r}', n); self._edge(d, pid, nid, el)
        self._visit(n.value, d, nid, 'val')

    def _v_PrintNode(self, n, d, pid, el):
        nid = self._node(d, 'Print', n); self._edge(d, pid, nid, el)
        self._visit(n.expr, d, nid, 'expr')

    def _v_IfNode(self, n, d, pid, el):
        nid = self._node(d, 'If', n); self._edge(d, pid, nid, el)
        self._visit(n.condition, d, nid, 'cond')
        self._visit(n.if_body, d, nid, 'then')
        if n.else_body:
            self._visit(n.else_body, d, nid, 'else')

    def _v_WhileNode(self, n, d, pid, el):
        nid = self._node(d, 'While', n); self._edge(d, pid, nid, el)
        self._visit(n.condition, d, nid, 'cond')
        self._visit(n.body, d, nid, 'body')

    def _v_BlockNode(self, n, d, pid, el):
        nid = self._node(d, f'Block ({len(n.statements)})', n); self._edge(d, pid, nid, el)
        for i, s in enumerate(n.statements):
            self._visit(s, d, nid, f'{i+1}')

    def _v_FuncDefNode(self, n, d, pid, el):
        params = ', '.join(n.params)
        nid = self._node(d, f'def {n.name}({params})', n); self._edge(d, pid, nid, el)
        self._visit(n.body, d, nid, 'body')

    def _v_ReturnNode(self, n, d, pid, el):
        nid = self._node(d, 'Return', n); self._edge(d, pid, nid, el)
        self._visit(n.expr, d, nid, 'val')

    def _v_BinOpNode(self, n, d, pid, el):
        nid = self._node(d, f'{n.op}', n); self._edge(d, pid, nid, el)
        self._visit(n.left, d, nid, 'L')
        self._visit(n.right, d, nid, 'R')

    def _v_CompareNode(self, n, d, pid, el):
        nid = self._node(d, f'{n.op}', n); self._edge(d, pid, nid, el)
        self._visit(n.left, d, nid, 'L')
        self._visit(n.right, d, nid, 'R')

    def _v_UnaryOpNode(self, n, d, pid, el):
        nid = self._node(d, f'unary {n.op}', n); self._edge(d, pid, nid, el)
        self._visit(n.operand, d, nid)

    def _v_FuncCallNode(self, n, d, pid, el):
        nid = self._node(d, f'call {n.name}()', n); self._edge(d, pid, nid, el)
        for i, a in enumerate(n.args):
            self._visit(a, d, nid, f'arg{i+1}')

    def _v_NumNode(self, n, d, pid, el):
        nid = self._node(d, str(n.value), n); self._edge(d, pid, nid, el)

    def _v_StringNode(self, n, d, pid, el):
        nid = self._node(d, f'"{n.value}"', n); self._edge(d, pid, nid, el)

    def _v_VarNode(self, n, d, pid, el):
        nid = self._node(d, n.name, n); self._edge(d, pid, nid, el)

    def _v_unknown(self, n, d, pid, el):
        nid = self._node(d, type(n).__name__, n); self._edge(d, pid, nid, el)


def visualise_ast(ast_root, filename='ast_output', fmt='png'):
    if not HAS_GRAPHVIZ:
        print("  [!] graphviz not installed. pip install graphviz && brew install graphviz")
        return None
    viz = ASTVisualiser()
    dot = viz.build(ast_root)
    try:
        path = dot.render(filename, format=fmt, cleanup=True)
        return path
    except Exception as e:
        print(f"  [!] Graphviz render failed: {e}")
        gv = filename + '.gv'
        dot.save(gv)
        return gv
