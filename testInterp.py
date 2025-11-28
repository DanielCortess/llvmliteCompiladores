# testInterp.py
import sys
from lexer import Lexer
from parser import Parser
from context import Context
from interp import Interpreter

def main():
    # Nombre del archivo fuente (por defecto knight.bminor)
    filename = sys.argv[1] if len(sys.argv) > 1 else "knight.bminor"

    print(f"== Ejecutando intérprete para {filename} ==\n")

    # Leer código fuente
    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()

    # Crear contexto de compilación
    ctxt = Context(filename, source)

    # Analizador léxico y sintáctico
    lexer = Lexer()
    parser = Parser()
    ast = parser.parse(lexer.tokenize(source))

    if ctxt.have_errors:
        print("Se encontraron errores durante el análisis sintáctico o léxico.")
        ctxt.show_errors()
        return

    print("Análisis sintáctico exitoso. Ejecutando intérprete...\n")

    # Ejecutar el intérprete
    interp = Interpreter(ctxt)
    interp.interpret(ast)

    print("\n\n== Ejecución finalizada ==")

if __name__ == "__main__":
    main()
