"""Recursive descent statement parser — all stages (A through D)."""
from __future__ import annotations
from compiler.core.ast import (
    AssignStmt, AttributeAssignStmt, BinaryExpr, BreakStmt, CallExpr,
    ClassDef, ConstantExpr, ContinueStmt, DeleteStmt, ExceptHandler,
    ExprStmt, ForStmt, FromImportStmt, FunctionDef, GlobalStmt, IfStmt,
    ImportStmt, NameExpr, NonlocalStmt, PassStmt, PrintStmt, Program,
    RaiseStmt, ReturnStmt, StarUnpackAssignStmt, Statement, TryStmt,
    TupleExpr, UnaryExpr, UnpackAssignStmt, WhileStmt, WithStmt, Expression,
    AttributeExpr, IndexExpr, SliceExpr, NamedExpr,
)
from compiler.frontend.parser.expr_parser import ExprParser
from compiler.frontend.parser.precedence import AUGASSIGN_OPS, BP_TERNARY
from compiler.frontend.parser.recovery import synchronize
from compiler.frontend.parser.token_cursor import ParseError, TokenCursor
from compiler.frontend.tokens import LexedSource
from compiler.utils.error_handler import ErrorHandler


class StmtParser:
    """Top-level parser that drives the token cursor and expression parser."""

    def __init__(self, cursor: TokenCursor, errors: ErrorHandler) -> None:
        self.cursor = cursor
        self.errors = errors
        self.expr = ExprParser(cursor)
        self._function_depth = 0

    # ── Public API ──────────────────────────────────────────────────

    def parse_module(self) -> Program:
        self.cursor.skip_noise()
        body = self._parse_body(allow_docstring=True, top_level=True)
        if body:
            span = body[0].span
            end = body[-1].span
            return Program(
                span=type(span)(
                    line=span.line,
                    column=span.column,
                    end_line=end.end_line,
                    end_column=end.end_column,
                ),
                body=body,
            )
        return Program(span=self.cursor.current_span(), body=body)

    # ── Block / body parsing ────────────────────────────────────────

    def _parse_body(self, allow_docstring: bool = False, top_level: bool = False) -> list[Statement]:
        stmts: list[Statement] = []
        while not self.cursor.at_end() and self.cursor.peek_kind() != "ENDMARKER":
            if self.cursor.peek_kind() == "DEDENT":
                if top_level:
                    self.cursor.advance()
                    continue
                break
            self.cursor.skip_noise()
            if self.cursor.at_end() or self.cursor.peek_kind() == "ENDMARKER":
                break
            if self.cursor.peek_kind() == "DEDENT":
                if top_level:
                    self.cursor.advance()
                    continue
                break
            try:
                result = self._parse_statement()
                if result is None:
                    continue
                if allow_docstring and not stmts and isinstance(result, ExprStmt):
                    if isinstance(result.expr, ConstantExpr) and isinstance(result.expr.value, str):
                        continue  # skip docstring
                if isinstance(result, list):
                    stmts.extend(r for r in result if r is not None)
                else:
                    stmts.append(result)
            except ParseError as e:
                self.errors.error("Syntax", str(e), e.line, e.column)
                synchronize(self.cursor)
        return stmts

    def _parse_block(self, allow_docstring: bool = True) -> list[Statement]:
        self.cursor.expect("NEWLINE", msg="expected newline before block")
        self.cursor.expect("INDENT", msg="expected indented block")
        body = self._parse_body(allow_docstring=allow_docstring)
        if self.cursor.peek_kind() == "DEDENT":
            self.cursor.advance()
        return body

    # ── Statement dispatch ──────────────────────────────────────────

    def _parse_statement(self):
        tok = self.cursor.peek()
        if tok.kind in ("NEWLINE", "NL", "COMMENT"):
            self.cursor.advance()
            return None
        if tok.kind == "NAME":
            dispatch = {
                "pass": self._parse_pass,
                "break": self._parse_break,
                "continue": self._parse_continue,
                "return": self._parse_return,
                "if": self._parse_if,
                "while": self._parse_while,
                "for": self._parse_for,
                "def": self._parse_def,
                "class": self._parse_class,
                "import": self._parse_import,
                "from": self._parse_from_import,
                "raise": self._parse_raise,
                "try": self._parse_try,
                "with": self._parse_with,
                "del": self._parse_del,
                "global": self._parse_global,
                "nonlocal": self._parse_nonlocal,
                "assert": self._parse_assert,
            }
            handler = dispatch.get(tok.text)
            if handler is not None:
                return handler()
            if tok.text == "@":
                return self._parse_decorated()
        if tok.kind == "OP" and tok.text == "@":
            return self._parse_decorated()
        return self._parse_expr_or_assign_stmt()

    # ── Simple statements ───────────────────────────────────────────

    def _parse_pass(self):
        tok = self.cursor.advance()
        self._consume_newline()
        return PassStmt(span=self.cursor.span_from(tok))

    def _parse_break(self):
        tok = self.cursor.advance()
        self._consume_newline()
        return BreakStmt(span=self.cursor.span_from(tok))

    def _parse_continue(self):
        tok = self.cursor.advance()
        self._consume_newline()
        return ContinueStmt(span=self.cursor.span_from(tok))

    def _parse_return(self):
        tok = self.cursor.advance()
        value = None
        if not self._at_stmt_end():
            value = self._parse_testlist()
        self._consume_newline()
        return ReturnStmt(span=self.cursor.span_from(tok), value=value)

    def _parse_global(self):
        tok = self.cursor.advance()
        names = [self.cursor.expect("NAME", msg="expected name after 'global'").text]
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            names.append(self.cursor.expect("NAME").text)
        self._consume_newline()
        return GlobalStmt(span=self.cursor.span_from(tok), names=names)

    def _parse_nonlocal(self):
        tok = self.cursor.advance()
        names = [self.cursor.expect("NAME", msg="expected name after 'nonlocal'").text]
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            names.append(self.cursor.expect("NAME").text)
        self._consume_newline()
        return NonlocalStmt(span=self.cursor.span_from(tok), names=names)

    def _parse_del(self):
        tok = self.cursor.advance()
        targets = [self._parse_del_target()]
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            targets.append(self._parse_del_target())
        self._consume_newline()
        return DeleteStmt(span=self.cursor.span_from(tok), targets=targets)

    def _parse_del_target(self) -> Expression:
        expr = self.expr.parse_expression()
        if isinstance(expr, (NameExpr, AttributeExpr, IndexExpr)):
            return expr
        raise ParseError("only name, attribute, and subscript delete targets are supported",
                         self.cursor.peek().line, self.cursor.peek().column)

    # ── If / While / For ────────────────────────────────────────────

    def _parse_if(self):
        tok = self.cursor.advance()  # 'if'
        condition = self.expr.parse_expression()
        self.cursor.expect("OP", ":", msg="expected ':' after if condition")
        body = self._parse_block()
        orelse = self._parse_else_chain()
        return IfStmt(span=self.cursor.span_from(tok), condition=condition, body=body, orelse=orelse)

    def _parse_else_chain(self) -> list[Statement]:
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "elif":
            elif_tok = self.cursor.advance()
            condition = self.expr.parse_expression()
            self.cursor.expect("OP", ":", msg="expected ':' after elif condition")
            body = self._parse_block()
            orelse = self._parse_else_chain()
            return [IfStmt(span=self.cursor.span_from(elif_tok), condition=condition, body=body, orelse=orelse)]
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "else":
            self.cursor.advance()
            self.cursor.expect("OP", ":", msg="expected ':' after else")
            return self._parse_block()
        return []

    def _parse_while(self):
        tok = self.cursor.advance()
        condition = self.expr.parse_expression()
        self.cursor.expect("OP", ":", msg="expected ':' after while condition")
        body = self._parse_block()
        orelse = []
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "else":
            self.cursor.advance()
            self.cursor.expect("OP", ":", msg="expected ':'")
            orelse = self._parse_block()
        return WhileStmt(span=self.cursor.span_from(tok), condition=condition, body=body, orelse=orelse)

    def _parse_for(self):
        tok = self.cursor.advance()  # 'for'
        target = self._parse_for_target()
        self.cursor.expect("NAME", "in", msg="expected 'in' after for target")
        iterator = self.expr.parse_expression()
        self.cursor.expect("OP", ":", msg="expected ':' after for iterator")
        body = self._parse_block()
        orelse = []
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "else":
            self.cursor.advance()
            self.cursor.expect("OP", ":", msg="expected ':'")
            orelse = self._parse_block()
        return ForStmt(span=self.cursor.span_from(tok), target=target, iterator=iterator, body=body, orelse=orelse)

    def _parse_for_target(self):
        name_tok = self.cursor.expect("NAME", msg="expected loop variable")
        if self.cursor.peek().text == ",":
            names = [name_tok.text]
            while self.cursor.peek().text == ",":
                self.cursor.advance()
                if self.cursor.peek().kind == "NAME" and self.cursor.peek().text != "in":
                    names.append(self.cursor.advance().text)
                else:
                    break
            return names
        return name_tok.text

    # ── Function / Class ────────────────────────────────────────────

    def _parse_def(self):
        tok = self.cursor.advance()  # 'def'
        name = self.cursor.expect("NAME", msg="expected function name").text
        self.cursor.expect("OP", "(", msg="expected '(' after function name")
        params, defaults, kwonly, kwonly_defaults, vararg, kwarg = self._parse_params()
        self.cursor.expect("OP", ")", msg="expected ')' after parameters")
        # Skip return annotation
        if self.cursor.peek().text == "->":
            self.cursor.advance()
            self.expr.parse_expression()
            self.errors.error("Syntax", "function return annotations are not supported",
                              self.cursor.peek().line, self.cursor.peek().column)
            return None
        self.cursor.expect("OP", ":", msg="expected ':' after function signature")
        self._function_depth += 1
        body = self._parse_block(allow_docstring=True)
        self._function_depth -= 1
        return FunctionDef(
            span=self.cursor.span_from(tok), name=name, params=params,
            body=body, defaults=defaults, kwonly_params=kwonly,
            kwonly_defaults=kwonly_defaults, vararg=vararg, kwarg=kwarg,
        )

    def _parse_params(self):
        params, defaults = [], []
        kwonly, kwonly_defaults = [], {}
        vararg, kwarg = None, None
        if self.cursor.peek().text == ")":
            return params, defaults, kwonly, kwonly_defaults, vararg, kwarg
        seen_star = False
        while self.cursor.peek().text != ")":
            if self.cursor.peek().text == "**":
                self.cursor.advance()
                kwarg = self.cursor.expect("NAME").text
            elif self.cursor.peek().text == "*":
                self.cursor.advance()
                seen_star = True
                if self.cursor.peek().kind == "NAME" and self.cursor.peek().text not in (",", ")"):
                    vararg = self.cursor.advance().text
            elif self.cursor.peek().kind == "NAME":
                p = self.cursor.advance().text
                # Skip annotation
                if self.cursor.peek().text == ":":
                    self.cursor.advance()
                    self.expr.parse_expression(BP_TERNARY + 1)
                if seen_star:
                    kwonly.append(p)
                    if self.cursor.peek().text == "=":
                        self.cursor.advance()
                        kwonly_defaults[p] = self.expr.parse_expression(BP_TERNARY + 1)
                else:
                    params.append(p)
                    if self.cursor.peek().text == "=":
                        self.cursor.advance()
                        defaults.append(self.expr.parse_expression(BP_TERNARY + 1))
            if self.cursor.peek().text == ",":
                self.cursor.advance()
            else:
                break
        return params, defaults, kwonly, kwonly_defaults, vararg, kwarg

    def _parse_class(self):
        tok = self.cursor.advance()  # 'class'
        name = self.cursor.expect("NAME", msg="expected class name").text
        bases: list[Expression] = []
        if self.cursor.peek().text == "(":
            self.cursor.advance()
            while self.cursor.peek().text != ")":
                bases.append(self.expr.parse_expression())
                if self.cursor.peek().text == ",":
                    self.cursor.advance()
            self.cursor.expect("OP", ")", msg="expected ')'")
        self.cursor.expect("OP", ":", msg="expected ':' after class")
        self.cursor.expect("NEWLINE")
        self.cursor.expect("INDENT")
        attributes, methods = [], []
        while self.cursor.peek_kind() not in ("DEDENT", "ENDMARKER") and not self.cursor.at_end():
            self.cursor.skip_noise()
            if self.cursor.peek_kind() in ("DEDENT", "ENDMARKER"):
                break
            tok2 = self.cursor.peek()
            if tok2.kind == "NAME" and tok2.text == "pass":
                self.cursor.advance()
                self._consume_newline()
                continue
            if tok2.kind == "NAME" and tok2.text == "def":
                result = self._parse_def()
                if isinstance(result, FunctionDef):
                    methods.append(result)
                continue
            if tok2.kind == "NAME" and tok2.text == "@":
                result = self._parse_decorated()
                if isinstance(result, list):
                    for r in result:
                        if isinstance(r, FunctionDef):
                            methods.append(r)
                elif isinstance(result, FunctionDef):
                    methods.append(result)
                continue
            if tok2.kind == "OP" and tok2.text == "@":
                result = self._parse_decorated()
                if isinstance(result, list):
                    for r in result:
                        if isinstance(r, FunctionDef):
                            methods.append(r)
                elif isinstance(result, FunctionDef):
                    methods.append(result)
                continue
            # Try docstring
            if tok2.kind == "STRING":
                self.cursor.advance()
                self._consume_newline()
                continue
            # Class attribute
            result = self._parse_expr_or_assign_stmt()
            if isinstance(result, AssignStmt):
                attributes.append(result)
        if self.cursor.peek_kind() == "DEDENT":
            self.cursor.advance()
        return ClassDef(span=self.cursor.span_from(tok), name=name, bases=bases, attributes=attributes, methods=methods)

    # ── Decorators ──────────────────────────────────────────────────

    def _parse_decorated(self):
        decorators = []
        while self.cursor.peek().text == "@":
            self.cursor.advance()
            decorators.append(self.expr.parse_expression())
            self._consume_newline()
        if self.cursor.peek().text == "def":
            defn = self._parse_def()
        elif self.cursor.peek().text == "class":
            defn = self._parse_class()
        else:
            raise ParseError("expected 'def' or 'class' after decorator", self.cursor.peek().line, self.cursor.peek().column)
        if defn is None:
            return None
        name = defn.name
        span = defn.span
        result = [defn]
        from compiler.core.ast import CallValueExpr
        current = NameExpr(span=span, name=name)
        for dec in reversed(decorators):
            current = CallValueExpr(span=span, callee=dec, args=[current])
        result.append(AssignStmt(span=span, name=name, value=current))
        return result

    # ── Import ──────────────────────────────────────────────────────

    def _parse_import(self):
        tok = self.cursor.advance()
        results = []
        mod = self._parse_dotted_name()
        alias = None
        if self.cursor.peek().text == "as":
            self.cursor.advance()
            alias = self.cursor.expect("NAME").text
        results.append(ImportStmt(span=self.cursor.span_from(tok), module=mod, alias=alias))
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            mod = self._parse_dotted_name()
            alias = None
            if self.cursor.peek().text == "as":
                self.cursor.advance()
                alias = self.cursor.expect("NAME").text
            results.append(ImportStmt(span=self.cursor.span_from(tok), module=mod, alias=alias))
        self._consume_newline()
        return results

    def _parse_from_import(self):
        tok = self.cursor.advance()  # 'from'
        level = 0
        while self.cursor.peek().text == ".":
            self.cursor.advance()
            level += 1
        module = None
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text != "import":
            module = self._parse_dotted_name()
        self.cursor.expect("NAME", "import", msg="expected 'import'")
        results = []
        if self.cursor.peek().text == "*":
            self.cursor.advance()
            results.append(FromImportStmt(span=self.cursor.span_from(tok), module=module, name="*", alias=None, level=level))
        else:
            while True:
                name = self.cursor.expect("NAME", msg="expected name to import").text
                alias = None
                if self.cursor.peek().text == "as":
                    self.cursor.advance()
                    alias = self.cursor.expect("NAME").text
                results.append(FromImportStmt(span=self.cursor.span_from(tok), module=module, name=name, alias=alias, level=level))
                if self.cursor.peek().text == ",":
                    self.cursor.advance()
                else:
                    break
        self._consume_newline()
        return results

    def _parse_dotted_name(self) -> str:
        name = self.cursor.expect("NAME", msg="expected module name").text
        while self.cursor.peek().text == ".":
            self.cursor.advance()
            name += "." + self.cursor.expect("NAME").text
        return name

    # ── Raise / Try / With / Assert ─────────────────────────────────

    def _parse_raise(self):
        tok = self.cursor.advance()
        value = None
        cause = None
        if not self._at_stmt_end():
            value = self.expr.parse_expression()
            if self.cursor.peek().text == "from":
                self.cursor.advance()
                cause = self.expr.parse_expression()
        self._consume_newline()
        return RaiseStmt(span=self.cursor.span_from(tok), value=value, cause=cause)

    def _parse_try(self):
        tok = self.cursor.advance()
        self.cursor.expect("OP", ":", msg="expected ':' after try")
        body = self._parse_block()
        handlers = []
        while self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "except":
            handlers.append(self._parse_except_handler())
        orelse = []
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "else":
            self.cursor.advance()
            self.cursor.expect("OP", ":")
            orelse = self._parse_block()
        finalbody = []
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "finally":
            self.cursor.advance()
            self.cursor.expect("OP", ":")
            finalbody = self._parse_block()
        return TryStmt(span=self.cursor.span_from(tok), body=body, handlers=handlers, orelse=orelse, finalbody=finalbody)

    def _parse_except_handler(self) -> ExceptHandler:
        tok = self.cursor.advance()  # 'except'
        type_name = None
        name = None
        if self.cursor.peek().text != ":":
            type_name = self.cursor.expect("NAME", msg="expected exception type").text
            if self.cursor.peek().text == "as":
                self.cursor.advance()
                name = self.cursor.expect("NAME").text
        self.cursor.expect("OP", ":", msg="expected ':' after except")
        body = self._parse_block()
        return ExceptHandler(span=self.cursor.span_from(tok), type_name=type_name, name=name, body=body)

    def _parse_with(self):
        tok = self.cursor.advance()  # 'with'
        items = []
        while True:
            ctx = self.expr.parse_expression()
            opt_var = None
            if self.cursor.peek().text == "as":
                self.cursor.advance()
                name_tok = self.cursor.expect("NAME", msg="expected name after 'as'")
                opt_var = name_tok.text
            items.append((ctx, opt_var))
            if self.cursor.peek().text == ",":
                self.cursor.advance()
            else:
                break
        self.cursor.expect("OP", ":", msg="expected ':' after with")
        body = self._parse_block(allow_docstring=True)
        # Nest from right to left (like ast_lowering does)
        for ctx, opt_var in reversed(items):
            body = [WithStmt(span=self.cursor.span_from(tok), context_expr=ctx, optional_var=opt_var, body=body)]
        return body[0]

    def _parse_assert(self):
        tok = self.cursor.advance()  # 'assert'
        condition = self.expr.parse_expression()
        span = self.cursor.span_from(tok)
        negated = UnaryExpr(span=span, op="not", operand=condition)
        if self.cursor.peek().text == ",":
            self.cursor.advance()
            msg = self.expr.parse_expression()
        else:
            msg = ConstantExpr(span=span, value="assertion failed")
        error_call = CallExpr(span=span, func_name="AssertionError", args=[msg])
        raise_stmt = RaiseStmt(span=span, value=error_call)
        self._consume_newline()
        return IfStmt(span=span, condition=negated, body=[raise_stmt], orelse=[])

    # ── Expression / Assignment ─────────────────────────────────────

    def _parse_expr_or_assign_stmt(self):
        start = self.cursor.peek()
        expr = self._parse_testlist()
        # Augmented assignment: x += ...
        if self.cursor.peek().text in AUGASSIGN_OPS:
            op_tok = self.cursor.advance()
            base_op = AUGASSIGN_OPS[op_tok.text]
            if not isinstance(expr, NameExpr):
                self.errors.error("Syntax", "only simple name augmented assignment is supported", start.line, start.column)
                return None
            right = self.expr.parse_expression()
            left = NameExpr(span=expr.span, name=expr.name)
            value = BinaryExpr(span=self.cursor.span_from(start), op=base_op, left=left, right=right)
            self._consume_newline()
            return AssignStmt(span=self.cursor.span_from(start), name=expr.name, value=value)
        # Simple assignment: target = value
        if self.cursor.peek().text == "=":
            self.cursor.advance()
            value = self._parse_testlist()
            self._consume_newline()
            span = self.cursor.span_from(start)
            if isinstance(expr, NameExpr):
                return AssignStmt(span=span, name=expr.name, value=value)
            if isinstance(expr, AttributeExpr):
                return AttributeAssignStmt(span=span, object=expr.object, attr_name=expr.attr_name, value=value)
            if isinstance(expr, TupleExpr):
                return self._lower_tuple_assign(expr, value, span)
            self.errors.error("Syntax", "unsupported assignment target", start.line, start.column)
            return None
        # print() special-case
        if isinstance(expr, CallExpr) and expr.func_name == "print":
            self._consume_newline()
            return self._lower_print(expr)
        self._consume_newline()
        return ExprStmt(span=self.cursor.span_from(start), expr=expr)

    def _lower_tuple_assign(self, tuple_expr, value, span):
        from compiler.core.ast import TupleExpr, StarredExpr
        elements = tuple_expr.elements
        starred_indices = [i for i, e in enumerate(elements) if isinstance(e, StarredExpr)]
        if starred_indices:
            if len(starred_indices) != 1:
                self.errors.error("Syntax", "only a single starred assignment target is supported", span.line, span.column)
                return None
            idx = starred_indices[0]
            star_el = elements[idx]
            if not isinstance(star_el.value, NameExpr):
                self.errors.error("Syntax", "only simple names may be starred in assignment", span.line, span.column)
                return None
            prefix = elements[:idx]
            suffix = elements[idx+1:]
            if not all(isinstance(e, NameExpr) for e in prefix + suffix):
                self.errors.error("Syntax", "only simple names in unpacking assignment are supported", span.line, span.column)
                return None
            return StarUnpackAssignStmt(
                span=span,
                prefix_targets=[e.name for e in prefix],
                starred_target=star_el.value.name,
                suffix_targets=[e.name for e in suffix],
                value=value,
            )
        if not all(isinstance(e, NameExpr) for e in elements):
            self.errors.error("Syntax", "only simple names in unpacking assignment are supported", span.line, span.column)
            return None
        return UnpackAssignStmt(span=span, targets=[e.name for e in elements], value=value)

    def _lower_print(self, call: CallExpr) -> PrintStmt:
        sep, end = None, None
        for k, v in call.kwargs.items():
            if k == "sep":
                sep = v
            elif k == "end":
                end = v
            else:
                self.errors.error("Syntax", f"print() keyword '{k}' is not supported yet", call.span.line, call.span.column)
        return PrintStmt(span=call.span, values=call.args, sep=sep, end=end)

    # ── Utilities ───────────────────────────────────────────────────

    def _parse_testlist(self) -> Expression:
        start = self.cursor.peek()
        expr = self.expr.parse_expression()
        if self.cursor.peek().text == ",":
            elements = [expr]
            while self.cursor.peek().text == ",":
                self.cursor.advance()
                if self._at_stmt_end() or self.cursor.peek().text in AUGASSIGN_OPS or self.cursor.peek().text == "=":
                    break
                elements.append(self.expr.parse_expression())
            if len(elements) > 1 or self.cursor.peek_previous().text == ",":
                return TupleExpr(span=self.cursor.span_from(start), elements=elements)
        return expr

    def _at_stmt_end(self) -> bool:
        k = self.cursor.peek_kind()
        return k in ("NEWLINE", "NL", "ENDMARKER", "DEDENT", "COMMENT")

    def _consume_newline(self):
        k = self.cursor.peek_kind()
        if k in ("NEWLINE", "NL", "COMMENT"):
            self.cursor.advance()
        elif k == "ENDMARKER":
            pass
        # For semicolons or other cases, just skip


def parse_to_program(lexed: LexedSource, errors: ErrorHandler) -> Program | None:
    """Public entry: parse tokens into a Program AST directly."""
    cursor = TokenCursor(lexed.tokens)
    parser = StmtParser(cursor, errors)
    try:
        return parser.parse_module()
    except ParseError as e:
        errors.error("Syntax", str(e), e.line, e.column)
        return None
