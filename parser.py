"""
parser.py — LALR(1) Parser using PLY yacc (Production)
=======================================================
Supports: assignments, augmented assignments (+=, -=, *=, /=),
arithmetic, comparisons, if/elif/else, while, functions, return,
print, strings. Uses brace-delimited blocks.
"""

import ply.yacc as yacc
from lexer import tokens, lexer  # noqa: F401
from ast_nodes import (
    ProgramNode, AssignNode, BinOpNode, CompareNode, UnaryOpNode,
    NumNode, StringNode, VarNode, PrintNode, IfNode, WhileNode,
    BlockNode, FuncDefNode, ReturnNode, FuncCallNode,
)

# ── Operator precedence (lowest → highest) ─────────────────────

precedence = (
    ('left', 'EQEQ', 'NEQ', 'LT', 'GT', 'LTE', 'GTE'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE', 'MODULO'),
    ('right', 'UMINUS'),
)

# ── Program ────────────────────────────────────────────────────

def p_program(p):
    """program : stmt_list"""
    p[0] = ProgramNode(p[1])

def p_stmt_list_multi(p):
    """stmt_list : stmt_list statement"""
    if p[2] is not None:
        p[1].append(p[2])
    p[0] = p[1]

def p_stmt_list_single(p):
    """stmt_list : statement"""
    p[0] = [p[1]] if p[1] is not None else []

# ── Statements ─────────────────────────────────────────────────

def p_stmt_assign(p):
    """statement : ID EQUALS expression NEWLINE
                 | ID EQUALS expression"""
    p[0] = AssignNode(p[1], p[3])

# ── Augmented assignment (desugared to x = x OP expr) ─────────

def p_stmt_aug_assign(p):
    """statement : ID PLUSEQ expression NEWLINE
                 | ID PLUSEQ expression
                 | ID MINUSEQ expression NEWLINE
                 | ID MINUSEQ expression
                 | ID TIMESEQ expression NEWLINE
                 | ID TIMESEQ expression
                 | ID DIVEQ expression NEWLINE
                 | ID DIVEQ expression"""
    # Map augmented operator to arithmetic operator
    op_map = {'+=': '+', '-=': '-', '*=': '*', '/=': '/'}
    op = op_map[p[2]]
    # x += expr  →  x = x + expr
    p[0] = AssignNode(p[1], BinOpNode(op, VarNode(p[1]), p[3]))

def p_stmt_print(p):
    """statement : PRINT LPAREN expression RPAREN NEWLINE
                 | PRINT LPAREN expression RPAREN"""
    p[0] = PrintNode(p[3])

def p_stmt_return(p):
    """statement : RETURN expression NEWLINE
                 | RETURN expression"""
    p[0] = ReturnNode(p[2])

def p_stmt_expr(p):
    """statement : expression NEWLINE
                 | expression"""
    p[0] = p[1]

def p_stmt_newline(p):
    """statement : NEWLINE"""
    p[0] = None

# ── If / Elif / Else ──────────────────────────────────────────

def p_stmt_if_only(p):
    """statement : IF expression LBRACE stmt_list RBRACE"""
    p[0] = IfNode(p[2], BlockNode(p[4]))

def p_stmt_if_with_tail(p):
    """statement : IF expression LBRACE stmt_list RBRACE else_clause"""
    p[0] = IfNode(p[2], BlockNode(p[4]), p[6])

def p_else_block(p):
    """else_clause : ELSE LBRACE stmt_list RBRACE"""
    p[0] = BlockNode(p[3])

def p_elif_only(p):
    """else_clause : ELIF expression LBRACE stmt_list RBRACE"""
    p[0] = BlockNode([IfNode(p[2], BlockNode(p[4]))])

def p_elif_with_tail(p):
    """else_clause : ELIF expression LBRACE stmt_list RBRACE else_clause"""
    p[0] = BlockNode([IfNode(p[2], BlockNode(p[4]), p[6])])

# ── While ──────────────────────────────────────────────────────

def p_stmt_while(p):
    """statement : WHILE expression LBRACE stmt_list RBRACE"""
    p[0] = WhileNode(p[2], BlockNode(p[4]))

# ── Function definition ───────────────────────────────────────

def p_stmt_funcdef(p):
    """statement : DEF ID LPAREN param_list RPAREN LBRACE stmt_list RBRACE"""
    p[0] = FuncDefNode(p[2], p[4], BlockNode(p[7]))

def p_stmt_funcdef_noparams(p):
    """statement : DEF ID LPAREN RPAREN LBRACE stmt_list RBRACE"""
    p[0] = FuncDefNode(p[2], [], BlockNode(p[6]))

def p_param_list_multi(p):
    """param_list : param_list COMMA ID"""
    p[0] = p[1] + [p[3]]

def p_param_list_single(p):
    """param_list : ID"""
    p[0] = [p[1]]

# ── Expressions: comparisons ──────────────────────────────────

def p_expr_compare(p):
    """expression : expression EQEQ expression
                  | expression NEQ  expression
                  | expression LT   expression
                  | expression GT   expression
                  | expression LTE  expression
                  | expression GTE  expression"""
    p[0] = CompareNode(p[2], p[1], p[3])

# ── Expressions: arithmetic ───────────────────────────────────

def p_expr_binop(p):
    """expression : expression PLUS   expression
                  | expression MINUS  expression
                  | expression TIMES  expression
                  | expression DIVIDE expression
                  | expression MODULO expression"""
    p[0] = BinOpNode(p[2], p[1], p[3])

def p_expr_uminus(p):
    """expression : MINUS expression %prec UMINUS"""
    p[0] = UnaryOpNode('-', p[2])

def p_expr_group(p):
    """expression : LPAREN expression RPAREN"""
    p[0] = p[2]

# ── Expressions: atoms ────────────────────────────────────────

def p_expr_number(p):
    """expression : NUMBER"""
    p[0] = NumNode(p[1])

def p_expr_string(p):
    """expression : STRING"""
    p[0] = StringNode(p[1])

def p_expr_var(p):
    """expression : ID"""
    p[0] = VarNode(p[1])

def p_expr_funccall(p):
    """expression : ID LPAREN arg_list RPAREN"""
    p[0] = FuncCallNode(p[1], p[3])

def p_expr_funccall_noargs(p):
    """expression : ID LPAREN RPAREN"""
    p[0] = FuncCallNode(p[1], [])

def p_arg_list_multi(p):
    """arg_list : arg_list COMMA expression"""
    p[0] = p[1] + [p[3]]

def p_arg_list_single(p):
    """arg_list : expression"""
    p[0] = [p[1]]

# ── Error ──────────────────────────────────────────────────────

def p_error(p):
    if p:
        raise SyntaxError(
            f"[Line {p.lineno}] Syntax error near {p.type!r} ({p.value!r})"
        )
    raise SyntaxError("Syntax error at end of file")

# ── Build parser ───────────────────────────────────────────────

parser = yacc.yacc(errorlog=yacc.NullLogger(), debug=False)

def parse(source: str) -> ProgramNode:
    """Parse source code → ProgramNode (AST root)."""
    return parser.parse(source, lexer=lexer, tracking=True)
