from __future__ import annotations

import ast

from compiler.core.ast import (
    AssignStmt,
    AttributeAssignStmt,
    AttributeExpr,
    BinaryExpr,
    BoolOpExpr,
    CallExpr,
    CallValueExpr,
    ClassDef,
    Comprehension,
    CompareExpr,
    CompareChainExpr,
    ConstantExpr,
    DeleteStmt,
    DictExpr,
    DictCompExpr,
    ExceptHandler,
    ExprStmt,
    ForStmt,
    FromImportStmt,
    FunctionDef,
    GlobalStmt,
    IfStmt,
    IfExpr,
    ImportStmt,
    IndexExpr,
    LambdaExpr,
    ListExpr,
    ListCompExpr,
    MethodCallExpr,
    NameExpr,
    NonlocalStmt,
    PassStmt,
    PrintStmt,
    Program,
    RaiseStmt,
    ReturnStmt,
    SetExpr,
    SetCompExpr,
    SliceExpr,
    StarredExpr,
    KwStarredExpr,
    NamedExpr,
    SourceSpan,
    StarUnpackAssignStmt,
    TryStmt,
    TupleExpr,
    UnaryExpr,
    UnpackAssignStmt,
    StarUnpackAssignStmt,
    WhileStmt,
    WithStmt,
    BreakStmt,
    ContinueStmt,
)
from compiler.frontend.cst import ParsedModule
from compiler.utils.error_handler import ErrorHandler


class PythonSubsetLowerer:
    def __init__(self, errors: ErrorHandler):
        self.errors = errors
        self._function_depth = 0
        self._lambda_counter = 0

    def lower(self, module: ParsedModule) -> Program | None:
        body = self._lower_body(module.syntax_tree.body, allow_docstring=True)
        if body is None or self.errors.has_errors():
            return None
        return Program(span=self._span(module.syntax_tree), body=body)

    def _lower_body(self, statements: list[ast.stmt], allow_docstring: bool = False) -> list | None:
        lowered = []
        for index, statement in enumerate(statements):
            if allow_docstring and index == 0 and self._is_docstring(statement):
                continue
            item = self._lower_statement(statement)
            if isinstance(item, list):
                lowered.extend(node for node in item if node is not None)
            elif item is not None:
                lowered.append(item)
        return lowered

    def _lower_statement(self, node: ast.stmt):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                self._unsupported(node, "only single-target assignment is supported")
                return None
            target = node.targets[0]
            value = self._lower_expr(node.value)
            if value is None:
                return None
            if isinstance(target, ast.Name):
                return AssignStmt(span=self._span(node), name=target.id, value=value)
            if isinstance(target, ast.Attribute):
                obj = self._lower_expr(target.value)
                if obj is None:
                    return None
                return AttributeAssignStmt(span=self._span(node), object=obj, attr_name=target.attr, value=value)
            if isinstance(target, (ast.Tuple, ast.List)):
                starred_indices = [
                    i for i, element in enumerate(target.elts)
                    if isinstance(element, ast.Starred)
                ]
                if starred_indices:
                    if len(starred_indices) != 1:
                        self._unsupported(node, "only a single starred assignment target is supported")
                        return None
                    star_index = starred_indices[0]
                    star_element = target.elts[star_index]
                    assert isinstance(star_element, ast.Starred)
                    if not isinstance(star_element.value, ast.Name):
                        self._unsupported(node, "only simple names may be starred in assignment")
                        return None

                    prefix = target.elts[:star_index]
                    suffix = target.elts[star_index + 1 :]
                    if not all(isinstance(element, ast.Name) for element in prefix + suffix):
                        self._unsupported(node, "only simple names in unpacking assignment are supported")
                        return None

                    return StarUnpackAssignStmt(
                        span=self._span(node),
                        prefix_targets=[element.id for element in prefix],
                        starred_target=star_element.value.id,
                        suffix_targets=[element.id for element in suffix],
                        value=value,
                    )

                if not all(isinstance(element, ast.Name) for element in target.elts):
                    self._unsupported(node, "only simple names in unpacking assignment are supported")
                    return None
                return UnpackAssignStmt(
                    span=self._span(node),
                    targets=[element.id for element in target.elts],
                    value=value,
                )
            self._unsupported(node, "only simple name or attribute assignment is supported")
            return None

        if isinstance(node, ast.AugAssign):
            if not isinstance(node.target, ast.Name):
                self._unsupported(node, "only simple name augmented assignment is supported")
                return None
            operator = self._binop_symbol(node.op)
            if operator is None:
                self._unsupported(node, "unsupported augmented assignment operator")
                return None
            right = self._lower_expr(node.value)
            if right is None:
                return None
            left = NameExpr(span=self._span(node.target), name=node.target.id)
            value = BinaryExpr(span=self._span(node), op=operator, left=left, right=right)
            return AssignStmt(span=self._span(node), name=node.target.id, value=value)

        if isinstance(node, ast.Expr):
            if self._is_docstring(node):
                return None
            if self._is_print_call(node.value):
                return self._lower_print_statement(node)
            expr = self._lower_expr(node.value)
            if expr is None:
                return None
            return ExprStmt(span=self._span(node), expr=expr)

        if isinstance(node, ast.Pass):
            return PassStmt(span=self._span(node))

        if isinstance(node, ast.Delete):
            targets = []
            for target in node.targets:
                lowered = self._lower_delete_target(target)
                if lowered is None:
                    return None
                targets.append(lowered)
            return DeleteStmt(span=self._span(node), targets=targets)

        if isinstance(node, ast.Global):
            return GlobalStmt(span=self._span(node), names=list(node.names))

        if isinstance(node, ast.Nonlocal):
            return NonlocalStmt(span=self._span(node), names=list(node.names))

        if isinstance(node, ast.With):
            body = self._lower_body(node.body, allow_docstring=True) or []
            for item in reversed(node.items):
                context_expr = self._lower_expr(item.context_expr)
                if context_expr is None:
                    return None
                optional_var = None
                if item.optional_vars is not None:
                    if not isinstance(item.optional_vars, ast.Name):
                        self._unsupported(item.optional_vars, "only simple name targets in with-as clauses are supported")
                        return None
                    optional_var = item.optional_vars.id
                body = [WithStmt(span=self._span(item), context_expr=context_expr, optional_var=optional_var, body=body)]
            return body[0]

        if isinstance(node, ast.If):
            condition = self._lower_expr(node.test)
            if condition is None:
                return None
            body = self._lower_body(node.body, allow_docstring=True) or []
            orelse = self._lower_body(node.orelse, allow_docstring=True) or []
            return IfStmt(span=self._span(node), condition=condition, body=body, orelse=orelse)

        if isinstance(node, ast.Assert):
            # Desugar: assert cond, msg  ->  if not cond: raise AssertionError(msg)
            condition = self._lower_expr(node.test)
            if condition is None:
                return None
            negated = UnaryExpr(span=self._span(node), op="not", operand=condition)
            if node.msg is not None:
                msg = self._lower_expr(node.msg)
                if msg is None:
                    return None
                error_call = CallExpr(span=self._span(node), func_name="AssertionError", args=[msg])
            else:
                error_call = CallExpr(span=self._span(node), func_name="AssertionError", args=[
                    ConstantExpr(span=self._span(node), value="assertion failed")
                ])
            raise_stmt = RaiseStmt(span=self._span(node), value=error_call)
            return IfStmt(span=self._span(node), condition=negated, body=[raise_stmt], orelse=[])

        if isinstance(node, ast.While):
            condition = self._lower_expr(node.test)
            if condition is None:
                return None
            body = self._lower_body(node.body, allow_docstring=True) or []
            orelse = self._lower_body(node.orelse, allow_docstring=True) or []
            return WhileStmt(span=self._span(node), condition=condition, body=body, orelse=orelse)

        if isinstance(node, ast.For):
            target: str | list[str]
            if isinstance(node.target, ast.Name):
                target = node.target.id
            elif isinstance(node.target, (ast.Tuple, ast.List)):
                if any(isinstance(element, ast.Starred) for element in node.target.elts):
                    self._unsupported(node, "starred assignment is not supported yet")
                    return None
                if not all(isinstance(element, ast.Name) for element in node.target.elts):
                    self._unsupported(node, "only simple name loop targets are supported")
                    return None
                target = [element.id for element in node.target.elts]
            else:
                self._unsupported(node, "only simple name loop targets are supported")
                return None
            iterator = self._lower_expr(node.iter)
            if iterator is None:
                return None
            body = self._lower_body(node.body, allow_docstring=True) or []
            orelse = self._lower_body(node.orelse, allow_docstring=True) or []
            return ForStmt(span=self._span(node), target=target, iterator=iterator, body=body, orelse=orelse)

        if isinstance(node, ast.FunctionDef):
            if node.returns is not None:
                self._unsupported(node, "function return annotations are not supported")
                return None
            if node.args.posonlyargs:
                self._unsupported(node, "positional-only parameters are not supported")
                return None
            if any(arg.annotation is not None for arg in node.args.args + node.args.kwonlyargs):
                self._unsupported(node, "parameter annotations are not supported")
                return None
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                self._unsupported(node, "parameter annotations are not supported")
                return None
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                self._unsupported(node, "parameter annotations are not supported")
                return None
            defaults = [self._lower_expr(default) for default in node.args.defaults]
            if any(default is None for default in defaults):
                return None
            kwonly_defaults = {}
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if default is None:
                    continue
                lowered_default = self._lower_expr(default)
                if lowered_default is None:
                    return None
                kwonly_defaults[arg.arg] = lowered_default
            self._function_depth += 1
            body = self._lower_body(node.body, allow_docstring=True) or []
            self._function_depth -= 1
            function_def = FunctionDef(
                span=self._span(node),
                name=node.name,
                params=[arg.arg for arg in node.args.args],
                body=body,
                defaults=defaults,
                kwonly_params=[arg.arg for arg in node.args.kwonlyargs],
                kwonly_defaults=kwonly_defaults,
                vararg=node.args.vararg.arg if node.args.vararg is not None else None,
                kwarg=node.args.kwarg.arg if node.args.kwarg is not None else None,
            )
            if not node.decorator_list:
                return function_def
            decorated = self._apply_decorators(node.name, node.decorator_list, self._span(node))
            if decorated is None:
                return None
            return [function_def, *decorated]

        if isinstance(node, ast.ClassDef):
            if self._function_depth > 0:
                self._unsupported(node, "nested classes are not supported yet")
                return None
            if node.keywords:
                self._unsupported(node, "class keywords are not supported yet")
                return None
            bases = [self._lower_expr(base) for base in node.bases]
            if any(base is None for base in bases):
                return None
            attributes = []
            methods = []
            for child in node.body:
                if self._is_docstring(child) or isinstance(child, ast.Pass):
                    continue
                if isinstance(child, ast.Assign):
                    lowered = self._lower_statement(child)
                    if lowered is None:
                        return None
                    if not isinstance(lowered, AssignStmt):
                        self._unsupported(child, "class assignments must target simple names")
                        return None
                    attributes.append(lowered)
                    continue
                if not isinstance(child, ast.FunctionDef):
                    self._unsupported(child, "class bodies may only contain methods or simple assignments")
                    return None
                lowered = self._lower_statement(child)
                if lowered is None or not isinstance(lowered, FunctionDef):
                    return None
                methods.append(lowered)
            class_def = ClassDef(
                span=self._span(node),
                name=node.name,
                bases=bases,
                attributes=attributes,
                methods=methods,
            )
            if not node.decorator_list:
                return class_def
            decorated = self._apply_decorators(node.name, node.decorator_list, self._span(node))
            if decorated is None:
                return None
            return [class_def, *decorated]

        if isinstance(node, ast.Import):
            lowered = []
            for alias in node.names:
                lowered.append(ImportStmt(span=self._span(node), module=alias.name, alias=alias.asname))
            return lowered

        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is None:
                self._unsupported(node, "missing import module is not supported")
                return None
            lowered = []
            for alias in node.names:
                lowered.append(
                    FromImportStmt(
                        span=self._span(node),
                        module=node.module,
                        name=alias.name,
                        alias=alias.asname,
                        level=node.level,
                    )
                )
            return lowered

        if isinstance(node, ast.Raise):
            value = self._lower_expr(node.exc) if node.exc is not None else None
            if node.exc is not None and value is None:
                return None

            cause = self._lower_expr(node.cause) if node.cause is not None else None
            if node.cause is not None and cause is None:
                return None

            return RaiseStmt(span=self._span(node), value=value, cause=cause)

        if isinstance(node, ast.Return):
            value = self._lower_expr(node.value) if node.value is not None else None
            if node.value is not None and value is None:
                return None
            return ReturnStmt(span=self._span(node), value=value)

        if isinstance(node, ast.NamedExpr):
            if not isinstance(node.target, ast.Name):
                self._unsupported(node, "only simple name targets are supported for :=")
                return None
            value = self._lower_expr(node.value)
            if value is None:
                return None
            return NamedExpr(
                span=self._span(node),
                target=node.target.id,
                value=value,
            )
        if isinstance(node, ast.Try):
            if not node.handlers and not node.finalbody:
                self._unsupported(node, "try without except or finally is not supported")
                return None
            handlers = []
            for handler in node.handlers:
                type_name = None
                if handler.type is not None:
                    if not isinstance(handler.type, ast.Name):
                        self._unsupported(handler, "only named exception handlers are supported")
                        return None
                    type_name = handler.type.id
                lowered_body = self._lower_body(handler.body, allow_docstring=True) or []
                handlers.append(ExceptHandler(span=self._span(handler), type_name=type_name, name=handler.name, body=lowered_body))
            body = self._lower_body(node.body, allow_docstring=True) or []
            orelse = self._lower_body(node.orelse, allow_docstring=True) or []
            finalbody = self._lower_body(node.finalbody, allow_docstring=True) or []
            return TryStmt(span=self._span(node), body=body, handlers=handlers, orelse=orelse, finalbody=finalbody)

        if isinstance(node, ast.Break):
            return BreakStmt(span=self._span(node))

        if isinstance(node, ast.Continue):
            return ContinueStmt(span=self._span(node))

        self._unsupported(node, f"{type(node).__name__} is not supported")
        return None

    def _lower_expr(self, node: ast.expr):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return ConstantExpr(span=self._span(node), value=node.value)
            if isinstance(node.value, int):
                return ConstantExpr(span=self._span(node), value=node.value)
            if isinstance(node.value, float):
                return ConstantExpr(span=self._span(node), value=node.value)
            if isinstance(node.value, str):
                return ConstantExpr(span=self._span(node), value=node.value)
            self._unsupported(node, f"constant {node.value!r} is not supported")
            return None

        if isinstance(node, ast.JoinedStr):
            if not node.values:
                return ConstantExpr(span=self._span(node), value="")
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant):
                    parts.append(ConstantExpr(span=self._span(value), value=str(value.value)))
                    continue
                if isinstance(value, ast.FormattedValue):
                    inner = self._lower_expr(value.value)
                    if inner is None:
                        return None
                    if value.conversion == ord("r"):
                        inner = CallExpr(span=self._span(value), func_name="repr", args=[inner])
                    elif value.conversion == ord("a"):
                        inner = CallExpr(span=self._span(value), func_name="ascii", args=[inner])
                    else:
                        inner = CallExpr(span=self._span(value), func_name="str", args=[inner])
                    parts.append(inner)
                    continue
                self._unsupported(node, f"unsupported f-string component {type(value).__name__}")
                return None
            expr = parts[0]
            for part in parts[1:]:
                expr = BinaryExpr(span=self._span(node), op="+", left=expr, right=part)
            return expr

        if isinstance(node, ast.Name):
            return NameExpr(span=self._span(node), name=node.id)

        if isinstance(node, ast.BinOp):
            operator = self._binop_symbol(node.op)
            if operator is None:
                self._unsupported(node, "unsupported binary operator")
                return None
            left = self._lower_expr(node.left)
            right = self._lower_expr(node.right)
            if left is None or right is None:
                return None
            return BinaryExpr(span=self._span(node), op=operator, left=left, right=right)

        if isinstance(node, ast.UnaryOp):
            operator = self._unary_symbol(node.op)
            if operator is None:
                self._unsupported(node, "unsupported unary operator")
                return None
            operand = self._lower_expr(node.operand)
            if operand is None:
                return None
            return UnaryExpr(span=self._span(node), op=operator, operand=operand)

        if isinstance(node, ast.BoolOp):
            operator = self._boolop_symbol(node.op)
            if operator is None:
                self._unsupported(node, "unsupported boolean operator")
                return None
            values = [self._lower_expr(value) for value in node.values]
            if any(value is None for value in values):
                return None
            expr = values[0]
            for value in values[1:]:
                expr = BoolOpExpr(span=self._span(node), op=operator, left=expr, right=value)
            return expr

        if isinstance(node, ast.Compare):
            left = self._lower_expr(node.left)
            comparators = [self._lower_expr(comparator) for comparator in node.comparators]
            operators = [self._compare_symbol(operator) for operator in node.ops]
            if any(operator is None for operator in operators):
                self._unsupported(node, "unsupported comparison operator")
                return None
            if left is None or any(comparator is None for comparator in comparators):
                return None
            if len(operators) == 1:
                return CompareExpr(span=self._span(node), op=operators[0], left=left, right=comparators[0])
            return CompareChainExpr(span=self._span(node), operands=[left, *comparators], ops=operators)

        if isinstance(node, ast.Call):
            args = []
            for arg in node.args:
                if isinstance(arg, ast.Starred):
                    lowered = self._lower_expr(arg.value)
                    if lowered is None:
                        return None
                    args.append(StarredExpr(span=self._span(arg), value=lowered))
                    continue
                lowered = self._lower_expr(arg)
                if lowered is None:
                    return None
                args.append(lowered)
            if any(arg is None for arg in args):
                return None
            kwargs = {}
            kw_starred = []
            for keyword in node.keywords:
                lowered_value = self._lower_expr(keyword.value)
                if lowered_value is None:
                    return None
                if keyword.arg is None:
                    kw_starred.append(KwStarredExpr(span=self._span(keyword), value=lowered_value))
                else:
                    kwargs[keyword.arg] = lowered_value
            if isinstance(node.func, ast.Name):
                return CallExpr(span=self._span(node), func_name=node.func.id, args=args, kwargs=kwargs, kw_starred=kw_starred)
            if isinstance(node.func, ast.Attribute):
                obj = self._lower_expr(node.func.value)
                if obj is None:
                    return None
                return MethodCallExpr(span=self._span(node), object=obj, method_name=node.func.attr, args=args, kwargs=kwargs, kw_starred=kw_starred)
            callee = self._lower_expr(node.func)
            if callee is None:
                return None
            return CallValueExpr(span=self._span(node), callee=callee, args=args, kwargs=kwargs, kw_starred=kw_starred)

        if isinstance(node, ast.NamedExpr):
            if not isinstance(node.target, ast.Name):
                self._unsupported(node, "only simple name targets are supported for :=")
                return None
            value = self._lower_expr(node.value)
            if value is None:
                return None
            return NamedExpr(span=self._span(node), target=node.target.id, value=value)

        if isinstance(node, ast.List):
            elements = [self._lower_expr(element) for element in node.elts]
            if any(element is None for element in elements):
                return None
            return ListExpr(span=self._span(node), elements=elements)

        if isinstance(node, ast.Tuple):
            elements = [self._lower_expr(element) for element in node.elts]
            if any(element is None for element in elements):
                return None
            return TupleExpr(span=self._span(node), elements=elements)

        if isinstance(node, ast.Dict):
            keys = []
            values = []
            for key, value in zip(node.keys, node.values):
                if key is None:
                    self._unsupported(node, "dict unpacking (**) is not supported yet")
                    return None
                lowered_key = self._lower_expr(key)
                lowered_value = self._lower_expr(value)
                if lowered_key is None or lowered_value is None:
                    return None
                keys.append(lowered_key)
                values.append(lowered_value)
            return DictExpr(span=self._span(node), keys=keys, values=values)

        if isinstance(node, ast.Set):
            elements = [self._lower_expr(element) for element in node.elts]
            if any(element is None for element in elements):
                return None
            return SetExpr(span=self._span(node), elements=elements)

        if isinstance(node, ast.ListComp):
            element = self._lower_expr(node.elt)
            generators = self._lower_comprehensions(node.generators)
            if element is None or generators is None:
                return None
            return ListCompExpr(span=self._span(node), element=element, generators=generators)

        if isinstance(node, ast.SetComp):
            element = self._lower_expr(node.elt)
            generators = self._lower_comprehensions(node.generators)
            if element is None or generators is None:
                return None
            return SetCompExpr(span=self._span(node), element=element, generators=generators)

        if isinstance(node, ast.DictComp):
            key = self._lower_expr(node.key)
            value = self._lower_expr(node.value)
            generators = self._lower_comprehensions(node.generators)
            if key is None or value is None or generators is None:
                return None
            return DictCompExpr(span=self._span(node), key=key, value=value, generators=generators)

        if isinstance(node, ast.Subscript):
            collection = self._lower_expr(node.value)
            if isinstance(node.slice, ast.Slice):
                index = self._lower_slice(node.slice)
            else:
                index = self._lower_expr(node.slice)
            if collection is None or index is None:
                return None
            return IndexExpr(span=self._span(node), collection=collection, index=index)

        if isinstance(node, ast.Attribute):
            obj = self._lower_expr(node.value)
            if obj is None:
                return None
            return AttributeExpr(span=self._span(node), object=obj, attr_name=node.attr)

        if isinstance(node, ast.IfExp):
            condition = self._lower_expr(node.test)
            body = self._lower_expr(node.body)
            orelse = self._lower_expr(node.orelse)
            if condition is None or body is None or orelse is None:
                return None
            return IfExpr(span=self._span(node), condition=condition, body=body, orelse=orelse)

        if isinstance(node, ast.Lambda):
            self._lambda_counter += 1
            name = f"<lambda_{self._lambda_counter}>"
            if node.args.posonlyargs:
                self._unsupported(node, "positional-only parameters are not supported")
                return None
            if any(arg.annotation is not None for arg in node.args.args + node.args.kwonlyargs):
                self._unsupported(node, "parameter annotations are not supported")
                return None
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                self._unsupported(node, "parameter annotations are not supported")
                return None
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                self._unsupported(node, "parameter annotations are not supported")
                return None
            lowered_body = self._lower_expr(node.body)
            if lowered_body is None:
                return None
            return_stmt = ReturnStmt(span=self._span(node), value=lowered_body)
            params = [arg.arg for arg in node.args.args]
            defaults = [self._lower_expr(d) for d in node.args.defaults]
            if any(d is None for d in defaults):
                return None
            kwonly_defaults = {}
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if default is None:
                    continue
                lowered_default = self._lower_expr(default)
                if lowered_default is None:
                    return None
                kwonly_defaults[arg.arg] = lowered_default
            func_def = FunctionDef(
                span=self._span(node),
                name=name,
                params=params,
                body=[return_stmt],
                defaults=defaults,
                kwonly_params=[arg.arg for arg in node.args.kwonlyargs],
                kwonly_defaults=kwonly_defaults,
                vararg=node.args.vararg.arg if node.args.vararg is not None else None,
                kwarg=node.args.kwarg.arg if node.args.kwarg is not None else None,
            )
            return LambdaExpr(span=self._span(node), func_def=func_def)

        self._unsupported(node, f"expression {type(node).__name__} is not supported")
        return None

    def _lower_slice(self, node: ast.Slice) -> SliceExpr | None:
        lower = self._lower_expr(node.lower) if node.lower is not None else None
        upper = self._lower_expr(node.upper) if node.upper is not None else None
        step = self._lower_expr(node.step) if node.step is not None else None
        if (
            (node.lower is not None and lower is None)
            or (node.upper is not None and upper is None)
            or (node.step is not None and step is None)
        ):
            return None
        return SliceExpr(span=self._span(node), lower=lower, upper=upper, step=step)

    def _lower_comprehensions(self, generators: list[ast.comprehension]) -> list[Comprehension] | None:
        lowered: list[Comprehension] = []
        for generator in generators:
            if generator.is_async:
                self._unsupported(generator, "async comprehensions are not supported yet")
                return None
            if not isinstance(generator.target, ast.Name):
                self._unsupported(generator.target, "only simple name comprehension targets are supported")
                return None
            iterator = self._lower_expr(generator.iter)
            if iterator is None:
                return None
            ifs = [self._lower_expr(condition) for condition in generator.ifs]
            if any(condition is None for condition in ifs):
                return None
            lowered.append(
                Comprehension(
                    span=self._span(generator),
                    target=generator.target.id,
                    iterator=iterator,
                    ifs=ifs,
                )
            )
        return lowered

    def _lower_delete_target(self, node: ast.expr):
        if isinstance(node, ast.Name):
            return NameExpr(span=self._span(node), name=node.id)
        if isinstance(node, ast.Subscript):
            collection = self._lower_expr(node.value)
            if isinstance(node.slice, ast.Slice):
                index = self._lower_slice(node.slice)
            else:
                index = self._lower_expr(node.slice)
            if collection is None or index is None:
                return None
            return IndexExpr(span=self._span(node), collection=collection, index=index)
        self._unsupported(node, "only name and subscript delete targets are supported")
        return None

    def _apply_decorators(self, target_name: str, decorators: list[ast.expr], span: SourceSpan) -> list[AssignStmt] | None:
        current: NameExpr | CallValueExpr | CallExpr | MethodCallExpr | AttributeExpr = NameExpr(span=span, name=target_name)
        for decorator in reversed(decorators):
            lowered_decorator = self._lower_expr(decorator)
            if lowered_decorator is None:
                return None
            current = CallValueExpr(span=self._span(decorator), callee=lowered_decorator, args=[current])
        return [AssignStmt(span=span, name=target_name, value=current)]

    @staticmethod
    def _is_print_call(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        )

    def _lower_print_statement(self, node: ast.Expr) -> PrintStmt | None:
        call = node.value
        assert isinstance(call, ast.Call)
        values = [self._lower_expr(arg) for arg in call.args]
        if any(value is None for value in values):
            return None

        sep = None
        end = None
        for keyword in call.keywords:
            if keyword.arg == "sep":
                sep = self._lower_expr(keyword.value)
                if sep is None:
                    return None
                continue
            if keyword.arg == "end":
                end = self._lower_expr(keyword.value)
                if end is None:
                    return None
                continue
            self._unsupported(call, f"print() keyword {keyword.arg!r} is not supported yet")
            return None
        return PrintStmt(span=self._span(node), values=values, sep=sep, end=end)

    @staticmethod
    def _is_docstring(node: ast.stmt) -> bool:
        return isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str)

    @staticmethod
    def _binop_symbol(operator: ast.AST) -> str | None:
        mapping = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
            ast.FloorDiv: "//",
            ast.Pow: "**",
            ast.BitAnd: "&",
            ast.BitOr: "|",
            ast.BitXor: "^",
            ast.LShift: "<<",
            ast.RShift: ">>",
        }
        return mapping.get(type(operator))

    @staticmethod
    def _unary_symbol(operator: ast.AST) -> str | None:
        mapping = {
            ast.USub: "-",
            ast.UAdd: "+",
            ast.Not: "not",
            ast.Invert: "~",
        }
        return mapping.get(type(operator))

    @staticmethod
    def _boolop_symbol(operator: ast.AST) -> str | None:
        mapping = {
            ast.And: "and",
            ast.Or: "or",
        }
        return mapping.get(type(operator))

    @staticmethod
    def _compare_symbol(operator: ast.AST) -> str | None:
        mapping = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.In: "in",
            ast.NotIn: "not in",
            ast.Is: "is",
            ast.IsNot: "is not",
        }
        return mapping.get(type(operator))

    def _unsupported(self, node: ast.AST, message: str) -> None:
        span = self._span(node)
        self.errors.error("Frontend", message, span.line, span.column, span.end_line, span.end_column)

    @staticmethod
    def _span(node: ast.AST) -> SourceSpan:
        return SourceSpan(
            line=getattr(node, "lineno", 1),
            column=getattr(node, "col_offset", 0),
            end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            end_column=getattr(node, "end_col_offset", getattr(node, "col_offset", 0) + 1),
        )


def lower_cst(module: ParsedModule, errors: ErrorHandler) -> Program | None:
    return PythonSubsetLowerer(errors).lower(module)
