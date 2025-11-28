# Pruebas completas para py2llvmlite

# 1. Asignaciones y literales
a = 10
b = 3
c = -5
d = +7

print(a)
print(b)
print(c)
print(d)

# 2. Binarios
suma       = a + b
resta      = a - b
producto   = a * b
division   = a // b
modulo     = a % b

print(suma)
print(resta)
print(producto)
print(division)
print(modulo)

# 3. Comparaciones
print(a < b)
print(a <= b)
print(a > b)
print(a >= b)
print(a == b)
print(a != b)

# 4. If / else básico
if a > b:
    x = 100
else:
    x = 200

print(x)

# 5. If / else anidado
if a < b:
    y = 1
else:
    if b < c:
        y = 2
    else:
        y = 3

print(y)

# 6. While simple
i = 0
total = 0

while i < 5:
    total = total + i
    i = i + 1

print(total)  # 0+1+2+3+4 = 10

# 7. While con condición calculada
j = 3

while j != 0:
    print(j)
    j = j - 1
