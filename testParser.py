# testParser.py
#
# Script para probar el parser con knight.bminor

import sys
from lexer import Lexer
from parser import Parser

def main():
    if len(sys.argv) != 2:
        print("Uso: python testParser.py archivo.bminor")
        sys.exit(1)

    filename = sys.argv[1]

    # Leer el código fuente
    try:
        with open(filename, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: no se encontró el archivo '{filename}'")
        sys.exit(1)

    # Inicializar lexer y parser
    lexer = Lexer()
    parser = Parser()

    try:
        tokens = lexer.tokenize(source)
        ast = parser.parse(tokens)
        print("Parsing exitoso\n")

        # Si tu parser devuelve un AST tipo objeto, ajusta aquí
        print("AST")
        print(ast)

    except Exception as e:
        print("Error durante parsing:", e)

if __name__ == "__main__":
    main()
