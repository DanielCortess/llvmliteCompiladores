# checker.py
'''
Este archivo contendrá la parte de verificación/validación de tipos de 
datos del compilador. Hay varios aspectos que deben gestionarse para que
esto funcione. 
Primero, debe tener una noción de "tipo" en su compilador.
Segundo, debe administrar los entornos (symtab) y el alcance para manejar
los nombres de las definiciones (variables, funciones, etc.)

Una clave para esta parte del proyecto es realizar pruebas adecuadas.
A medida que agregue código, piense en cómo podría probarlo.
'''
from rich    import print
from typing  import Union, List

from errors  import error, errors_detected
from model   import *
from symtab  import Symtab
from typesys import typenames, check_binop, check_unaryop, CheckError


class Check(Visitor):
    @classmethod
    def checker(cls, n: Program):
        '''
        1. Crear la tabla de simbol global
        2. Visitar todas las declaraciones en n.body
        '''
        checker = cls()
        env = Symtab('global')
        for decl in n.body:
            decl.accept(checker, env)

        return env

    def visit(self, n: VarDecl, env: Symtab):
        '''
        1. Si n.value es diferente de None, verifica que el tipo de datos sea igual al
           de la variable
        2. Agregar 'n' a la tabla de Simbol actual
        '''
        if n.value:
            if typenames(check_binop('=', n.type, n.value.type)) is None:
                error(f"En asignación de '{n.name}', no coincide los tipos", n.lineno)
        
        try:
            env.add(n.name, n)
        except Symtab.SymbolConflictError:
            error(f"La variable '{n.name}' ya declarada y con tipo diferente", n.lineno)
        except Symtab.SymbolDefinedError:
            error(f"La variable '{n.name}' ya declarada", n.lineno)

    def visit(self, n: ArrayDecl, env: Symtab):
        '''
        1. Si se definió n.size, verificar que sea entero
        2. Si se definió n.value, deben de ser tipo del arreglo
        3. Agregar el arreglo n a symtab.
        '''
        pass

    def visit(self, n: FuncDecl, env: Symtab):
        '''
        1. Agregar n a la tabla de simbol actual
        2. Crear la Symtab para la función
        3. Visitar cada uno de los parametros y agregarlos a Symtab
        4. Visitar cada decl en n.body
        '''
        try:
            env.add(n.name, n)
        except Symtab.SymbolConflictError:
            error(f"La función '{n.name}' ya declarada y con tipo diferente", n.lineno)
        except Symtab.SymbolDefinedError:
            error(f"La función '{n.name}' ya declarada", n.lineno)
        
        env = Symtab(n.name, env)

        for parm in n.parms:
            parm.accept(self, env)

        for stmt in n.body:
            stmt.accept(self, env)

    def visit(self, n: VarParm, env: Symtab):
        '''
        1. Agregar 'n' a la tabla a Symtab
        '''        
        try:
            env.add(n.name, n)
        except Symtab.SymbolConflictError:
            error(f"El parámetro '{n.name}' ya declarada y con tipo diferente", n.lineno)
        except Symtab.SymbolDefinedError:
            error(f"El parámetro '{n.name}' ya declarada", n.lineno)

    def visit(self, n: ArrayParm, env: Symtab):
        '''
        1. Si n.size esta definido, verificar que sea entero
        2. Agregar 'n' a la tabla de Symtab
        '''
        pass

    def visit(self, n: ReturnStmt, env: Symtab):
        '''
        1. Verificar que el return este dentro de una función.
        2. Visitar n.expr, si existe
        3. Verificar que tipo de n.expr sea igual al tipo de retorno de la función
        '''
        if env.name == 'global':
            error("La instrucción Return esta por fuera de uan función", n.lineno)
        
        func = env.get(env.name)
        if n.expr:
            n.expr.accept(self, env)
            if func.type != n.expr.type:
                error(f"La función '{func.name}' retorna un tipo diferente", n.lineno)

    def visit(self, n: BinOper, env: Symtab):
        '''
        1. Visitar el n.left y n.right
        2. Revisar si n.oper es permitida
        '''
        n.left.accept(self, env)
        n.right.accept(self, env)

        n.type = check_binop(n.oper, n.left.type, n.right.type)

        if n.type is None:
            error(f"En '{n.oper}', no coincide los tipos", n.lineno)

    def visit(self, n: VarLoc, env: Symtab):
        '''
        1. Buscar en Symtab la variable n.name y guardar su tipo
        '''
        n.type = env.get(n.name)

        if n.type is None:
            error(f"La variable '{n.name}' no está definida", n.lineno)