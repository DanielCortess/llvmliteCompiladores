#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
py2llvmlite.py — Genera **únicamente** texto LLVM IR usando llvmlite.ir
(no usa llvmlite.binding, no hace JIT ni emite .o). Pensado para compilar luego con clang.

Subconjunto soportado:
  - int y bool
  - variables (int)
  - asignación: a = expr
  - binarios: +, -, *, // (sdiv), % (srem)
  - unarios: +x, -x
  - comparaciones: <, <=, >, >=, ==, !=  (icmp i32 -> i1)
  - if/else
  - while
  - print(expr) -> printf("%d\n", expr)

Uso:
  pip install llvmlite
  python3 py2llvmlite.py programa.py > out.ll
  clang out.ll -O2 -o prog
  ./prog
"""
import ast
import argparse
from typing   import Dict
from llvmlite import ir  # solo módulo IR (sin binding)

BINOPS = {
	ast.Add: "add",
	ast.Sub: "sub",
	ast.Mult: "mul",
	ast.FloorDiv: "sdiv",
	ast.Mod: "srem",
}

CMP_PRED = {
	ast.Lt:  "<",
	ast.LtE: "<=",
	ast.Gt:  ">",
	ast.GtE: ">=",
	ast.Eq:  "==",
	ast.NotEq: "!=",
}

class Codegen:
	def __init__(self, module_name="module"):
		self.module = ir.Module(name=module_name)
		self.builder: ir.IRBuilder | None = None
		self.func: ir.Function | None = None
		self.vars: Dict[str, ir.AllocaInstr] = {}
		# tipos
		self.i32 = ir.IntType(32)
		self.i1  = ir.IntType(1)
		self.i8  = ir.IntType(8)
		# runtime: printf y formato
		self.printf: ir.Function | None = None
		self.fmt_global: ir.GlobalVariable | None = None
		
	# --- runtime ---
	def declare_printf(self):
		if self.printf is not None:
			return
		printf_ty = ir.FunctionType(self.i32, [self.i8.as_pointer()], var_arg=True)
		self.printf = ir.Function(self.module, printf_ty, name="printf")
		fmt_bytes = b"%d\n\x00"
		arr_ty = ir.ArrayType(self.i8, len(fmt_bytes))
		self.fmt_global = ir.GlobalVariable(self.module, arr_ty, name=".fmt")
		self.fmt_global.linkage = 'private'
		self.fmt_global.global_constant = True
		self.fmt_global.initializer = ir.Constant(arr_ty, bytearray(fmt_bytes))
		
	def gep_fmt(self):
		zero = ir.Constant(self.i32, 0)
		return self.builder.gep(self.fmt_global, [zero, zero], inbounds=True)
		
	# --- main ---
	def begin_main(self):
		fnty = ir.FunctionType(self.i32, [])
		self.func = ir.Function(self.module, fnty, name="main")
		entry = self.func.append_basic_block("entry")
		self.builder = ir.IRBuilder(entry)
		
	def end_main(self):
		b = self.builder
		assert b is not None
		if b.block.terminator is None:
			b.ret(self.i32(0))
			
	# --- vars ---
	def ensure_alloca(self, name: str):
		if name in self.vars:
			return self.vars[name]
		b = self.builder
		assert b is not None
		with b.goto_entry_block():
			ptr = b.alloca(self.i32, name=f"{name}_ptr")
		self.vars[name] = ptr
		return ptr
		
	# --- exprs ---
	def as_i32(self, node: ast.AST) -> ir.Value:
		b = self.builder
		assert b is not None
		if isinstance(node, ast.Constant):
			if isinstance(node.value, bool):
				return self.i32(1 if node.value else 0)
			if isinstance(node.value, int):
				return self.i32(node.value)
			raise NotImplementedError(f"Literal no soportado: {node.value!r}")
		if isinstance(node, ast.Name):
			ptr = self.ensure_alloca(node.id)
			return b.load(ptr)
		if isinstance(node, ast.UnaryOp):
			if isinstance(node.op, ast.UAdd):
				return self.as_i32(node.operand)
			if isinstance(node.op, ast.USub):
				v = self.as_i32(node.operand)
				return b.sub(self.i32(0), v)
			raise NotImplementedError(f"Unario no soportado: {ast.dump(node.op)}")
		if isinstance(node, ast.BinOp):
			op = BINOPS.get(type(node.op))
			if not op:
				raise NotImplementedError(f"Binario no soportado: {ast.dump(node.op)}")
			l = self.as_i32(node.left)
			r = self.as_i32(node.right)
			return getattr(b, op)(l, r)
		if isinstance(node, ast.Compare):
			if len(node.ops) != 1 or len(node.comparators) != 1:
				raise NotImplementedError("Comparaciones encadenadas no soportadas.")
			pred = CMP_PRED.get(type(node.ops[0]))
			if not pred:
				raise NotImplementedError(f"Comparador no soportado: {ast.dump(node.ops[0])}")
			l = self.as_i32(node.left)
			r = self.as_i32(node.comparators[0])
			return b.icmp_signed(pred, l, r)  # i1
		if isinstance(node, ast.Call):
			# print(expr)
			if isinstance(node.func, ast.Name) and node.func.id == "print":
				if len(node.args) != 1:
					raise NotImplementedError("print() soporta exactamente 1 argumento.")
				self.declare_printf()
				v = self.as_i32(node.args[0])
				# si es i1, zext a i32
				if isinstance(v.type, ir.IntType) and v.type.width == 1:
					v = b.zext(v, self.i32)
				fmtp = self.gep_fmt()
				b.call(self.printf, [fmtp, v])
				return self.i32(0)
			raise NotImplementedError(f"Llamada no soportada: {ast.dump(node)}")
		raise NotImplementedError(f"Expresión no soportada: {ast.dump(node)}")
		
	# --- stmts ---
	def compile_stmt(self, node: ast.AST):
		b = self.builder
		assert b is not None
		if isinstance(node, ast.Expr):
			_ = self.as_i32(node.value)
			return
		if isinstance(node, ast.Assign):
			if len(node.targets) != 1:
				raise NotImplementedError("Asignación múltiple no soportada.")
			target = node.targets[0]
			if not isinstance(target, ast.Name):
				raise NotImplementedError("Asignación solo a variables simples.")
			ptr = self.ensure_alloca(target.id)
			val = self.as_i32(node.value)
			# si viene de icmp i1, zext a i32
			if isinstance(val.type, ir.IntType) and val.type.width == 1:
				val = b.zext(val, self.i32)
			b.store(val, ptr)
			return
		if isinstance(node, ast.If):
			cond = self.as_i32(node.test)
			# normalizar a i1
			if isinstance(cond.type, ir.IntType) and cond.type.width != 1:
				cond = b.icmp_signed('!=', cond, self.i32(0))
			then_bb = self.func.append_basic_block('then')
			else_bb = self.func.append_basic_block('else')
			end_bb  = self.func.append_basic_block('endif')
			b.cbranch(cond, then_bb, else_bb)
			# then
			b.position_at_end(then_bb)
			for s in node.body:
				self.compile_stmt(s)
			if b.block.terminator is None:
				b.branch(end_bb)
			# else
			b.position_at_end(else_bb)
			for s in node.orelse or []:
				self.compile_stmt(s)
			if b.block.terminator is None:
				b.branch(end_bb)
			# end
			b.position_at_end(end_bb)
			return
		if isinstance(node, ast.While):
			cond_bb = self.func.append_basic_block('while.cond')
			body_bb = self.func.append_basic_block('while.body')
			end_bb  = self.func.append_basic_block('while.end')
			b.branch(cond_bb)
			b.position_at_end(cond_bb)
			cond = self.as_i32(node.test)
			if isinstance(cond.type, ir.IntType) and cond.type.width != 1:
				cond = b.icmp_signed('!=', cond, self.i32(0))
			b.cbranch(cond, body_bb, end_bb)
			b.position_at_end(body_bb)
			for s in node.body:
				self.compile_stmt(s)
			if b.block.terminator is None:
				b.branch(cond_bb)
			b.position_at_end(end_bb)
			return
		raise NotImplementedError(f"Nodo no soportado: {node.__class__.__name__}: {ast.dump(node)}")
		
	def compile_module(self, source: str) -> ir.Module:
		self.begin_main()
		tree = ast.parse(source)
		for stmt in tree.body:
			self.compile_stmt(stmt)
		self.end_main()
		return self.module
		
def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("source", help="Archivo .py (subconjunto)")
	args = ap.parse_args()
	with open(args.source, "r", encoding="utf-8") as f:
		src = f.read()
	cg = Codegen("py2llvmlite")
	mod = cg.compile_module(src)
	print(str(mod))
	
if __name__ == "__main__":
	main()

