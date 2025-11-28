import argparse
import sys
from lexer import Lexer

def scan_file(filename):
    try:
        with open(filename, 'r') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"    File doest exist'{filename}'", file=sys.stderr)
        sys.exit(1)

    lexer = Lexer()
    try:
        for token in lexer.tokenize(data):
            print(token)
        sys.exit(0)
    except Exception as e:
        print(f"    {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="B-Minor Compiler")
    parser.add_argument('--scan', help='Scan file .bminor')
    args = parser.parse_args()

    if args.scan:
        scan_file(args.scan)
    else:
        print("Uso: python bminor.py --scan archivo.bminor", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()  