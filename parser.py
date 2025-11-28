# parser.py
import logging
from rich import print as rprint
from rich.tree import Tree
import sly

from lexer import Lexer
from model import *
from errors import error, errors_detected  # si no existe, crea un stub simple


def _L(node, lineno):
    if hasattr(node, "lineno"):
        node.lineno = lineno
    return node


class Parser(sly.Parser):
    log = logging.getLogger()
    log.setLevel(logging.ERROR)
    expected_shift_reduce = 1
    debugfile = 'grammar.txt'

    tokens = Lexer.tokens

    # ==========================================================
    # PROGRAM
    # ==========================================================
    @_('decl_list')
    def prog(self, p):
        return Program(p.decl_list)

    @_('decl decl_list')
    def decl_list(self, p):
        return [p.decl] + p.decl_list

    @_('empty')
    def decl_list(self, p):
        return []

    # ==========================================================
    # DECLARATIONS
    # ==========================================================
    # var simple: name : type ;
    @_('ID ":" type_simple ";"')
    def decl(self, p):
        return _L(VarDecl(name=p.ID, type=p.type_simple), p.lineno)

    # array declaration: name : array [ expr ] type ;
    @_('ID ":" type_array_sized ";"')
    def decl(self, p):
        t = p.type_array_sized
        dims = t.dims if isinstance(t, TypeNode) and t.dims else []
        return _L(ArrayDecl(name=p.ID, type=TypeNode(name=t.name, dims=dims), dims=dims), p.lineno)

    # function declaration header: name : function ret_type ( params ) ;
    @_('ID ":" type_func ";"')
    def decl(self, p):
        ret_type, params = p.type_func
        return _L(FuncDecl(name=p.ID, return_type=ret_type, params=params), p.lineno)

    # declaration with initializer (var)
    @_('ID ":" type_simple "=" expr ";"')
    def decl_init(self, p):
        return _L(VarDecl(name=p.ID, type=p.type_simple, value=p.expr), p.lineno)

    # array with initializer: name : array [ expr ] type = { list } ;
    @_('ID ":" type_array_sized "=" "{" opt_expr_list "}" ";"')
    def decl_init(self, p):
        vals = p.opt_expr_list or []
        t = p.type_array_sized
        dims = t.dims if isinstance(t, TypeNode) and t.dims else []
        return _L(ArrayDecl(name=p.ID, type=TypeNode(name=t.name, dims=dims), dims=dims, value=vals), p.lineno)

    # function with body: name : function ret_type ( params ) = { stmts }
    @_('ID ":" type_func "=" "{" opt_stmt_list "}"')
    def decl_init(self, p):
        ret_type, params = p.type_func
        body = p.opt_stmt_list or []
        return _L(FuncDecl(name=p.ID, return_type=ret_type, params=params, body=body), p.lineno)

        # array sin tamaño
    @_('ID ":" type_array ";"')
    def decl(self, p):
        return _L(ArrayDecl(name=p.ID, type=p.type_array, dims=[]), p.lineno)


    # allow decl or decl_init as decl
    @_('decl_init')
    def decl(self, p):
        return p.decl_init

    # ==========================================================
    # STATEMENTS
    # ==========================================================
    @_('stmt_list')
    def opt_stmt_list(self, p): return p.stmt_list

    @_('empty')
    def opt_stmt_list(self, p): return []

    @_('stmt stmt_list')
    def stmt_list(self, p): return [p.stmt] + p.stmt_list

    @_('stmt')
    def stmt_list(self, p): return [p.stmt]

    @_('open_stmt')
    @_('closed_stmt')
    def stmt(self, p): return p[0]

    # closed / open statements (if / for ambiguity handling)
    @_('if_stmt_closed')
    @_('for_stmt_closed')
    @_('simple_stmt')
    def closed_stmt(self, p): return p[0]

    @_('if_stmt_open', 'for_stmt_open')
    def open_stmt(self, p): return p[0]

    # ---------- IF ----------
    @_('IF "(" opt_expr ")"')
    def if_cond(self, p): return p.opt_expr

    @_('if_cond closed_stmt ELSE closed_stmt')
    def if_stmt_closed(self, p):
        then_branch = p[1] if isinstance(p[1], list) else [p[1]]
        else_branch = p[3] if isinstance(p[3], list) else [p[3]]
        return _L(IfStmt(cond=p.if_cond, then=then_branch, else_=else_branch), p.lineno)

    @_('if_cond stmt')
    def if_stmt_open(self, p):
        then_branch = p[1] if isinstance(p[1], list) else [p[1]]
        return _L(IfStmt(cond=p.if_cond, then=then_branch), p.lineno)

    @_('if_cond closed_stmt ELSE if_stmt_open')
    def if_stmt_open(self, p):
        then_branch = p[1] if isinstance(p[1], list) else [p[1]]
        else_branch = p[3].then if isinstance(p[3], IfStmt) else [p[3]]
        return _L(IfStmt(cond=p.if_cond, then=then_branch, else_=else_branch), p.lineno)

    # ---------- FOR ----------
    # for ( init ; cond ; step ) stmt
    # Note: opt_expr appears three times -> SLY will name them opt_expr0 opt_expr1 opt_expr2
    @_('FOR "(" opt_expr ";" opt_expr ";" opt_expr ")" closed_stmt')
    def for_stmt_closed(self, p):
        init = getattr(p, 'opt_expr0', None)
        cond = getattr(p, 'opt_expr1', None)
        incr = getattr(p, 'opt_expr2', None)
        body = p.closed_stmt if isinstance(p.closed_stmt, list) else [p.closed_stmt]
        return _L(ForStmt(init=init, cond=cond, step=incr, body=body), p.lineno)

    @_('FOR "(" opt_expr ";" opt_expr ";" opt_expr ")" stmt')
    def for_stmt_open(self, p):
        init = getattr(p, 'opt_expr0', None)
        cond = getattr(p, 'opt_expr1', None)
        incr = getattr(p, 'opt_expr2', None)
        body = p.stmt if isinstance(p.stmt, list) else [p.stmt]
        return _L(ForStmt(init=init, cond=cond, step=incr, body=body), p.lineno)

    # ---------- SIMPLE STATEMENTS ----------
    @_('RETURN opt_expr ";"')
    def simple_stmt(self, p):
        return _L(ReturnStmt(value=p.opt_expr), p.lineno)

    @_('PRINT opt_expr_list ";"')
    def simple_stmt(self, p):
        vals = p.opt_expr_list or []
        return _L(PrintStmt(value=vals), p.lineno)

    @_('"{" opt_stmt_list "}"')
    def simple_stmt(self, p):
        return p.opt_stmt_list

    @_('decl')
    def simple_stmt(self, p):
        return p.decl

    @_('expr ";"')
    def simple_stmt(self, p):
        return p.expr


    # ==========================================================
    # EXPRESSIONS
    # ==========================================================
    @_('expr1')
    def expr(self, p): return p.expr1

    @_('lval "=" expr1')
    def expr1(self, p): return _L(Assignment(target=p.lval, value=p.expr1), p.lineno)

    @_('expr2')
    def expr1(self, p): return p.expr2

    # expr2: simplified binary expression with left recursion flattened
    @_('factor')
    def expr2(self, p): return p.factor

    @_('expr2 "+" factor')
    def expr2(self, p): return _L(BinOper(oper='+', left=p.expr2, right=p.factor), p.lineno)

    @_('expr2 "-" factor')
    def expr2(self, p): return _L(BinOper(oper='-', left=p.expr2, right=p.factor), p.lineno)

    @_('expr2 "*" factor')
    def expr2(self, p): return _L(BinOper(oper='*', left=p.expr2, right=p.factor), p.lineno)

    @_('expr2 "/" factor')
    def expr2(self, p): return _L(BinOper(oper='/', left=p.expr2, right=p.factor), p.lineno)

   

    # lvalues
    @_('ID')
    def lval(self, p): return _L(VarLoc(mode="store", name=p.ID), p.lineno)

    @_('ID "[" expr "]"')
    def lval(self, p):
        # array access: ID [ expr ]
        return _L(ArrayLoc(mode="store", name=p.ID, index=[p.expr]), p.lineno)

    # ==========================================================
    # FACTORS (tokens literales and groups)
    # ==========================================================
    @_('"(" expr ")"')
    def group(self, p):
        return p.expr

    @_('ID "(" opt_expr_list ")"')
    def group(self, p):
        args = p.opt_expr_list or []
        return _L(FuncCall(name=p.ID, args=args), p.lineno)

    @_('ID')
    def factor(self, p): return _L(VarLoc(mode="load", name=p.ID), p.lineno)

    @_('INT_LITERAL')
    def factor(self, p): return _L(Integer(p.INT_LITERAL), p.lineno)

    @_('FLOAT_LITERAL')
    def factor(self, p): return _L(Float(p.FLOAT_LITERAL), p.lineno)

    @_('CHAR_LITERAL')
    def factor(self, p): return _L(Char(p.CHAR_LITERAL), p.lineno)

    @_('STRING_LITERAL')
    def factor(self, p): return _L(String(p.STRING_LITERAL), p.lineno)

    @_('TRUE')
    def factor(self, p): return _L(Boolean(True), p.lineno)

    @_('FALSE')
    def factor(self, p): return _L(Boolean(False), p.lineno)

    # ==========================================================
    # TYPES and TYPE FORMS
    # ==========================================================
    @_('INTEGER')
    @_('FLOAT')
    @_('BOOLEAN')
    @_('CHAR')
    @_('STRING')
    @_('VOID')
    def type_simple(self, p):
        return TypeNode(name=p[0])

    # array without explicit dimension: array [] type
    @_('ARRAY "[" "]" type_simple')
    def type_array(self, p):
        return TypeNode(name=p.type_simple.name, dims=[])

    # array with expression dimension: array [ expr ] type
    @_('ARRAY "[" expr "]" type_simple')
    def type_array_sized(self, p):
        # store the expression as dimension (may be an Integer node or any expr)
        return TypeNode(name=p.type_simple.name, dims=[p.expr])   
    # function type: FUNCTION ret_type ( opt_param_list )
    @_('FUNCTION type_simple "(" opt_param_list ")"')
    def type_func(self, p):
        return (p.type_simple, p.opt_param_list or [])

    @_('FUNCTION type_array_sized "(" opt_param_list ")"')
    def type_func(self, p):
        return (p.type_array_sized, p.opt_param_list or [])

    # params helpers
    @_('param_list')
    def opt_param_list(self, p): return p.param_list

    @_('empty')
    def opt_param_list(self, p): return []

    @_('param "," param_list')
    def param_list(self, p): return [p.param] + p.param_list

    @_('param')
    def param_list(self, p): return [p.param]

    @_('ID ":" type_simple')
    def param(self, p):
        return VarParm(name=p.ID, type=p.type_simple)

    @_('ID ":" type_array')
    def param(self, p):
        return VarParm(name=p.ID, type=p.type_array)

    @_('ID ":" type_array_sized')
    def param(self, p):
        return VarParm(name=p.ID, type=p.type_array_sized)   

    # ==========================================================
    # EXPR LIST
    # ==========================================================
    @_('expr_list')
    def opt_expr_list(self, p): return p.expr_list

    @_('empty')
    def opt_expr_list(self, p): return []

    @_('expr "," expr_list')
    def expr_list(self, p): return [p.expr] + p.expr_list

    @_('expr')
    def expr_list(self, p): return [p.expr]

    # ==========================================================
    # OPT EXPR
    # ==========================================================
    @_('expr')
    def opt_expr(self, p): return p.expr

    @_('empty')
    def opt_expr(self, p): return None

    # ==========================================================
    # EMPTY
    # ==========================================================
    @_('')
    def empty(self, p): return None

    # ==========================================================
    # ERROR
    # ==========================================================
    def error(self, p):
        lineno = p.lineno if p else 'EOF'
        value = repr(p.value) if p else 'EOF'
        error(f"Syntax error at {value}", lineno)


def parse(txt):
    l = Lexer()
    p = Parser()
    return p.parse(l.tokenize(txt))


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        rprint("Usage: python parser.py <filename>")
    else:
        filename = sys.argv[1]
        txt = open(filename, encoding='utf-8').read()
        ast = parse(txt)

        # Imprimir AST con Rich
        def print_ast(node, tree: Tree):
            if isinstance(node, Node):
                branch = tree.add(node.__class__.__name__)
                for field, value in vars(node).items():
                    if isinstance(value, list):
                        sub = branch.add(field)
                        for v in value: print_ast(v, sub)
                    elif isinstance(value, Node):
                        sub = branch.add(field)
                        print_ast(value, sub)
                    else:
                        branch.add(f"{field}: {value}")
            else:
                tree.add(str(node))

        t = Tree("AST")
        print_ast(ast, t)
        rprint(t)
