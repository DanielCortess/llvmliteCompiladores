# Ejemplo completo para pyast_llvmir.py

# --- Función que calcula factorial ---
def fact(n):
    r = 1
    i = 1
    while i <= n:
        r = r * i
        i = i + 1
    return r

# --- Función que suma los elementos de un arreglo ---
def sum_array(arr, n):
    i = 0
    s = 0
    while i < n:
        s = s + arr[i]
        i = i + 1
    return s

# --- Programa principal (implícito) ---
print( fact(5) )       # 120

a = array(5)           # crea array de tamaño 5
a[0] = 10
a[1] = 20
a[2] = 30
a[3] = 40
a[4] = 50

print( sum_array(a, 5) )   # imprime 150

# ejemplo de for descompuesto por el compilador
s = 0
for i in range(1, 6):
    s = s + i

print(s)   # imprime 15

# if / else
x = 10
if x > 5:
    print(1)
else:
    print(0)
