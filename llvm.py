# llvm.py
"""
Generador LLVM para B-Minor usando llvmlite.ir

Notas:
- Debes haber leído docs/Tutorial_LLVMlite.md y docs/Control-Flow.md
- Este generador cubre las construcciones comunes (declaraciones, expresiones,
  funciones, llamadas, prints, if, for, return). Es un generador razonablemente
  completo, pero puede requerir ajustes si tu AST usa nombres distintos.
"""

from llvmlite import ir
from model import *

# Tipos LLVM correspondientes a B-Minor
int_type   = ir.IntType(32)
float_type = ir.DoubleType()
bool_type  = ir.IntType(1)
char_type  = ir.IntType(8)
void_type  = ir.VoidType()

_typemap = {
    'integer': int_type,
    'float'  : float_type,
    'boolean': bool_type,
    'char'   : char_type,
    'void'   : void_type,
}

def get_llvm_type(btype):
    """Devuelve el tipo LLVM para un tipo B-Minor.
    btype puede ser: string ('integer') o un TypeNode con atributo name.
    """
    if btype is None:
        return None
    name = btype if isinstance(btype, str) else getattr(btype, 'name', None)
    if name is None:
        raise RuntimeError(f"Tipo inválido: {btype}")
    if name not in _typemap:
        raise RuntimeError(f"Tipo B-Minor no mapeado a LLVM: {name}")
    return _typemap[name]

class LLVMContext:
    def __init__(self):
        # env: mapping de nombres a (alloca o ir.Value) o a Func
        self.env = {}

        # Módulo LLVM
        self.module = ir.Module(name='bminor')

        # Función 'main' vacía (ret void)
        self.main_fn = ir.Function(self.module, ir.FunctionType(void_type, []), name='main')
        entry = self.main_fn.append_basic_block('entry')
        self.builder = ir.IRBuilder(entry)
        self.current_function = self.main_fn

        # Runtime printing functions (declaradas externamente en runtime.c)
        self._printi = ir.Function(self.module, ir.FunctionType(void_type, [int_type]), name='_printi')
        self._printf = ir.Function(self.module, ir.FunctionType(void_type, [float_type]), name='_printf')
        self._printb = ir.Function(self.module, ir.FunctionType(void_type, [bool_type]), name='_printb')
        self._printc = ir.Function(self.module, ir.FunctionType(void_type, [char_type]), name='_printc')
        # Puedes agregar _printstr si tienes runtime para strings

    def __str__(self):
        return str(self.module)

    # Helpers
    def new_alloca(self, name, llvm_type):
        """Crear un alloca en la entrada de la función para variables locales (stack slot)."""
        # alloca debe ir en el entry block; para simplicidad colocamos en el current block
        with self.builder.goto_entry_block():
            return self.builder.alloca(llvm_type, name=name)

# -------------------------
# Generación de código
# -------------------------
def generate_program(program):
    """Genera código LLVM para un Program AST (instancia de Program)."""
    context = LLVMContext()

    # Si Program contiene lista de declaraciones como program.body
    for decl in program.body:
        generate(decl, context)

    # terminar main
    # Si main ya tiene un retorno emitido, no emitir otro ret.
    if not context.builder.block.is_terminated:
        context.builder.ret_void()

    return str(context.module)

# -------------------------
# Generador recursivo
# -------------------------
def generate(node, context):
    """Dispatcher principal"""
    # Literales
    if isinstance(node, Integer):
        return ('integer', ir.Constant(int_type, int(node.value)))

    if isinstance(node, Float):
        return ('float', ir.Constant(float_type, float(node.value)))

    if isinstance(node, Boolean):
        val = 1 if bool(node.value) else 0
        return ('boolean', ir.Constant(bool_type, val))

    if isinstance(node, Char):
        return ('char', ir.Constant(char_type, ord(node.value[0]) if isinstance(node.value, str) and node.value else 0))

    if isinstance(node, String):
        # string handling: create a global constant and return pointer (i8*)
        s = node.value.encode('utf8') + b'\00'
        gvar = ir.GlobalVariable(context.module, ir.ArrayType(ir.IntType(8), len(s)), name=f".str{len(context.module.global_values)}")
        gvar.global_constant = True
        gvar.initializer = ir.Constant(ir.ArrayType(ir.IntType(8), len(s)), bytearray(s))
        ptr = context.builder.bitcast(gvar, ir.IntType(8).as_pointer())
        return ('string', ptr)

    # Variables (load)
    if isinstance(node, VarLoc):
        if node.mode == "load":
            entry = context.env.get(node.name)
            if entry is None:
                raise RuntimeError(f"Variable no definida: {node.name}")
            ptr, btype = entry
            val = context.builder.load(ptr, name=node.name+"_val")
            return (btype, val)
        else:
            # store-mode used only when generating assignment target
            entry = context.env.get(node.name)
            if entry is None:
                raise RuntimeError(f"Variable no definida: {node.name}")
            ptr, btype = entry
            return ('lvalue', (ptr, btype))

    # Array access
    if isinstance(node, ArrayLoc):
        # support only single-dim access here; node.index is list of expressions
        entry = context.env.get(node.name)
        if entry is None:
            raise RuntimeError(f"Arreglo no definido: {node.name}")
        ptr, btype = entry  # ptr es pointer to array base or alloca
        # resolver índice (solo primer índice)
        if not node.index:
            raise RuntimeError("Index expression vacía")
        idx_type, idx_val = generate(node.index[0], context)
        # convert idx to int if needed (assume integer)
        # calcular elemento pointer: GEP
        # ptr puede ser pointer al primer elemento o pointer al array; asumimos pointer al primer elemento
        gep = context.builder.gep(ptr, [ir.Constant(int_type, 0), idx_val] if isinstance(ptr.type.pointee, ir.ArrayType) else [idx_val], inbounds=True)
        val = context.builder.load(gep, name=f"{node.name}_elem")
        return (btype, val)

    # Assignment: lval = expr
    if isinstance(node, Assignment):
        # obtener lvalue
        target_mode, target = generate(node.target, context)
        if target_mode != 'lvalue':
            raise RuntimeError("Target no es lvalue")
        ptr, btype = target
        # generar rhs
        rhs_type, rhs_val = generate(node.value, context)
        # si rhs_type no es igual a btype, intentar coerción simple
        if rhs_type != btype:
            # intentar conversión int->float
            if rhs_type == 'integer' and btype == 'float':
                rhs_val = context.builder.sitofp(rhs_val, float_type)
                rhs_type = 'float'
            else:
                raise RuntimeError(f"Incompatible assignment: {rhs_type} to {btype}")
        context.builder.store(rhs_val, ptr)
        return None

    # BinOper
    if isinstance(node, BinOper):
        lt, lv = generate(node.left, context)
        rt, rv = generate(node.right, context)

        # promote int->float if one is float
        if lt == 'float' or rt == 'float':
            # ensure both floats
            if lt == 'integer':
                lv = context.builder.sitofp(lv, float_type)
                lt = 'float'
            if rt == 'integer':
                rv = context.builder.sitofp(rv, float_type)
                rt = 'float'

        if lt != rt:
            raise RuntimeError(f"Operando binario con tipos incompatibles: {lt} vs {rt}")

        op = node.oper
        if lt == 'integer':
            if op == '+':
                return ('integer', context.builder.add(lv, rv, name='addtmp'))
            if op == '-':
                return ('integer', context.builder.sub(lv, rv, name='subtmp'))
            if op == '*':
                return ('integer', context.builder.mul(lv, rv, name='multmp'))
            if op == '/':
                return ('integer', context.builder.sdiv(lv, rv, name='divtmp'))
            if op == '%':
                return ('integer', context.builder.srem(lv, rv, name='modtmp'))
            if op in ('<','<=','>','>=','==','!='):
                if op == '<':
                    c = context.builder.icmp_signed('<', lv, rv)
                elif op == '<=':
                    c = context.builder.icmp_signed('<=', lv, rv)
                elif op == '>':
                    c = context.builder.icmp_signed('>', lv, rv)
                elif op == '>=':
                    c = context.builder.icmp_signed('>=', lv, rv)
                elif op == '==':
                    c = context.builder.icmp_signed('==', lv, rv)
                elif op == '!=':
                    c = context.builder.icmp_signed('!=', lv, rv)
                return ('boolean', c)
        elif lt == 'float':
            if op == '+':
                return ('float', context.builder.fadd(lv, rv, name='faddtmp'))
            if op == '-':
                return ('float', context.builder.fsub(lv, rv, name='fsubtmp'))
            if op == '*':
                return ('float', context.builder.fmul(lv, rv, name='fmultmp'))
            if op == '/':
                return ('float', context.builder.fdiv(lv, rv, name='fdivtmp'))
            if op in ('<','<=','>','>=','==','!='):
                if op == '<':
                    c = context.builder.fcmp_ordered('<', lv, rv)
                elif op == '<=':
                    c = context.builder.fcmp_ordered('<=', lv, rv)
                elif op == '>':
                    c = context.builder.fcmp_ordered('>', lv, rv)
                elif op == '>=':
                    c = context.builder.fcmp_ordered('>=', lv, rv)
                elif op == '==':
                    c = context.builder.fcmp_ordered('==', lv, rv)
                elif op == '!=':
                    c = context.builder.fcmp_ordered('!=', lv, rv)
                # fcpm returns i1 already
                return ('boolean', c)

        # logical ops (assume boolean operands)
        if lt == 'boolean':
            if op == '&&' or op == 'LAND':
                return ('boolean', context.builder.and_(lv, rv))
            if op == '||' or op == 'LOR':
                return ('boolean', context.builder.or_(lv, rv))
            if op == '==':
                return ('boolean', context.builder.icmp_signed('==', lv, rv))
            if op == '!=':
                return ('boolean', context.builder.icmp_signed('!=', lv, rv))

        raise RuntimeError(f"BinOp no soportado: {node.oper} con tipo {lt}")

    # Unary
    if isinstance(node, UnaryOper):
        t, v = generate(node.expr, context)
        if node.oper == '-':
            if t == 'integer':
                return ('integer', context.builder.neg(v))
            if t == 'float':
                return ('float', context.builder.fneg(v))
        if node.oper == '!':
            if t == 'boolean':
                # not: xor with 1
                one = ir.Constant(bool_type, 1)
                return ('boolean', context.builder.xor(v, one))
        raise RuntimeError(f"Unary operator {node.oper} not supported for {t}")

    # Print statement
    if isinstance(node, PrintStmt):
        # assume PrintStmt.value is list of expressions
        for expr in node.value:
            ty, val = generate(expr, context)
            if ty == 'integer':
                context.builder.call(context._printi, [val])
            elif ty == 'float':
                context.builder.call(context._printf, [val])
            elif ty == 'boolean':
                context.builder.call(context._printb, [val])
            elif ty == 'char':
                context.builder.call(context._printc, [val])
            elif ty == 'string':
                # if runtime has a printstring, you'd call it; here just ignore or extend
                # try to bitcast to i8* and call if defined
                try:
                    fn = context.module.get_global('_printstr')
                    context.builder.call(fn, [val])
                except Exception:
                    pass
        return None

    # Return
    if isinstance(node, ReturnStmt):
        if node.value:
            ty, val = generate(node.value, context)
            # if current function returns non-void, emit return value cast if necessary
            if context.current_function.function_type.return_type == void_type:
                # returning void but value present
                raise RuntimeError("Return with value in void function")
            # handle int->float cast
            ret_ty = context.current_function.function_type.return_type
            if ret_ty == float_type and ty == 'integer':
                val = context.builder.sitofp(val, float_type)
            context.builder.ret(val)
        else:
            context.builder.ret_void()
        return None

    # Function declaration
    if isinstance(node, FuncDecl):
        # gather param types names
        params = getattr(node, 'params', getattr(node, 'parms', []))
        ret_type = node.return_type if hasattr(node, 'return_type') else getattr(node, 'type', None)
        llvm_ret = get_llvm_type(ret_type) if ret_type else void_type
        llvm_param_types = []
        for p in params:
            ptype = getattr(p, 'type', None)
            llvm_param_types.append(get_llvm_type(ptype))

        fn_type = ir.FunctionType(llvm_ret, llvm_param_types)
        fn = ir.Function(context.module, fn_type, name=node.name)

        # create entry block and new builder
        block = fn.append_basic_block('entry')
        saved_builder = context.builder
        saved_function = context.current_function

        context.builder = ir.IRBuilder(block)
        context.current_function = fn

        # allocate space for parameters and add to env
        context.env = context.env.copy()  # shallow copy so locals don't clobber globals
        for i, p in enumerate(params):
            llvm_ptype = llvm_param_types[i]
            alloca = context.builder.alloca(llvm_ptype, name=p.name)
            # store incoming argument in alloca
            context.builder.store(fn.args[i], alloca)
            context.env[p.name] = (alloca, getattr(p, 'type', None))

        # generate body
        for stmt in node.body:
            generate(stmt, context)

        # ensure function terminated
        if not context.builder.block.is_terminated:
            if llvm_ret == void_type:
                context.builder.ret_void()
            else:
                # return zero constant of return type
                if llvm_ret == int_type:
                    context.builder.ret(ir.Constant(int_type, 0))
                elif llvm_ret == float_type:
                    context.builder.ret(ir.Constant(float_type, 0.0))
                else:
                    context.builder.ret(ir.Constant(llvm_ret, None))

        # restore builder and function
        context.builder = saved_builder
        context.current_function = saved_function

        # register function in env
        context.env[node.name] = (fn, node.return_type)
        return None

    # Function call
    if isinstance(node, FuncCall):
        # resolve function
        entry = context.env.get(node.name)
        if entry is None:
            # allow calling runtime print functions by name
            fn = context.module.get_global(node.name) if node.name in context.module.globals else None
            if fn is None:
                raise RuntimeError(f"Función no definida: {node.name}")
        else:
            fn, _ = entry

        # generate args
        args = []
        for arg in node.args:
            ty, val = generate(arg, context)
            # maybe cast integer->float for parameter
            args.append(val)
        call = context.builder.call(fn, args)
        # try to determine return type
        rt = fn.function_type.return_type
        if rt == void_type:
            return None
        if rt == int_type:
            return ('integer', call)
        if rt == float_type:
            return ('float', call)
        if rt == bool_type:
            return ('boolean', call)
        return ('unknown', call)

    # If statement
    if isinstance(node, IfStmt):
        cond_ty, cond_val = generate(node.cond, context)
        # if boolean is i1, use it directly, else compare
        if cond_ty != 'boolean':
            raise RuntimeError("Condición de if debe ser boolean")
        then_bb = context.current_function.append_basic_block('then')
        else_bb = context.current_function.append_basic_block('else')
        end_bb = context.current_function.append_basic_block('ifend')
        context.builder.cbranch(cond_val, then_bb, else_bb)

        # then block
        context.builder.position_at_end(then_bb)
        for s in node.then:
            generate(s, context)
        if not context.builder.block.is_terminated:
            context.builder.branch(end_bb)

        # else block
        context.builder.position_at_end(else_bb)
        if node.else_:
            for s in node.else_:
                generate(s, context)
        if not context.builder.block.is_terminated:
            context.builder.branch(end_bb)

        # continue at end_bb
        context.builder.position_at_end(end_bb)
        return None

    # For statement: for(init; cond; step) body
    if isinstance(node, ForStmt):
        # init
        if node.init:
            generate(node.init, context)
        # create blocks
        loop_bb = context.current_function.append_basic_block('forloop')
        after_bb = context.current_function.append_basic_block('forafter')
        # branch to condition
        context.builder.branch(loop_bb)
        context.builder.position_at_end(loop_bb)
        # condition
        if node.cond:
            cond_ty, cond_val = generate(node.cond, context)
            if cond_ty != 'boolean':
                raise RuntimeError("Condición de for debe ser boolean")
            # body or exit
            body_bb = context.current_function.append_basic_block('forbody')
            context.builder.cbranch(cond_val, body_bb, after_bb)
            # body
            context.builder.position_at_end(body_bb)
            for s in node.body:
                generate(s, context)
            # step
            if node.step:
                generate(node.step, context)
            # loop back
            context.builder.branch(loop_bb)
            # move to after block
            context.builder.position_at_end(after_bb)
        else:
            # infinite loop form (no cond) - run body then step then branch
            for s in node.body:
                generate(s, context)
            if node.step:
                generate(node.step, context)
            context.builder.branch(loop_bb)
            context.builder.position_at_end(after_bb)
        return None

    # Declarations (var)
    if isinstance(node, VarDecl):
        llvm_t = get_llvm_type(node.type)
        ptr = context.builder.alloca(llvm_t, name=node.name)
        context.env[node.name] = (ptr, getattr(node, 'type', None))
        if node.value:
            ty, val = generate(node.value, context)
            if ty != getattr(node, 'type', None) and not (ty == 'integer' and getattr(node, 'type', None) == 'float'):
                # simple coercion int->float
                if ty == 'integer' and getattr(node, 'type', None) == 'float':
                    val = context.builder.sitofp(val, float_type)
                else:
                    raise RuntimeError(f"Incompatible init value type for variable {node.name}: {ty}")
            context.builder.store(val, ptr)
        return None

    # Array declaration (simple): allocate array in stack if size known
    if isinstance(node, ArrayDecl):
        # only support one dimension and integer size
        if node.dims and len(node.dims) >= 1:
            dim_expr = node.dims[0]
            dt, dv = generate(dim_expr, context)
            if dt != 'integer':
                raise RuntimeError("Dimensión de arreglo debe ser integer")
            # create array type
            base_llvm = get_llvm_type(node.type)
            if isinstance(dv, ir.Constant):
                size_val = int(dv.constant)
                arr_ty = ir.ArrayType(base_llvm, size_val)
                galloca = context.builder.alloca(arr_ty, name=node.name)
                # store pointer to array base
                ptr = galloca
            else:
                # if size is not constant at compile-time: allocate pointer and use malloc (not implemented)
                raise RuntimeError("Dimensión de arreglo debe ser constante para la implementación actual")
            context.env[node.name] = (ptr, getattr(node, 'type', None))
            # initialize values if provided
            if node.value:
                for i, v in enumerate(node.value):
                    ty, val = generate(v, context)
                    # compute element pointer
                    gep = context.builder.gep(ptr, [ir.Constant(int_type, 0), ir.Constant(int_type, i)], inbounds=True)
                    context.builder.store(val, gep)
            return None
        else:
            raise RuntimeError("Declaración de arreglo sin tamaño no soportada por este generador")

    # Fallback
    raise RuntimeError(f"No se puede generar código para nodo: {node.__class__.__name__}")
    

# -------------------------
# Pequeña utilidad para ejecutar desde línea de comandos
# -------------------------
def main(filename):
    # Dependiendo de tu proyecto, ajustar parse_file / typecheck
    from parser import parse
    from checker import Check

    txt = open(filename, encoding='utf-8').read()
    prog = parse(txt)
    # asume que Check.checker retorna env o True si pasa
    try:
        Check.checker(prog)
    except Exception as e:
        print("Errores semánticos detectados:", e)
        return

    code = generate_program(prog)
    with open('out.ll', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Wrote out.ll")

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        print("Usage: python llvm.py <source.bminor>")
