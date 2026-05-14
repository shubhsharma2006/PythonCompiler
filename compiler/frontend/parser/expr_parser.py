"""Pratt expression parser — all stages (A through D)."""
from __future__ import annotations
from compiler.core.ast import (
    AttributeExpr, BinaryExpr, BoolOpExpr, CallExpr, CallValueExpr,
    CompareChainExpr, CompareExpr, Comprehension, ConstantExpr,
    DictCompExpr, DictExpr, Expression, IfExpr, IndexExpr,
    KwStarredExpr, LambdaExpr, ListCompExpr, ListExpr, MethodCallExpr,
    NameExpr, NamedExpr, ReturnStmt, SetCompExpr, SetExpr, SliceExpr,
    SourceSpan, StarredExpr, TupleExpr, UnaryExpr, FunctionDef, YieldExpr,
)
from compiler.frontend.parser.token_cursor import ParseError, TokenCursor
from compiler.frontend.parser.precedence import (
    AUGASSIGN_OPS, BP_ADD, BP_AND, BP_ATTR, BP_BIT_AND, BP_BIT_OR,
    BP_BIT_XOR, BP_CALL, BP_COMPARE, BP_INDEX, BP_MUL, BP_NONE,
    BP_NOT, BP_OR, BP_POWER, BP_SHIFT, BP_TERNARY, BP_UNARY,
    BP_WALRUS, COMPARE_OPS, INFIX_BP, UNARY_OPS,
)

class ExprParser:
    def __init__(self, cursor: TokenCursor) -> None:
        self.cursor = cursor
        self._lambda_counter = 0

    def parse_expression(self, min_bp: int = BP_NONE) -> Expression:
        left = self._parse_prefix()
        while not self.cursor.at_end():
            left = self._parse_infix(left, min_bp)
            if left is None:
                raise ParseError("failed to parse expression", self.cursor.peek().line, self.cursor.peek().column)
            # Check if we should continue
            bp = self._current_infix_bp()
            if bp is None or bp <= min_bp:
                break
            left = self._parse_infix(left, min_bp)
        return left

    def parse_expression_or_none(self, min_bp: int = BP_NONE) -> Expression | None:
        try:
            return self.parse_expression(min_bp)
        except ParseError:
            return None

    # ── Prefix (atoms) ──────────────────────────────────────────────

    def _parse_prefix(self) -> Expression:
        tok = self.cursor.peek()
        # Numbers
        if tok.kind == "NUMBER":
            self.cursor.advance()
            if "." in tok.text or "e" in tok.text.lower() or "j" in tok.text.lower():
                return ConstantExpr(span=self.cursor.span_from(tok), value=complex(tok.text) if tok.text.lower().endswith("j") else float(tok.text))
            return ConstantExpr(span=self.cursor.span_from(tok), value=int(tok.text, 0))
        # Strings
        if tok.kind == "STRING":
            return self._parse_string()
        # Names / keywords
        if tok.kind == "NAME":
            if tok.text == "True":
                self.cursor.advance()
                return ConstantExpr(span=self.cursor.span_from(tok), value=True)
            if tok.text == "False":
                self.cursor.advance()
                return ConstantExpr(span=self.cursor.span_from(tok), value=False)
            if tok.text == "None":
                self.cursor.advance()
                return ConstantExpr(span=self.cursor.span_from(tok), value=None)
            if tok.text in ("not",):
                return self._parse_unary()
            if tok.text == "lambda":
                return self._parse_lambda()
            if tok.text == "yield":
                return self._parse_yield()
            self.cursor.advance()
            return NameExpr(span=self.cursor.span_from(tok), name=tok.text)
        # Unary operators
        if tok.kind == "OP" and tok.text in ("-", "+", "~"):
            return self._parse_unary()
        # Parenthesized / tuple
        if tok.kind == "OP" and tok.text == "(":
            return self._parse_paren()
        # List literal / comprehension
        if tok.kind == "OP" and tok.text == "[":
            return self._parse_list()
        # Dict / Set literal / comprehension
        if tok.kind == "OP" and tok.text == "{":
            return self._parse_dict_or_set()
        # Starred expression (in call arguments)
        if tok.kind == "OP" and tok.text == "*":
            self.cursor.advance()
            value = self.parse_expression(BP_UNARY)
            return StarredExpr(span=self.cursor.span_from(tok), value=value)
        # Ellipsis
        if tok.kind == "OP" and tok.text == "...":
            self.cursor.advance()
            return ConstantExpr(span=self.cursor.span_from(tok), value=...)
        raise ParseError(f"unexpected token '{tok.text}'", tok.line, tok.column)

    def _parse_unary(self) -> Expression:
        tok = self.cursor.advance()
        bp = UNARY_OPS.get(tok.text, BP_UNARY)
        operand = self.parse_expression(bp)
        return UnaryExpr(span=self.cursor.span_from(tok), op=tok.text, operand=operand)

    def _parse_yield(self) -> Expression:
        tok = self.cursor.advance()
        if self.cursor.peek_kind() == "NAME" and self.cursor.peek_text() == "from":
            from_tok = self.cursor.advance()
            raise ParseError("'yield from' is not supported yet", from_tok.line, from_tok.column)
        if self.cursor.peek_kind() in ("NEWLINE", "NL", "DEDENT", "ENDMARKER"):
            return YieldExpr(span=self.cursor.span_from(tok), value=None)
        if self.cursor.peek_kind() == "OP" and self.cursor.peek_text() in {")", "]", "}", ",", ":"}:
            return YieldExpr(span=self.cursor.span_from(tok), value=None)
        value = self.parse_expression(BP_NONE)
        return YieldExpr(span=self.cursor.span_from(tok), value=value)

    def _parse_string(self) -> Expression:
        tok = self.cursor.advance()
        text = tok.text
        prefix = ""
        while text and text[0].lower() in ("f", "r", "b", "u"):
            prefix += text[0].lower()
            text = text[1:]
        if "f" in prefix:
            return self._parse_fstring_value(tok)
        try:
            value = eval(tok.text)
        except Exception:
            value = tok.text.strip("'\"")
        # Concatenate adjacent string literals
        while not self.cursor.at_end() and self.cursor.peek().kind == "STRING":
            next_tok = self.cursor.advance()
            try:
                next_val = eval(next_tok.text)
            except Exception:
                next_val = next_tok.text.strip("'\"")
            value = value + next_val
        return ConstantExpr(span=self.cursor.span_from(tok), value=value)

    def _parse_fstring_value(self, tok) -> Expression:
        """Parse an f-string token into concatenated str() calls."""
        import ast as _ast
        try:
            tree = _ast.parse(tok.text, mode="eval")
        except SyntaxError:
            return ConstantExpr(span=self.cursor.span_from(tok), value="")
        if not isinstance(tree.body, _ast.JoinedStr):
            try:
                return ConstantExpr(span=self.cursor.span_from(tok), value=eval(tok.text))
            except Exception:
                return ConstantExpr(span=self.cursor.span_from(tok), value="")
        parts: list[Expression] = []
        span = self.cursor.span_from(tok)
        for value in tree.body.values:
            if isinstance(value, _ast.Constant):
                parts.append(ConstantExpr(span=span, value=str(value.value)))
            elif isinstance(value, _ast.FormattedValue):
                inner = self._lower_ast_expr(value.value, span)
                if value.conversion == ord("r"):
                    inner = CallExpr(span=span, func_name="repr", args=[inner])
                elif value.conversion == ord("a"):
                    inner = CallExpr(span=span, func_name="ascii", args=[inner])
                else:
                    inner = CallExpr(span=span, func_name="str", args=[inner])
                parts.append(inner)
        if not parts:
            return ConstantExpr(span=span, value="")
        expr = parts[0]
        for part in parts[1:]:
            expr = BinaryExpr(span=span, op="+", left=expr, right=part)
        return expr

    def _lower_ast_expr(self, node, span: SourceSpan) -> Expression:
        """Minimal CPython AST → our AST converter for f-string internals."""
        import ast as _ast
        if isinstance(node, _ast.Constant):
            return ConstantExpr(span=span, value=node.value)
        if isinstance(node, _ast.Name):
            return NameExpr(span=span, name=node.id)
        if isinstance(node, _ast.BinOp):
            op_map = {_ast.Add: "+", _ast.Sub: "-", _ast.Mult: "*", _ast.Div: "/", _ast.FloorDiv: "//", _ast.Mod: "%", _ast.Pow: "**"}
            op = op_map.get(type(node.op), "+")
            return BinaryExpr(span=span, op=op, left=self._lower_ast_expr(node.left, span), right=self._lower_ast_expr(node.right, span))
        if isinstance(node, _ast.Attribute):
            return AttributeExpr(span=span, object=self._lower_ast_expr(node.value, span), attr_name=node.attr)
        if isinstance(node, _ast.Call):
            args = [self._lower_ast_expr(a, span) for a in node.args]
            if isinstance(node.func, _ast.Name):
                return CallExpr(span=span, func_name=node.func.id, args=args)
            if isinstance(node.func, _ast.Attribute):
                obj = self._lower_ast_expr(node.func.value, span)
                return MethodCallExpr(span=span, object=obj, method_name=node.func.attr, args=args)
            callee = self._lower_ast_expr(node.func, span)
            return CallValueExpr(span=span, callee=callee, args=args)
        if isinstance(node, _ast.Subscript):
            return IndexExpr(span=span, collection=self._lower_ast_expr(node.value, span), index=self._lower_ast_expr(node.slice, span))
        if isinstance(node, _ast.Compare):
            cmp_map = {_ast.Eq: "==", _ast.NotEq: "!=", _ast.Lt: "<", _ast.Gt: ">", _ast.LtE: "<=", _ast.GtE: ">="}
            if len(node.ops) == 1:
                op = cmp_map.get(type(node.ops[0]), "==")
                return CompareExpr(span=span, op=op, left=self._lower_ast_expr(node.left, span), right=self._lower_ast_expr(node.comparators[0], span))
        return NameExpr(span=span, name="__unknown__")

    # ── Infix ───────────────────────────────────────────────────────

    def _current_infix_bp(self) -> int | None:
        tok = self.cursor.peek()
        if tok.kind == "ENDMARKER" or tok.kind in ("NEWLINE", "NL", "DEDENT", "INDENT"):
            return None
        if tok.kind == "NAME":
            if tok.text in ("and", "or"):
                return INFIX_BP[tok.text][0]
            if tok.text == "if":
                return BP_TERNARY
            if tok.text in ("in", "not", "is"):
                return BP_COMPARE
            if tok.text == ":=":
                return BP_WALRUS
            return None
        if tok.kind == "OP":
            if tok.text in INFIX_BP:
                return INFIX_BP[tok.text][0]
            if tok.text in COMPARE_OPS:
                return BP_COMPARE
            if tok.text == "(":
                return BP_CALL
            if tok.text == "[":
                return BP_INDEX
            if tok.text == ".":
                return BP_ATTR
            if tok.text == ":=":
                return BP_WALRUS
        return None

    def _parse_infix(self, left: Expression, min_bp: int) -> Expression:
        tok = self.cursor.peek()
        # Attribute access
        if tok.kind == "OP" and tok.text == ".":
            if BP_ATTR <= min_bp:
                return left
            self.cursor.advance()
            name_tok = self.cursor.expect("NAME", msg="expected attribute name after '.'")
            attr = AttributeExpr(span=self.cursor.span_from(tok), object=left, attr_name=name_tok.text)
            # Check for method call
            if not self.cursor.at_end() and self.cursor.peek().text == "(":
                return self._parse_call_tail(attr, tok, is_method=True, method_name=name_tok.text, obj=left)
            return attr
        # Call
        if tok.kind == "OP" and tok.text == "(":
            if BP_CALL <= min_bp:
                return left
            return self._parse_call_tail(left, tok)
        # Index / Slice
        if tok.kind == "OP" and tok.text == "[":
            if BP_INDEX <= min_bp:
                return left
            return self._parse_index(left, tok)
        # Walrus
        if tok.text == ":=" and isinstance(left, NameExpr):
            if BP_WALRUS <= min_bp:
                return left
            self.cursor.advance()
            value = self.parse_expression(BP_WALRUS)
            return NamedExpr(span=self.cursor.span_from(tok), target=left.name, value=value)
        # Ternary
        if tok.kind == "NAME" and tok.text == "if":
            if BP_TERNARY <= min_bp:
                return left
            self.cursor.advance()
            condition = self.parse_expression(BP_TERNARY)
            self.cursor.expect("NAME", "else", msg="expected 'else' in conditional expression")
            orelse = self.parse_expression(BP_TERNARY)
            return IfExpr(span=self.cursor.span_from(tok), condition=condition, body=left, orelse=orelse)
        # Comparisons (chained)
        if self._is_compare_op(tok):
            if BP_COMPARE <= min_bp:
                return left
            return self._parse_compare_chain(left)
        # Binary / boolean ops
        text = tok.text
        if text in INFIX_BP:
            lbp, rbp = INFIX_BP[text]
            if lbp <= min_bp:
                return left
            self.cursor.advance()
            right = self.parse_expression(rbp)
            span = self.cursor.span_from(tok)
            if text in ("and", "or"):
                return BoolOpExpr(span=span, op=text, left=left, right=right)
            return BinaryExpr(span=span, op=text, left=left, right=right)
        if tok.kind == "NAME" and text in ("and", "or"):
            lbp, rbp = INFIX_BP[text]
            if lbp <= min_bp:
                return left
            self.cursor.advance()
            right = self.parse_expression(rbp)
            return BoolOpExpr(span=self.cursor.span_from(tok), op=text, left=left, right=right)
        return left

    def _is_compare_op(self, tok) -> bool:
        if tok.text in ("==", "!=", "<", ">", "<=", ">="):
            return True
        if tok.kind == "NAME" and tok.text in ("in", "is", "not"):
            return True
        return False

    def _get_compare_op(self) -> str:
        tok = self.cursor.peek()
        if tok.text in ("==", "!=", "<", ">", "<=", ">="):
            self.cursor.advance()
            return tok.text
        if tok.kind == "NAME" and tok.text == "in":
            self.cursor.advance()
            return "in"
        if tok.kind == "NAME" and tok.text == "is":
            self.cursor.advance()
            if self.cursor.peek().text == "not":
                self.cursor.advance()
                return "is not"
            return "is"
        if tok.kind == "NAME" and tok.text == "not":
            self.cursor.advance()
            self.cursor.expect("NAME", "in", msg="expected 'in' after 'not'")
            return "not in"
        raise ParseError(f"expected comparison operator", tok.line, tok.column)

    def _parse_compare_chain(self, left: Expression) -> Expression:
        ops: list[str] = []
        operands: list[Expression] = [left]
        while not self.cursor.at_end() and self._is_compare_op(self.cursor.peek()):
            op = self._get_compare_op()
            ops.append(op)
            operands.append(self.parse_expression(BP_COMPARE))
        if len(ops) == 1:
            return CompareExpr(span=operands[0].span, op=ops[0], left=operands[0], right=operands[1])
        return CompareChainExpr(span=operands[0].span, operands=operands, ops=ops)

    # ── Call / Method ───────────────────────────────────────────────

    def _parse_call_tail(self, callee: Expression, start_tok, is_method: bool = False, method_name: str = "", obj: Expression | None = None) -> Expression:
        self.cursor.advance()  # consume '('
        args, kwargs, kw_starred = self._parse_arguments()
        self.cursor.expect("OP", ")", msg="expected ')' after arguments")
        span = self.cursor.span_from(start_tok)
        if is_method and obj is not None:
            return MethodCallExpr(span=span, object=obj, method_name=method_name, args=args, kwargs=kwargs, kw_starred=kw_starred)
        if isinstance(callee, NameExpr):
            return CallExpr(span=span, func_name=callee.name, args=args, kwargs=kwargs, kw_starred=kw_starred)
        return CallValueExpr(span=span, callee=callee, args=args, kwargs=kwargs, kw_starred=kw_starred)

    def _parse_arguments(self) -> tuple[list[Expression], dict[str, Expression], list[KwStarredExpr]]:
        args: list[Expression] = []
        kwargs: dict[str, Expression] = {}
        kw_starred: list[KwStarredExpr] = []
        while not self.cursor.at_end() and self.cursor.peek().text != ")":
            tok = self.cursor.peek()
            # **kwargs splat
            if tok.text == "**":
                self.cursor.advance()
                value = self.parse_expression(BP_TERNARY + 1)
                kw_starred.append(KwStarredExpr(span=self.cursor.span_from(tok), value=value))
            # keyword=value
            elif tok.kind == "NAME" and self.cursor.peek_next().text == "=":
                name = self.cursor.advance().text
                self.cursor.advance()  # '='
                value = self.parse_expression(BP_TERNARY + 1)
                kwargs[name] = value
            else:
                args.append(self.parse_expression(BP_TERNARY + 1))
            if self.cursor.peek().text == ",":
                self.cursor.advance()
        return args, kwargs, kw_starred

    # ── Index / Slice ───────────────────────────────────────────────

    def _parse_index(self, collection: Expression, start_tok) -> Expression:
        self.cursor.advance()  # consume '['
        index = self._parse_slice_or_expr()
        self.cursor.expect("OP", "]", msg="expected ']' after index")
        return IndexExpr(span=self.cursor.span_from(start_tok), collection=collection, index=index)

    def _parse_slice_or_expr(self) -> Expression:
        tok = self.cursor.peek()
        if tok.text == ":":
            return self._parse_slice(None)
        expr = self.parse_expression()
        if self.cursor.peek().text == ":":
            return self._parse_slice(expr)
        return expr

    def _parse_slice(self, lower: Expression | None) -> Expression:
        start = self.cursor.peek()
        self.cursor.advance()  # consume ':'
        upper = None
        if self.cursor.peek().text not in ("]", ":"):
            upper = self.parse_expression()
        step = None
        if self.cursor.peek().text == ":":
            self.cursor.advance()
            if self.cursor.peek().text != "]":
                step = self.parse_expression()
        return SliceExpr(span=self.cursor.span_from(start), lower=lower, upper=upper, step=step)

    # ── Parenthesized / Tuple ───────────────────────────────────────

    def _parse_paren(self) -> Expression:
        start = self.cursor.advance()  # '('
        if self.cursor.peek().text == ")":
            self.cursor.advance()
            return TupleExpr(span=self.cursor.span_from(start), elements=[])
        # Comprehension inside parens not supported; parse as expr/tuple
        first = self.parse_expression()
        if self.cursor.peek().text == ",":
            elements = [first]
            while self.cursor.peek().text == ",":
                self.cursor.advance()
                if self.cursor.peek().text == ")":
                    break
                elements.append(self.parse_expression())
            self.cursor.expect("OP", ")", msg="expected ')' after tuple")
            return TupleExpr(span=self.cursor.span_from(start), elements=elements)
        self.cursor.expect("OP", ")", msg="expected ')'")
        return first

    # ── List ────────────────────────────────────────────────────────

    def _parse_list(self) -> Expression:
        start = self.cursor.advance()  # '['
        if self.cursor.peek().text == "]":
            self.cursor.advance()
            return ListExpr(span=self.cursor.span_from(start), elements=[])
        first = self.parse_expression()
        # List comprehension
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "for":
            generators = self._parse_comprehension_generators()
            self.cursor.expect("OP", "]", msg="expected ']' after list comprehension")
            return ListCompExpr(span=self.cursor.span_from(start), element=first, generators=generators)
        elements = [first]
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            if self.cursor.peek().text == "]":
                break
            elements.append(self.parse_expression())
        self.cursor.expect("OP", "]", msg="expected ']'")
        return ListExpr(span=self.cursor.span_from(start), elements=elements)

    # ── Dict / Set ──────────────────────────────────────────────────

    def _parse_dict_or_set(self) -> Expression:
        start = self.cursor.advance()  # '{'
        if self.cursor.peek().text == "}":
            self.cursor.advance()
            return DictExpr(span=self.cursor.span_from(start), keys=[], values=[])
        first = self.parse_expression()
        # Dict
        if self.cursor.peek().text == ":":
            self.cursor.advance()
            first_val = self.parse_expression()
            # Dict comprehension
            if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "for":
                generators = self._parse_comprehension_generators()
                self.cursor.expect("OP", "}", msg="expected '}' after dict comprehension")
                return DictCompExpr(span=self.cursor.span_from(start), key=first, value=first_val, generators=generators)
            keys, values = [first], [first_val]
            while self.cursor.peek().text == ",":
                self.cursor.advance()
                if self.cursor.peek().text == "}":
                    break
                keys.append(self.parse_expression())
                self.cursor.expect("OP", ":", msg="expected ':' in dict literal")
                values.append(self.parse_expression())
            self.cursor.expect("OP", "}", msg="expected '}'")
            return DictExpr(span=self.cursor.span_from(start), keys=keys, values=values)
        # Set comprehension
        if self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "for":
            generators = self._parse_comprehension_generators()
            self.cursor.expect("OP", "}", msg="expected '}' after set comprehension")
            return SetCompExpr(span=self.cursor.span_from(start), element=first, generators=generators)
        # Set literal
        elements = [first]
        while self.cursor.peek().text == ",":
            self.cursor.advance()
            if self.cursor.peek().text == "}":
                break
            elements.append(self.parse_expression())
        self.cursor.expect("OP", "}", msg="expected '}'")
        return SetExpr(span=self.cursor.span_from(start), elements=elements)

    # ── Comprehension generators ────────────────────────────────────

    def _parse_comprehension_generators(self) -> list[Comprehension]:
        generators: list[Comprehension] = []
        while self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "for":
            start = self.cursor.advance()  # 'for'
            target_tok = self.cursor.expect("NAME", msg="expected loop variable in comprehension")
            self.cursor.expect("NAME", "in", msg="expected 'in' in comprehension")
            iterator = self.parse_expression(BP_TERNARY + 1)
            ifs: list[Expression] = []
            while self.cursor.peek().kind == "NAME" and self.cursor.peek().text == "if":
                self.cursor.advance()
                ifs.append(self.parse_expression(BP_TERNARY + 1))
            generators.append(Comprehension(
                span=self.cursor.span_from(start),
                target=target_tok.text,
                iterator=iterator,
                ifs=ifs,
            ))
        return generators

    # ── Lambda ──────────────────────────────────────────────────────

    def _parse_lambda(self) -> Expression:
        start = self.cursor.advance()  # 'lambda'
        self._lambda_counter += 1
        name = f"<lambda_{self._lambda_counter}>"
        params, defaults, kwonly_params, kwonly_defaults, vararg, kwarg = self._parse_lambda_params()
        self.cursor.expect("OP", ":", msg="expected ':' after lambda parameters")
        body_expr = self.parse_expression()
        ret = ReturnStmt(span=self.cursor.span_from(start), value=body_expr)
        func_def = FunctionDef(
            span=self.cursor.span_from(start), name=name, params=params,
            body=[ret], defaults=defaults, kwonly_params=kwonly_params,
            kwonly_defaults=kwonly_defaults, vararg=vararg, kwarg=kwarg,
        )
        return LambdaExpr(span=self.cursor.span_from(start), func_def=func_def)

    def _parse_lambda_params(self):
        params, defaults = [], []
        kwonly_params, kwonly_defaults = [], {}
        vararg, kwarg = None, None
        if self.cursor.peek().text == ":":
            return params, defaults, kwonly_params, kwonly_defaults, vararg, kwarg
        seen_star = False
        while self.cursor.peek().text != ":":
            if self.cursor.peek().text == "**":
                self.cursor.advance()
                kwarg = self.cursor.expect("NAME").text
            elif self.cursor.peek().text == "*":
                self.cursor.advance()
                if self.cursor.peek().kind == "NAME" and self.cursor.peek().text != "," and self.cursor.peek().text != ":":
                    vararg = self.cursor.advance().text
                seen_star = True
            elif self.cursor.peek().kind == "NAME":
                p = self.cursor.advance().text
                if seen_star:
                    kwonly_params.append(p)
                    if self.cursor.peek().text == "=":
                        self.cursor.advance()
                        kwonly_defaults[p] = self.parse_expression(BP_TERNARY + 1)
                else:
                    params.append(p)
                    if self.cursor.peek().text == "=":
                        self.cursor.advance()
                        defaults.append(self.parse_expression(BP_TERNARY + 1))
            if self.cursor.peek().text == ",":
                self.cursor.advance()
            else:
                break
        return params, defaults, kwonly_params, kwonly_defaults, vararg, kwarg
