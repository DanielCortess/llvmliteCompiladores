# lexer.py
#
# Analizador Léxico para el lenguaje B-Minor (SLY)

import sly


class Lexer(sly.Lexer):
    # === Conjunto de TOKENS ===
    tokens = {
        # Palabras reservadas / tipos / control
        'ARRAY', 'AUTO', 'BOOLEAN', 'CHAR', 'ELSE', 'FALSE', 'FLOAT', 'FOR', 'FUNCTION',
        'IF', 'INTEGER', 'PRINT', 'RETURN', 'STRING', 'TRUE', 'VOID', 'WHILE',

        # Identificadores
        'ID',

        # Literales de la gramática
        'INT_LITERAL', 'FLOAT_LITERAL', 'CHAR_LITERAL', 'STRING_LITERAL',

        # Operadores lógicos / relacionales / unarios
        'LOR', 'LAND', 'EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'INC', 'DEC', 'NOT',

        ##Extensión

        'DOWHILE',
        'SWITCH','CASE','DEFAULT','BREAK'

    }

    # Símbolos de un carácter
    literals = '+-*/%^=()[]{}:;,'

    # === Espacios en blanco e ignorados ===
    ignore = ' \t\r'

    @_(r'\n+')
    def ignore_newline(self, t):
        self.lineno += t.value.count('\n')

    # Comentarios estilo C++ y C
    @_(r'//.*')
    def ignore_cppcomment(self, t):
        pass

    @_(r'/\*(.|\n)*?\*/')
    def ignore_comment(self, t):
        self.lineno += t.value.count('\n')

    # === Palabras reservadas e identificadores ===
    ID = r'[A-Za-z_]\w*'

    def ID(self, t):
        kw = t.value.lower()
        keywords = {
            'array': 'ARRAY',
            'auto': 'AUTO',
            'boolean': 'BOOLEAN',
            'char': 'CHAR',
            'else': 'ELSE',
            'false': 'FALSE',
            'float': 'FLOAT',
            'for': 'FOR',
            'function': 'FUNCTION',
            'if': 'IF',
            'integer': 'INTEGER',
            'print': 'PRINT',
            'return': 'RETURN',
            'string': 'STRING',
            'true': 'TRUE',
            'void': 'VOID',
            'while': 'WHILE',
            'do': 'DOWHILE',
            'switch': 'SWITCH',
            'case': 'CASE',
            'default': 'DEFAULT',
            'break': 'BREAK',
        }
        if kw in keywords:
            t.type = keywords[kw]
        return t

    # === Operadores multi-caracter ===
    @_(r'\|\|')
    def LOR(self, t): return t

    @_(r'&&')
    def LAND(self, t): return t

    @_(r'==')
    def EQ(self, t): return t

    @_(r'!=')
    def NE(self, t): return t

    @_(r'<=')
    def LE(self, t): return t

    @_(r'>=')
    def GE(self, t): return t

    @_(r'\+\+')
    def INC(self, t): return t

    @_(r'--')
    def DEC(self, t): return t

    # Operadores de un solo caracter que son tokens
    @_(r'<')
    def LT(self, t): return t

    @_(r'>')
    def GT(self, t): return t

    @_(r'!')
    def NOT(self, t): return t

    @_(r'\.\.')
    def FLOAT_ERROR(self, t):
        return self.error(t)

    # === Literales ===
    @_(r'(?:(?:\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)')
    def FLOAT_LITERAL(self, t):
        try:
            t.value = float(t.value)
        except ValueError:
            pass
        return t

    @_(r'\d+')
    def INT_LITERAL(self, t):
        try:
            t.value = int(t.value)
        except ValueError:
            pass
        return t

    @_(r"'([^\\']|\\.)'")
    def CHAR_LITERAL(self, t):
        raw = t.value[1:-1]
        try:
            t.value = bytes(raw, 'utf-8').decode('unicode_escape')
        except Exception:
            t.value = raw
        return t

    @_(r'"([^\\"]|\\.)*"')
    def STRING_LITERAL(self, t):
        raw = t.value[1:-1]
        try:
            t.value = bytes(raw, 'utf-8').decode('unicode_escape')
        except Exception:
            t.value = raw
        return t
    
    @_(r'/\*[^*]*$')
    def UNCLOSED_COMMENT(self, t):
        return self.error(t)
    
    def error(self, t):
        raise Exception(f"Lexical error at line {self.lineno}: illegal character '{t.value[0]}'")

def tokenize(txt: str):
    lexer = Lexer()
    for tok in lexer.tokenize(txt):
        print(tok)

if __name__ == '__main__':
    import sys
    print(sys.argv)
    if len(sys.argv) != 3 or sys.argv[1] != "--scan":
        print("usage: python lexer.py --scan filename")
        sys.exit(1)
    with open(sys.argv[2], encoding='utf-8') as f:
        tokenize(f.read())
