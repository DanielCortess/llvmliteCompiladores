# context.py
class Context:
    def __init__(self, filename, source):
        self.filename = filename
        self.source = source
        self.errors = []

    @property
    def have_errors(self):
        return len(self.errors) > 0

    def error(self, position, message):
        """Registra un error."""
        if hasattr(position, 'lineno'):
            line = position.lineno
        elif isinstance(position, int):
            line = position
        else:
            line = '?'
        self.errors.append(f"{line}: {message}")

    def show_errors(self):
        """Muestra los errores acumulados."""
        for err in self.errors:
            print(f"{err}")

    def find_source(self, node):
        """Retorna el texto fuente asociado a un nodo, si es posible."""
        try:
            return self.source[node.index]
        except:
            return str(node)
