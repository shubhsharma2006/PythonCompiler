from __future__ import annotations

from dataclasses import dataclass, field

from compiler.core.types import ValueType


@dataclass(frozen=True)
class SourceSpan:
    line: int = 1
    column: int = 0
    end_line: int = 1
    end_column: int = 0


@dataclass
class Node:
    span: SourceSpan


@dataclass
class Statement(Node):
    pass


@dataclass
class Expression(Node):
    inferred_type: ValueType = field(default=ValueType.UNKNOWN, init=False, repr=False)


@dataclass
class Program(Node):
    body: list[Statement]


@dataclass
class ImportStmt(Statement):
    module: str
    alias: str | None = None


@dataclass
class FromImportStmt(Statement):
    module: str
    name: str
    alias: str | None = None


@dataclass
class FunctionDef(Statement):
    name: str
    params: list[str]
    body: list[Statement]
    defaults: list[Expression] = field(default_factory=list)
    kwonly_params: list[str] = field(default_factory=list)
    kwonly_defaults: dict[str, Expression] = field(default_factory=dict)
    vararg: str | None = None
    kwarg: str | None = None


@dataclass
class ClassDef(Statement):
    name: str
    bases: list[Expression]
    attributes: list[AssignStmt]
    methods: list[FunctionDef]


@dataclass
class AssignStmt(Statement):
    name: str
    value: Expression


@dataclass
class AttributeAssignStmt(Statement):
    object: Expression
    attr_name: str
    value: Expression


@dataclass
class UnpackAssignStmt(Statement):
    targets: list[str]
    value: Expression


@dataclass
class PassStmt(Statement):
    pass


@dataclass
class DeleteStmt(Statement):
    targets: list[Expression]


@dataclass
class GlobalStmt(Statement):
    names: list[str]


@dataclass
class NonlocalStmt(Statement):
    names: list[str]


@dataclass
class WithStmt(Statement):
    context_expr: Expression
    optional_var: str | None
    body: list[Statement]


@dataclass
class PrintStmt(Statement):
    values: list[Expression]
    sep: Expression | None = None
    end: Expression | None = None


@dataclass
class ExprStmt(Statement):
    expr: Expression


@dataclass
class IfStmt(Statement):
    condition: Expression
    body: list[Statement]
    orelse: list[Statement]


@dataclass
class WhileStmt(Statement):
    condition: Expression
    body: list[Statement]
    orelse: list[Statement] = field(default_factory=list)


@dataclass
class ForStmt(Statement):
    target: str
    iterator: Expression
    body: list[Statement]
    orelse: list[Statement] = field(default_factory=list)


@dataclass
class BreakStmt(Statement):
    pass


@dataclass
class ContinueStmt(Statement):
    pass


@dataclass
class ExceptHandler(Node):
    body: list[Statement]
    type_name: str | None = None
    name: str | None = None


@dataclass
class TryStmt(Statement):
    body: list[Statement]
    handlers: list[ExceptHandler]
    finalbody: list[Statement] = field(default_factory=list)


@dataclass
class RaiseStmt(Statement):
    value: Expression


@dataclass
class ReturnStmt(Statement):
    value: Expression | None


@dataclass
class NameExpr(Expression):
    name: str


@dataclass
class ConstantExpr(Expression):
    value: object


@dataclass
class BinaryExpr(Expression):
    op: str
    left: Expression
    right: Expression


@dataclass
class UnaryExpr(Expression):
    op: str
    operand: Expression


@dataclass
class CompareExpr(Expression):
    op: str
    left: Expression
    right: Expression


@dataclass
class BoolOpExpr(Expression):
    op: str
    left: Expression
    right: Expression


@dataclass
class IfExpr(Expression):
    condition: Expression
    body: Expression
    orelse: Expression


@dataclass
class LambdaExpr(Expression):
    func_def: FunctionDef


@dataclass
class CallExpr(Expression):
    func_name: str
    args: list[Expression]
    kwargs: dict[str, Expression] = field(default_factory=dict)


@dataclass
class ListExpr(Expression):
    elements: list[Expression]


@dataclass
class TupleExpr(Expression):
    elements: list[Expression]


@dataclass
class DictExpr(Expression):
    keys: list[Expression]
    values: list[Expression]


@dataclass
class SetExpr(Expression):
    elements: list[Expression]


@dataclass
class Comprehension(Node):
    target: str
    iterator: Expression
    ifs: list[Expression]


@dataclass
class ListCompExpr(Expression):
    element: Expression
    generators: list[Comprehension]


@dataclass
class SetCompExpr(Expression):
    element: Expression
    generators: list[Comprehension]


@dataclass
class DictCompExpr(Expression):
    key: Expression
    value: Expression
    generators: list[Comprehension]


@dataclass
class IndexExpr(Expression):
    collection: Expression
    index: Expression


@dataclass
class SliceExpr(Expression):
    lower: Expression | None
    upper: Expression | None
    step: Expression | None


@dataclass
class AttributeExpr(Expression):
    object: Expression
    attr_name: str


@dataclass
class MethodCallExpr(Expression):
    object: Expression
    method_name: str
    args: list[Expression]
    kwargs: dict[str, Expression] = field(default_factory=dict)
