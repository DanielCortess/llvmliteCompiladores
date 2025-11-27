'''
llvm.py

En este archivo, el compilador generará la salida LLVM. No lo inicie a menos que haya completado el Tutorial de LLVM en:

		docs/Tutorial_LLVMlite.md

Una vez hecho esto, vuelve aquí.

La estrategia general será muy similar a la de la verificación de tipos. Recuerda que en la verificación de tipos existía un contexto y funciones como estas:

		def check(node, context):
			...

Aquí la idea será prácticamente la misma. Crearás una clase especial LLVMContext. Dentro de esa clase, incluirás los detalles habituales, como el entorno, pero también configurarás objetos relacionados con la generación de LLVM. Por ejemplo:


		class LLVMContext:
			def __init__(self):
				# Tracking of variables (similar to type-checking)
				self.env = { }
				
				# LLVM Code generation
				self.module = ir.Module('bminor')
				self.function = ir.Function(self.module,
					ir.FunctionType(VoidType(), []),
					name='main')
				self.block = self.function.append_basic_block()
				self.builder = ir.IRBuilder(self.block)


La generación posterior de código interactuará principalmente con el objeto "constructor". Por ejemplo:

			def generate(node, context):
				if isinstance(node, Integer):
					return ('int', ir.Constant(int_type, int(node.value)))
				
				elif isinstance(node, BinOp):
					left_type, left_val = generate(node.left, context)
					right_type, right_val = generate(node.right, context)
					if left_type == 'float':
						if node.op == '+':
							return ('float', context.builder.fadd(left_val, right_val))
							
							...
							
					elif left_type == 'int':
						if node.op == '+':
							return ('int', context.builder.add(left_val, right_val))
							
							...

A diferencia del código para una máquina de pila, LLVM se basa en registros. Cada operación debe devolver un tipo junto con el resultado "register". En el código anterior, observe con atención cómo se utilizan conjuntamente los tipos y los valores en las distintas operaciones. Por ejemplo:


		left_type, left_var = generate(node.left, context)

A primera vista, esto parece muy similar al intérprete que usted escribió. Sin embargo, LLVM no es un intérprete. Es un generador de código.
En este ejemplo, "left_var" es la ubicación donde se colocó un valor durante la generación de código. LLVM no está ejecutando el código.

De nuevo, es fundamental leer el tutorial de LLVM en docs/LLVM_Tutorial.md.
Además, hay algunas notas sobre el flujo de control de LLVM en docs/Control-Flow.md.
'''

from llvmlite import ir
from model    import *

# Definir los tipos LLVM correspondientes a los tipos bminor
int_type   = ir.IntType(32)
float_type = ir.DoubleType()
bool_type  = ir.IntType(1)
char_type  = ir.IntType(8)
void_type  = ir.VoidType()

# Asignación de tipos bminor a tipos LLVM
_typemap = {
	'integer': int_type,
	'float'  : float_type,
	'boolean': bool_type,
	'char'   : char_type,
}

# El módulo/entorno LLVM que bminor está rellenando
class LLVMContext:
	def __init__(self):
		self.env = { }
		self.module = ir.Module('bminor')
		self.function = ir.Function(self.module,
		ir.FunctionType(void_type, []),
		name='main')
		self.block = self.function.append_basic_block('entry')
		self.builder = ir.IRBuilder(self.block)
		
		# Declaración de funciones de tiempo de ejecución (véase runtime.c)
		self._printi = ir.Function(self.module,
		ir.FunctionType(void_type, [int_type]),
		name='_printi')
		self._printf = ir.Function(self.module,
		ir.FunctionType(void_type, [float_type]),
		name='_printf')
		self._printb = ir.Function(self.module,
		ir.FunctionType(void_type, [bool_type]),
		name='_printb')
		self._printc = ir.Function(self.module,
		ir.FunctionType(void_type, [char_type]),
		name='_printc')
		
	def __str__(self):
		return str(self.module)
		
		
# Función de nivel superior
def generate_program(program):
	context = LLVMContext()
	generate(program.model, context)
	context.builder.ret_void()
	return str(context)
	
# Función interna para generar código para cada tipo de nodo
def generate(node, context):
	if isinstance(node, Integer):
		return ('int', ir.Constant(int_type, int(node.value)))
		
	elif isinstance(node, PrintStatement):
		ty, var = generate(node.eval, context)
		if ty == 'int':
			context.builder.call(context._printi, [var])
		return None
		
	else:
		raise RuntimeError(f"No se puede generar código para {node}")
		
# Programa principal de ejemplo que ejecuta el compilador
def main(filename):
	from parser    import parse_file
	from typecheck import check_program

	program = parse_file(filename)
	if check_program(program):
		code = generate_program(program)
		with open('out.ll', 'w') as file:
			file.write(code)
		print('Wrote out.ll')
		
if __name__ == '__main__':
	import sys
	main(sys.argv[1])
	

