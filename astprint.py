# astprint.py

from graphviz import Digraph
from rich     import print

from model    import *


class ASTPrinter(Visitor):
    node_defaults = {
        'shape' : 'box',
        'color' : 'deepskyblue',
        'style' : 'filled'
    }
    edge_defaults = {
        'arrowhead' : 'none'
    }
    def __init__(self):
        self.dot = Digraph('AST')
        self.dot.attr('node', **self.node_defaults)
        self.dot.attr('edge', **self.edge_defaults)
        self._seq = 0
    
    @property
    def name(self):
        self._seq += 1
        return f'n{self._seq:02d}'
    
    @classmethod
    def render(cls, n: Node):
        dot = cls()
        n.accept(dot)
        return dot.dot

    def visit(self, n: Program):
        name = self.name
        self.dot.node(name, label='Program')
        for stmt in n.body:
            self.dot.edge(name, stmt.accept(self))
        return name

    def visit(self, n: VarDecl):
        name = self.name
        self.dot.node(name, label=f'VarDecl\n{n.name}:{n.type}')
        if n.value:
            self.dot.edge(name, n.value.accept(self))
        return name

    def visit(self, n: BinOper):
        name = self.name
        self.dot.node(name, label=f'{n.oper}', shape='circle')
        self.dot.edge(name, n.left.accept(self))
        self.dot.edge(name, n.right.accept(self))
        return name

    def visit(self, n: UnaryOper):
        name = self.name
        self.dot.node(name, label=f'{n.oper}', shape='circle')
        self.dot.edge(name, n.expr.accept(self))
        return name

    def visit(self, n: Literal):
        name = self.name
        self.dot.node(name, label=f'{n.value}:{n.type}')
        return name


if __name__ == '__main__':
    import sys
    from parser import parse
    
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python astprint.py <filename>")
    
    txt = open(sys.argv[1], encoding='utf-8').read()
    ast = parse(txt)
		
    dot = ASTPrinter.render(ast)
