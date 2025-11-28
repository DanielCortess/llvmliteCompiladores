from rich.tree import Tree
from rich.console import Console
from multimethod import multimethod
from model import *

# =====================================================================
# Visitor para imprimir el AST con Rich
# =====================================================================
class ASTPrinter(Visitor):
    def __init__(self):
        self.console = Console()

    def print(self, node: Node):
        """Imprime el árbol a partir del nodo raíz"""
        tree = self.visit(node)
        self.console.print(tree)

    # ---------------------------------------------------------
    # Métodos visit para cada clase
    # ---------------------------------------------------------
    @multimethod
    def visit(self, node: Program):
        t = Tree("Program")
        for stmt in node.body:
            t.add(self.visit(stmt))
        return t

    @multimethod
    def visit(self, node: VarDecl):
        t = Tree(f"VarDecl(name={node.name})")
        t.add(Tree("Type")).add(self.visit(node.type))
        if node.value:
            t.add(Tree("Value")).add(self.visit(node.value))
        return t

    @multimethod
    def visit(self, node: ArrayDecl):
        t = Tree(f"ArrayDecl(name={node.name}, dims={node.dims})")
        t.add(Tree("Type")).add(self.visit(node.type))
        if node.value:
            values_tree = t.add(Tree("Values"))
            for v in node.value:
                values_tree.add(self.visit(v))
        return t

    @multimethod
    def visit(self, node: FuncDecl):
        t = Tree(f"FuncDecl(name={node.name}, return={node.return_type})")
        params_tree = t.add("Params")
        for p in node.params:
            params_tree.add(self.visit(p))
        body_tree = t.add("Body")
        for stmt in node.body:
            body_tree.add(self.visit(stmt))
        return t

    @multimethod
    def visit(self, node: Param):
        return Tree(f"Param(name={node.name}, type={node.type})")

    @multimethod
    def visit(self, node: BinOper):
        t = Tree(f"BinOper({node.oper})")
        t.add(self.visit(node.left))
        t.add(self.visit(node.right))
        return t

    @multimethod
    def visit(self, node: UnaryOper):
        t = Tree(f"UnaryOper({node.oper})")
        t.add(self.visit(node.expr))
        return t

    @multimethod
    def visit(self, node: Integer):
        return Tree(f"Integer({node.value})")

    @multimethod
    def visit(self, node: Float):
        return Tree(f"Float({node.value})")

    @multimethod
    def visit(self, node: Boolean):
        return Tree(f"Boolean({node.value})")

    @multimethod
    def visit(self, node: Char):
        return Tree(f"Char('{node.value}')")

    @multimethod
    def visit(self, node: String):
        return Tree(f"String(\"{node.value}\")")

    @multimethod
    def visit(self, node: Assignment):
        t = Tree("Assignment")
        t.add(Tree("Target")).add(self.visit(node.target))
        t.add(Tree("Value")).add(self.visit(node.value))
        return t

    @multimethod
    def visit(self, node: VarLoc):
        return Tree(f"VarLoc({node.name}, mode={node.mode})")

    @multimethod
    def visit(self, node: ArrayLoc):
        t = Tree(f"ArrayLoc({node.name}, mode={node.mode})")
        for i, idx in enumerate(node.index):
            t.add(Tree(f"Index[{i}]")).add(self.visit(idx))
        return t

    # ---------------------------------------------------------
    # Fallback genérico
    # ---------------------------------------------------------
    @multimethod
    def visit(self, node: Node):
        return Tree(node.__class__.__name__)
