from dataclasses import dataclass, field
from multimethod import multimeta, multimethod
from typing      import List, Union, Optional

# =====================================================================
# Clases Abstractas
# =====================================================================
class Visitor(metaclass=multimeta):
    pass

@dataclass
class Node:
    def accept(self, v: Visitor, *args, **kwargs):
        return v.visit(self, *args, **kwargs)

@dataclass
class Statement(Node):
    pass

@dataclass
class Expression(Node):
    pass

# =====================================================================
# Definiciones
# =====================================================================
@dataclass
class Program(Statement):
    body: List[Statement] = field(default_factory=list)

# ------------------ Declaraciones ------------------
@dataclass
class Declaration(Statement):
    pass

@dataclass
class VarDecl(Declaration):
    name : str
    type : Expression
    value: Optional[Expression] = None

@dataclass
class ArrayDecl(Declaration):
    name  : str
    type  : Expression
    dims  : List[int]  # dimensiones del arreglo (ej. [3], [3,4])
    value : Optional[List[Expression]] = None

@dataclass
class FuncDecl(Declaration):
    name   : str
    return_type: Expression
    params : List["Param"]
    body   : List[Statement] = field(default_factory=list)

# ------------------ Parámetros ------------------
@dataclass
class Param(Node):
    name: str
    type: Expression

@dataclass
class VarParm(Param):
    pass

@dataclass
class ArrayParm(Param):
    dims: List[int] = field(default_factory=list)

# ------------------ Sentencias ------------------
@dataclass
class IfStmt(Statement):
    cond : Expression
    then : List[Statement]
    else_ : Optional[List[Statement]] = None

@dataclass
class ReturnStmt(Statement):
    value: Optional[Expression] = None

@dataclass
class PrintStmt(Statement):
    value: Expression

@dataclass
class ForStmt(Statement):
    init : Statement
    cond : Expression
    step : Statement
    body : List[Statement]

@dataclass
class WhileStmt(Statement):
    cond : Expression
    body : List[Statement]

@dataclass
class DoWhileStmt(Statement):
    body : List[Statement]
    cond : Expression

@dataclass
class Assignment(Statement):
    target: "Location"
    value : Expression

# =====================================================================
# Expresiones
# =====================================================================
@dataclass
class BinOper(Expression):
    oper : str
    left : Expression
    right: Expression

@dataclass
class UnaryOper(Expression):
    oper : str
    expr : Expression

@dataclass
class Literal(Expression):
    value : Union[int, float, str, bool]
    type  : str = None

@dataclass
class Integer(Literal):
    value : int
    def __post_init__(self):
        assert isinstance(self.value, int), "Value debe ser un 'integer'"
        self.type = 'integer'

@dataclass
class Float(Literal):
    value : float
    def __post_init__(self):
        assert isinstance(self.value, float), "Value debe ser un 'float'"
        self.type = 'float'

@dataclass
class Boolean(Literal):
    value : bool
    def __post_init__(self):
        assert isinstance(self.value, bool), "Value debe ser un 'boolean'"
        self.type = 'boolean'

@dataclass
class Char(Literal):
    value : str
    def __post_init__(self):
        assert isinstance(self.value, str) and len(self.value) == 1, "Value debe ser un 'char'"
        self.type = 'char'

@dataclass
class String(Literal):
    value : str
    def __post_init__(self):
        assert isinstance(self.value, str), "Value debe ser un 'string'"
        self.type = 'string'

@dataclass
class Increment(Expression):
    target: "Location"
    prefix: bool = True  # True = ++i, False = i++

@dataclass
class Decrement(Expression):
    target: "Location"
    prefix: bool = True  # True = --i, False = i--

@dataclass
class FuncCall(Expression):
    name: str
    args: List[Expression] = field(default_factory=list)

# ------------------ Ubicaciones ------------------
@dataclass
class Location(Expression):
    mode: str  # "load" o "store"

@dataclass
class VarLoc(Location):
    name: str

@dataclass
class ArrayLoc(Location):
    name : str
    index: List[Expression]

# ------------------ Tipos ------------------
@dataclass
class TypeNode(Expression):
    name: str
    dims: List[int] = field(default_factory=list)

