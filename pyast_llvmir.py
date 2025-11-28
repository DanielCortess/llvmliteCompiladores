# pyast_llvmir.py (corregido)
'''
pyast_llvmir.py — Tiny Pythonic -> LLVM IR (llvmlite)

Soporta:
	- int (i32), bool (i1)
	- variables locales (int)
	- asignación a = expr
	- binarios: +, -, *, // (sdiv), % (srem)
	- unarios: +x, -x
	- comparaciones: < <= > >= == != (icmp -> i1)
	- if/else
	- while
	- print(expr) -> printf("%d\n", expr)

	- Funciones (args i32, retorno i32)
	- for i in range(start, stop, step_const!=0)  [se descompone a while]
	- Arreglos 1D: array(n) -> alloca i32, i32 n (puntero i32*), a[i], a[i] = expr

Uso:
	pip install llvmlite
	python3 pyast_llvmir.py programa.py > out.ll
	llc -filetype=obj out.ll -o out.o && clang -o programa out.o

MIT License.
'''
import ast
import argparse
from typing import Dict, Optional
from llvmlite import ir, binding as llvm

# --- Inicialización de backend/target ---
# llvm.initialize()
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()
_target = llvm.Target.from_default_triple()
_tm = _target.create_target_machine()
_TRIPLE = _target.triple
_DATALAYOUT = str(_tm.target_data)

I32 = ir.IntType(32)
I1  = ir.IntType(1)
I8  = ir.IntType(8)

class CompileError(Exception):
	pass
	
class FunctionContext:
	'''
	Contexto por función: builder, tabla de locales (allocas) y builder de allocas
	colocado al INICIO del bloque 'entry' (canónico para mem2reg).
	'''
	def __init__(self, func: ir.Function, builder: ir.IRBuilder, printf: ir.Function, fmt_str: ir.GlobalVariable):
		self.func = func
		self.builder = builder
		self.printf = printf
		self.fmt_str = fmt_str
		self.locals: Dict[str, ir.AllocaInstr] = {}
		
		# Builder dedicado para allocas, posicionado
		# al inicio del 'entry'
		entry = func.entry_basic_block or func.append_basic_block('entry')
		self.allocas_builder = ir.IRBuilder(entry)
		
		# IMPORTANTE: allocas antes de cualquier otra 
		# instrucción
		self.allocas_builder.position_at_start(entry)
		
	def create_alloca(self, name: str, ty: ir.Type, count: Optional[ir.Value] = None):
		'''
		Crea alloca en 'entry'. Si count no es None, alloca dinámica (ty, count).
		'''
		with self.allocas_builder.goto_block(self.allocas_builder.block):
			if count is None:
				return self.allocas_builder.alloca(ty, name=name)
			# llvmlite usa el tamaño como segundo argumento posicional
			return self.allocas_builder.alloca(ty, count, name=name)
			
	def get_or_alloca(self, name: str, ty: ir.Type):
		"""
		Obtiene o crea un slot (alloca) de tipo 'ty' para la variable.
		"""
		if name not in self.locals:
			self.locals[name] = self.create_alloca(name, ty)
		else:
			alloc = self.locals[name]
			if alloc.type.pointee != ty:
				raise CompileError(f"Variable '{name}' ya está tipada como {alloc.type.pointee}, no como {ty}")
		return self.locals[name]
		
class LLVMCompiler(ast.NodeVisitor):
	def __init__(self):
		self.module = ir.Module(name="pyast_llvmir")
		# Fijar triple y datalayout del host
		self.module.triple = _TRIPLE
		self.module.data_layout = _DATALAYOUT
		
		# Declara printf: i32 (i8*, ...)
		self.printf_ty = ir.FunctionType(I32, [I8.as_pointer()], var_arg=True)
		self.printf = ir.Function(self.module, self.printf_ty, name="printf")
		
		# Cadena global "%d\n\0"
		arr_t = ir.ArrayType(I8, 4)
		self.fmt_str = ir.GlobalVariable(self.module, arr_t, name="fmt_dnl")
		self.fmt_str.global_constant = True
		self.fmt_str.linkage = 'internal'
		self.fmt_str.initializer = ir.Constant(arr_t, bytearray(b"%d\n\x00"))
		
		# Estado
		self.context: Optional[FunctionContext] = None
		self.functions: Dict[str, ir.Function] = {}
		
	# --- Utilidades de tipos
	def _as_i32(self, v: ir.Value):
		if isinstance(v.type, ir.IntType) and v.type.width == 32:
			return v
		if isinstance(v.type, ir.IntType) and v.type.width == 1:
			return self.context.builder.zext(v, I32)
		raise CompileError("expected int or bool value")
		
	def _as_i1(self, v: ir.Value):
		if isinstance(v.type, ir.IntType) and v.type.width == 1:
			return v
		if isinstance(v.type, ir.IntType) and v.type.width == 32:
			return self.context.builder.icmp_unsigned('!=', v, ir.Constant(I32, 0))
		raise CompileError("expected int/bool for condition")
		
	# --- Fase principal
	def compile(self, source: str):
		tree = ast.parse(source)
		# 1) Declaración de funciones
		for n in tree.body:
			if isinstance(n, ast.FunctionDef):
				self._declare_function(n)
		# 2) Si hay sentencias top-level o no hay main, sintetiza main()
		has_top = any(not isinstance(n, ast.FunctionDef) for n in tree.body)
		if has_top or 'main' not in self.functions:
			self._declare_implicit_main()
		# 3) Definir funciones y/o emitir top-level
		for n in tree.body:
			if isinstance(n, ast.FunctionDef):
				self._define_function(n)
			else:
				self._emit_in_implicit_main(n)
		# 4) Cerrar main implícito si corresponde
		self._finish_implicit_main()
		return str(self.module)
		
	def _declare_function(self, fdef: ast.FunctionDef):
		if fdef.args.vararg or fdef.args.kwarg or fdef.args.kwonlyargs:
			raise CompileError("solo argumentos posicionales soportados")
		fnty = ir.FunctionType(I32, [I32 for _ in fdef.args.args])
		fn = ir.Function(self.module, fnty, name=fdef.name)
		for i, a in enumerate(fdef.args.args):
			fn.args[i].name = a.arg
		self.functions[fdef.name] = fn
		
	def _declare_implicit_main(self):
		if 'main' in self.functions:
			return
		fnty = ir.FunctionType(I32, [])
		fn = ir.Function(self.module, fnty, name="main")
		self.functions['main'] = fn
		entry = fn.append_basic_block('entry')
		builder = ir.IRBuilder(entry)
		# Contexto con allocas en 'entry'
		self.context = FunctionContext(fn, builder, self.printf, self.fmt_str)
		# Cuerpo real
		body = fn.append_basic_block('toplevel')
		builder.branch(body)
		self.context.builder = ir.IRBuilder(body)
		
	def _finish_implicit_main(self):
		if self.context and self.context.func.name == 'main' and not self.context.builder.block.is_terminated:
			self.context.builder.ret(ir.Constant(I32, 0))
			self.context = None
			
	def _emit_in_implicit_main(self, node: ast.AST):
		if not self.context or self.context.func.name != 'main':
			raise CompileError("internal: implicit main context missing")
		self.visit(node)
		
	def _define_function(self, fdef: ast.FunctionDef):
		fn = self.functions[fdef.name]
		entry = fn.append_basic_block('entry')
		entry_builder = ir.IRBuilder(entry)
		# Contexto con allocas en 'entry'
		prev_ctx = self.context
		ctx = FunctionContext(fn, entry_builder, self.printf, self.fmt_str)
		# Bloque de cuerpo real
		body = fn.append_basic_block('body')
		entry_builder.branch(body)
		ctx.builder = ir.IRBuilder(body)
		self.context = ctx
		# Guardar args en locales (alloca i32 + store)
		for a in fn.args:
			alloca = ctx.get_or_alloca(a.name, I32)
			ctx.builder.store(a, alloca)
		# Emitir cuerpo
		for st in fdef.body:
			self.visit(st)
		# Asegurar retorno
		if not ctx.builder.block.is_terminated:
			ctx.builder.ret(ir.Constant(I32, 0))
		self.context = prev_ctx
		
	# --- Visitantes de AST
	def visit_Module(self, node: ast.Module):
		raise CompileError("usa compile(source) en lugar de visitar Module directamente")
		
	def visit_Expr(self, node: ast.Expr):
		return self.visit(node.value)
		
	def visit_Constant(self, node: ast.Constant):
		if isinstance(node.value, bool):
			return ir.Constant(I1, int(node.value))
		if isinstance(node.value, int):
			return ir.Constant(I32, node.value)
		raise CompileError("solo literales int/bool")
		
	def visit_Name(self, node: ast.Name):
		if isinstance(node.ctx, ast.Load):
			alloca = self.context.locals.get(node.id)
			if alloca is None:
				alloca = self.context.get_or_alloca(node.id, I32)
			return self.context.builder.load(alloca, name=node.id + '_val')
		elif isinstance(node.ctx, ast.Store):
			return node.id
		else:
			raise CompileError("Name ctx no soportado")
			
	def visit_Assign(self, node: ast.Assign):
		assert len(node.targets) == 1
		tgt = node.targets[0]
		val = self.visit(node.value)
		
		if isinstance(tgt, ast.Name):
			# Si RHS es i32* -> tipar variable como i32*
			if isinstance(val.type, ir.PointerType) and val.type.pointee == I32:
				alloca = self.context.get_or_alloca(tgt.id, I32.as_pointer())
				self.context.builder.store(val, alloca)
				return val
			# En otro caso, almacenar como i32
			ival = self._as_i32(val)
			alloca = self.context.get_or_alloca(tgt.id, I32)
			self.context.builder.store(ival, alloca)
			return ival
			
		elif isinstance(tgt, ast.Subscript):
			base_ptr = self._eval_array_base_ptr(tgt.value)
			idx = self._as_i32(self.visit(getattr(tgt.slice, 'value', tgt.slice)))
			elem_ptr = self.context.builder.gep(base_ptr, [idx], inbounds=True)
			self.context.builder.store(self._as_i32(val), elem_ptr)
			return val
			
		else:
			raise CompileError("asignación compleja no soportada")
			
	# --- Arreglos
	def _builtin_array(self, nval: ir.Value):
		n_i32 = self._as_i32(nval)
		# Devuelve i32* (alloca i32, n) en 'entry'
		# Nombre único por llamada para evitar colisiones de símbolo
		return self.context.create_alloca(f'arr_{len(self.context.locals)}', I32, count=n_i32)
		
	def _eval_array_base_ptr(self, node: ast.AST) -> ir.Value:
		if isinstance(node, ast.Name):
			slot = self.context.locals.get(node.id)
			if slot is None:
				# si no existe, defínelo como i32* (el usuario debe asignarle array(n) antes de usar)
				slot = self.context.get_or_alloca(node.id, I32.as_pointer())
			ptr = self.context.builder.load(slot, name=node.id + '_ptr')
			return ptr
		raise CompileError("solo a[i] con 'a' como Name")
		
	def visit_Subscript(self, node: ast.Subscript):
		base_ptr = self._eval_array_base_ptr(node.value)
		idx = self._as_i32(self.visit(getattr(node.slice, 'value', node.slice)))
		elem_ptr = self.context.builder.gep(base_ptr, [idx], inbounds=True)
		return self.context.builder.load(elem_ptr, name='elem')
		
	# --- Unarios
	def visit_UnaryOp(self, node: ast.UnaryOp):
		v = self._as_i32(self.visit(node.operand))
		if isinstance(node.op, ast.UAdd):
			return v
		if isinstance(node.op, ast.USub):
			return self.context.builder.sub(ir.Constant(I32, 0), v, name='neg')
		raise CompileError("solo unarios + y -")
		
	# --- Binarios
	def visit_BinOp(self, node: ast.BinOp):
		lhs = self._as_i32(self.visit(node.left))
		rhs = self._as_i32(self.visit(node.right))
		b = self.context.builder
		if isinstance(node.op, ast.Add):      return b.add(lhs, rhs, name='add')
		if isinstance(node.op, ast.Sub):      return b.sub(lhs, rhs, name='sub')
		if isinstance(node.op, ast.Mult):     return b.mul(lhs, rhs, name='mul')
		if isinstance(node.op, ast.FloorDiv): return b.sdiv(lhs, rhs, name='sdiv')
		if isinstance(node.op, ast.Mod):      return b.srem(lhs, rhs, name='srem')
		raise CompileError("operador binario no soportado")
		
	# --- Comparaciones (-> i1)
	def visit_Compare(self, node: ast.Compare):
		assert len(node.ops) == 1 and len(node.comparators) == 1, "comparación encadenada no soportada"
		lhs = self._as_i32(self.visit(node.left))
		rhs = self._as_i32(self.visit(node.comparators[0]))
		op = node.ops[0]
		pred_map = {
			ast.Lt  :'<',
			ast.LtE :'<=',
			ast.Gt  :'>',
			ast.GtE :'>=',
			ast.Eq  :'==',
			ast.NotEq:'!='
		}
		return self.context.builder.icmp_signed(pred_map[type(op)], lhs, rhs, name='cmp')
		
	# --- Llamadas
	def visit_Call(self, node: ast.Call):
		if isinstance(node.func, ast.Name):
			fname = node.func.id
			# print(expr)
			if fname == 'print':
				if len(node.args) != 1:
					raise CompileError("print(expr) espera 1 arg")
				val = self._as_i32(self.visit(node.args[0]))
				b = self.context.builder
				fmt_ptr = b.gep(self.fmt_str, [ir.Constant(I32, 0), ir.Constant(I32, 0)], inbounds=True)
				b.call(self.printf, [fmt_ptr, val])
				return ir.Constant(I32, 0)
			# array(n)
			if fname == 'array':
				if len(node.args) != 1:
					raise CompileError("array(n) espera 1 arg")
				return self._builtin_array(self.visit(node.args[0]))
			# función de usuario
			if fname not in self.functions:
				raise CompileError(f"función desconocida '{fname}'")
			fn = self.functions[fname]
			if len(node.args) != len(fn.args):
				raise CompileError(f"arity mismatch llamando a {fname}")
			args = [self._as_i32(self.visit(a)) for a in node.args]
			return self.context.builder.call(fn, args, name='call_' + fname)
		raise CompileError("llamada no soportada")
		
	# --- Control de flujo
	def visit_If(self, node: ast.If):
		cond = self._as_i1(self.visit(node.test))
		b = self.context.builder
		then_bb = self.context.func.append_basic_block('then')
		else_bb = self.context.func.append_basic_block('else')
		cont_bb = self.context.func.append_basic_block('endif')
		b.cbranch(cond, then_bb, else_bb)
		
		b.position_at_end(then_bb)
		for st in node.body:
			self.visit(st)
		if not b.block.is_terminated:
			b.branch(cont_bb)
			
		b.position_at_end(else_bb)
		for st in node.orelse:
			self.visit(st)
		if not b.block.is_terminated:
			b.branch(cont_bb)
			
		b.position_at_end(cont_bb)
		return ir.Constant(I32, 0)
		
	def visit_While(self, node: ast.While):
		func = self.context.func
		b = self.context.builder
		test_bb = func.append_basic_block('while_test')
		body_bb = func.append_basic_block('while_body')
		done_bb = func.append_basic_block('while_done')
		
		b.branch(test_bb)
		
		b.position_at_end(test_bb)
		cond = self._as_i1(self.visit(node.test))
		b.cbranch(cond, body_bb, done_bb)
		
		b.position_at_end(body_bb)
		for st in node.body:
			self.visit(st)
		if not b.block.is_terminated:
			b.branch(test_bb)
			
		b.position_at_end(done_bb)
		return ir.Constant(I32, 0)
		
	# helper opcional
	def _name(self, ident: str, load: bool) -> ast.Name:
		return ast.Name(id=ident, ctx=ast.Load() if load else ast.Store())
		
	def visit_For(self, node: ast.For):
		# for i in range(start, stop, step_const!=0)
		assert isinstance(node.target, ast.Name)
		assert isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'range'
		args = node.iter.args
		if len(args) == 1:
			start = ast.Constant(value=0); stop = args[0]; step = ast.Constant(value=1)
		elif len(args) == 2:
			start, stop = args; step = ast.Constant(value=1)
		elif len(args) == 3:
			start, stop, step = args
		else:
			raise CompileError("range() arity 1..3")
			
		if not isinstance(step, ast.Constant) or not isinstance(step.value, int) or step.value == 0:
			raise CompileError("range step debe ser entero constante distinto de 0")
		s = step.value
		
		var = node.target.id
		
		# i = start
		init_assign = ast.Assign(
			targets=[ast.Name(id=var, ctx=ast.Store())],
			value=start
		)
		self.visit(init_assign)
		
		# while ( s>0 ? i < stop : i > stop )
		test_op = ast.Lt() if s > 0 else ast.Gt()
		test = ast.Compare(
			left=ast.Name(id=var, ctx=ast.Load()),
			ops=[test_op],
			comparators=[stop]
		)
		
		# i = i + s
		incr = ast.Assign(
			targets=[ast.Name(id=var, ctx=ast.Store())],
			value=ast.BinOp(
				left=ast.Name(id=var, ctx=ast.Load()),
				op=ast.Add(),
				right=ast.Constant(value=s)
			)
		)
		
		# while (...) { body; i = i + s }
		return self.visit(ast.While(test=test, body=node.body + [incr]))
		
	def visit_Return(self, node: ast.Return):
		if node.value is None:
			self.context.builder.ret(ir.Constant(I32, 0))
		else:
			v = self._as_i32(self.visit(node.value))
			self.context.builder.ret(v)
		return ir.Constant(I32, 0)
		
	# Fallback
	def generic_visit(self, node):
		raise CompileError(f"Unsupported AST node: {type(node).__name__}")
		
def main():
	ap = argparse.ArgumentParser()
	ap.add_argument('source', help='Archivo .py (subconjunto)')
	args = ap.parse_args()
	with open(args.source, 'r', encoding='utf-8') as f:
		src = f.read()
	comp = LLVMCompiler()
	ir_txt = comp.compile(src)
	print(ir_txt)
	
if __name__ == "__main__":
	main()

