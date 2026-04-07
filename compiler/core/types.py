"""
types.py — Type system for the compiler.
Defines type objects used in semantic analysis and type checking.
"""


class Type:
    """Base class for all types."""
    def __eq__(self, other):
        return type(self) == type(other)
    def __hash__(self):
        return hash(type(self).__name__)
    def __repr__(self):
        return self.__class__.__name__


class IntType(Type):
    """Integer type (maps to C int/double)."""
    pass

class FloatType(Type):
    """Float type (maps to C double)."""
    pass

class BoolType(Type):
    """Boolean type (maps to C int: 0/1)."""
    pass

class StringType(Type):
    """String type (maps to C char*)."""
    pass

class VoidType(Type):
    """Void type (for functions with no return)."""
    pass

class FunctionType(Type):
    """Function type: stores parameter types and return type."""
    def __init__(self, param_types, return_type):
        self.param_types = param_types
        self.return_type = return_type

    def __repr__(self):
        params = ', '.join(str(p) for p in self.param_types)
        return f'({params}) -> {self.return_type}'


# Singleton instances for convenience
INT = IntType()
FLOAT = FloatType()
BOOL = BoolType()
STRING = StringType()
VOID = VoidType()


def is_numeric(t):
    """Check if a type is numeric (int or float)."""
    return isinstance(t, (IntType, FloatType))

def common_type(a, b):
    """Return the wider numeric type (int+float → float)."""
    if isinstance(a, FloatType) or isinstance(b, FloatType):
        return FLOAT
    return INT
