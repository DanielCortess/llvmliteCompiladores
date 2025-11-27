# Guía rápida de **llvmlite** (versión didáctica, en español)

Pequeña chuleta práctica para generar **LLVM IR** desde Python usando `llvmlite.ir`. Pensada para cursos de compiladores (p. ej. bminor/Wabbit): cubre lo mínimo para **emitir IR**, enlazar con `printf`, manejar variables, control de flujo y arreglos básicos.

> Instalación: `pip install llvmlite`  
> Documentación oficial (en inglés): https://llvmlite.readthedocs.io/en/latest/user-guide/ir/ir.html

---

## 1) Estructura mental (cómo piensa llvmlite)

- **Módulo** (`ir.Module`): el archivo IR (como un `.ll`).  
- **Función** (`ir.Function`): código ejecutable con una firma de tipos.  
- **Bloque básico**: secuencia lineal de instrucciones con un único salto al final.  
- **IRBuilder**: “lapicero” que **emite** instrucciones en el bloque actual.  
- **Tipos**: enteros (`i1`, `i8`, `i32`…), `double`, `void`, punteros, arreglos, structs.

Patrón típico:
```python
from llvmlite import ir
m = ir.Module(name="m")
i32, f64, i8 = ir.IntType(32), ir.DoubleType(), ir.IntType(8)
ft = ir.FunctionType(i32, ())           # int main()
fn = ir.Function(m, ft, name="main")
bb = fn.append_basic_block("entry")
b  = ir.IRBuilder(bb)
# ... emitir instrucciones ...
b.ret(ir.Constant(i32, 0))
print(m)
```

---

## 2) Tipos y constantes esenciales

```python
i1  = ir.IntType(1)
i8  = ir.IntType(8)
i32 = ir.IntType(32)
f64 = ir.DoubleType()
void= ir.VoidType()

c0  = ir.Constant(i32, 0)
c1  = ir.Constant(i32, 1)
pi  = ir.Constant(f64, 3.14159)
```

**Punteros y arreglos**
```python
i8ptr     = i8.as_pointer()             # i8*
arr10_i32 = ir.ArrayType(i32, 10)       # [10 x i32]
```

---

## 3) Variables locales (alloca, store, load)

- `alloca(T)` reserva un **slot** en la pila de la función (como una variable local).  
- Usa `store(valor, ptr)` para escribir y `load(ptr)` para leer.

```python
x = b.alloca(i32, name="x")             # i32* %x
b.store(ir.Constant(i32, 42), x)
vx = b.load(x, name="vx")               # i32 %vx
```

> **Tip:** crea los `alloca` al inicio de la función (entry block). Luego puedes optimizar con `opt -mem2reg` para SSA.

---

## 4) Aritmética y conversiones

**Enteros**
```python
a = b.add(vx, ir.Constant(i32, 8))      # add i32
s = b.sub(a, ir.Constant(i32, 2))
m = b.mul(a, s)
q = b.sdiv(m, ir.Constant(i32, 3))      # signed div
```

**Punto flotante (double)**
```python
fa = b.fadd(ir.Constant(f64, 1.0), ir.Constant(f64, 2.0))
fm = b.fmul(fa, ir.Constant(f64, 3.0))
```

**Conversiones**
```python
i_as_f = b.sitofp(vx, f64)              # i32 -> double
f_as_i = b.fptosi(fa, i32)              # double -> i32
z_i32  = b.zext(ir.Constant(i1,1), i32) # i1 -> i32 (cero-extensión)
```

---

## 5) Comparaciones y booleanos (`i1`)

```python
is_lt = b.icmp_signed("<",  vx, ir.Constant(i32, 10)) # i1
is_ge = b.icmp_signed(">=", vx, ir.Constant(i32, 0))
f_lt  = b.fcmp_ordered("<", ir.Constant(f64,2.0), ir.Constant(f64,3.0))  # i1

andv = b.and_(is_lt, is_ge)            # i1
orv  = b.or_(is_lt, f_lt)              # i1
notv = b.not_(is_lt)                   # i1
```

> Muchas operaciones lógicas y condicionales **esperan i1**. Si necesitas imprimir/usar como `i32`, convierte con `zext`.

---

## 6) Control de flujo (if/while/for)

### If / Else (esqueleto)
```python
then_bb = b.function.append_basic_block("then")
else_bb = b.function.append_basic_block("else")
end_bb  = b.function.append_basic_block("endif")

cond = b.icmp_signed("!=", vx, ir.Constant(i32,0))   # i1
b.cbranch(cond, then_bb, else_bb)

b.position_at_end(then_bb)
# ... cuerpo then ...
b.branch(end_bb)

b.position_at_end(else_bb)
# ... cuerpo else ...
b.branch(end_bb)

b.position_at_end(end_bb)
```

### While (esqueleto)
```python
fn = b.function
condbb = fn.append_basic_block("while.cond")
bodybb = fn.append_basic_block("while.body")
endbb  = fn.append_basic_block("while.end")

b.branch(condbb)
b.position_at_end(condbb)
c = b.icmp_signed("<", vx, ir.Constant(i32, 10))
b.cbranch(c, bodybb, endbb)

b.position_at_end(bodybb)
# ... cuerpo ...
b.branch(condbb)

b.position_at_end(endbb)
```

### PHI (unir valores de dos caminos)
```python
phi = b.phi(i32, name="v")
phi.add_incoming(ir.Constant(i32, 1), then_bb)
phi.add_incoming(ir.Constant(i32, 0), else_bb)
```

---

## 7) Funciones y llamadas

**Declarar y definir**
```python
add_t = ir.FunctionType(i32, (i32, i32))       # i32 add(i32,i32)
add_f = ir.Function(m, add_t, name="add")
add_f.args[0].name, add_f.args[1].name = "x", "y"

bb = add_f.append_basic_block("entry")
b2 = ir.IRBuilder(bb)
res = b2.add(add_f.args[0], add_f.args[1])
b2.ret(res)
```

**Llamar**
```python
retv = b.call(add_f, (ir.Constant(i32, 40), ir.Constant(i32, 2)))
```

---

## 8) Memoria compuesta: GEP (arrays/structs)

- `gep` calcula la dirección de un **elemento** dentro de un agregado.
- Primer índice suele ser `0` para “entrar” al agregado de un `alloca`/global.

```python
arr = b.alloca(ir.ArrayType(i32, 5), name="A")
zero = ir.Constant(i32, 0)
i3   = ir.Constant(i32, 3)

ptr_elt = b.gep(arr, [zero, i3], inbounds=True)   # i32* &A[3]
b.store(ir.Constant(i32, 99), ptr_elt)
v = b.load(ptr_elt)                                # i32 99
```

---

## 9) Globals y cadenas (para `printf`)

**Formato “%d\n” como global + GEP a i8***
```python
printf_ty = ir.FunctionType(ir.IntType(32), [ir.IntType(8).as_pointer()], var_arg=True)
printf    = ir.Function(m, printf_ty, name="printf")

fmt_bytes = "%d\n\0".encode("utf-8")
fmt_ty = ir.ArrayType(ir.IntType(8), len(fmt_bytes))
gfmt = ir.GlobalVariable(m, fmt_ty, name=".fmt")
gfmt.linkage = "internal"; gfmt.global_constant = True
gfmt.initializer = ir.Constant(fmt_ty, bytearray(fmt_bytes))

fmt_ptr = b.gep(gfmt, [ir.Constant(i32,0), ir.Constant(i32,0)], inbounds=True)  # i8*
b.call(printf, [fmt_ptr, ir.Constant(i32, 42)])
```

**Cadena arbitraria**
```python
msg = "Hola\0".encode("utf-8")
arr_ty = ir.ArrayType(ir.IntType(8), len(msg))
gstr = ir.GlobalVariable(m, arr_ty, name=".str")
gstr.linkage = "internal"; gstr.global_constant = True
gstr.initializer = ir.Constant(arr_ty, bytearray(msg))
cstr_ptr = b.gep(gstr, [ir.Constant(i32,0), ir.Constant(i32,0)], inbounds=True)  # i8*
```

---

## 10) Mini-ejemplo “hola mundo numérico”

```python
from llvmlite import ir

m   = ir.Module(name="demo")
i32 = ir.IntType(32)
i8  = ir.IntType(8)
printf_ty = ir.FunctionType(i32, [i8.as_pointer()], var_arg=True)
printf    = ir.Function(m, printf_ty, name="printf")

main = ir.Function(m, ir.FunctionType(i32, ()), name="main")
bb   = main.append_basic_block("entry")
b    = ir.IRBuilder(bb)

# "%d\n"
fmt = "%d\n\0".encode("utf-8")
fmt_ty = ir.ArrayType(i8, len(fmt))
gfmt = ir.GlobalVariable(m, fmt_ty, name=".fmt")
gfmt.linkage = "internal"; gfmt.global_constant = True
gfmt.initializer = ir.Constant(fmt_ty, bytearray(fmt))
fmt_ptr = b.gep(gfmt, [ir.Constant(i32,0), ir.Constant(i32,0)], inbounds=True)

x = b.alloca(i32, name="x")
b.store(ir.Constant(i32, 40), x)
val = b.load(x)
val = b.add(val, ir.Constant(i32, 2))
b.call(printf, [fmt_ptr, val])
b.ret(ir.Constant(i32, 0))

print(m)
```

Ejecútalo con:
```bash
python tu_script.py > out.ll
lli out.ll
# o
clang out.ll -o prog && ./prog
```

---

## 11) Consejos y errores comunes

- **Posicionamiento del builder**: Emite donde esté el cursor. Usa `position_at_end` antes de generar.  
- **`alloca` en entry**: más fácil para el pase `mem2reg`.  
- **Tipos exactos**: `icmp` vs `fcmp`, `add` vs `fadd`. Mezclar tipos sin castear da errores.  
- **`printf` varargs**: el primer argumento **tipado** es `i8*` del formato; los demás van con su tipo natural.  
- **`gep`**: recuerda el primer índice `0` para entrar a agregados (`alloca`/global).  
- **Booleans**: las comparaciones producen `i1`. Si necesitas `i32`, usa `zext`.  
- **Optimización**: después de generar, pasa `opt`:
  ```bash
  opt -S -mem2reg -instcombine -gvn -simplifycfg in.ll -o out.ll
  ```

---

## 12) Mapa rápido (bminor → llvmlite)

- `var x:int = e;` → `alloca i32`, `store` del valor de `e`.  
- `x = e;` → `load x;` + op de `e` + `store`.  
- `if (c) {A} else {B}` → `icmp/fcmp` → `cbranch` → bloques `then/else` → `branch end`.  
- `while (c) {B}` → bloque `cond` → `cbranch` a `body/end` → `branch cond`.  
- `print e;` → prepara `printf` y su formato → `call`.  
- `A[i]` → `gep(A, [0, i])` → `load/store` del elemento.  

---

¡Lista para usar en tus prácticas! 🚀
