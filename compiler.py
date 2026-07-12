import argparse
import sys
from pprint import pprint

from src.lexer import tokenize
from src.parser import parse
from src.codegen import generate_program, CodeGenerationError
from src.semantic import check_program


def compile_file(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)
    return generate_program(ast)


def main():
    arg_parser = argparse.ArgumentParser(
        description="Compilador Pascal para EWVM"
    )

    arg_parser.add_argument(
        "input_file",
        help="Ficheiro Pascal de entrada"
    )
    diagnostics = arg_parser.add_mutually_exclusive_group()
    diagnostics.add_argument("--tokens", action="store_true", help="Mostrar tokens e terminar")
    diagnostics.add_argument("--ast", action="store_true", help="Mostrar a AST e terminar")
    diagnostics.add_argument("--symbols", action="store_true", help="Mostrar a tabela de símbolos e terminar")

    arg_parser.add_argument(
        "-o",
        "--output",
        help="Ficheiro onde guardar o código EWVM gerado"
    )

    args = arg_parser.parse_args()

    try:
        with open(args.input_file, "r", encoding="utf-8") as source_file:
            source = source_file.read()

        if args.tokens:
            for token in tokenize(source):
                print(token)
            return

        ast = parse(source)
        if args.ast:
            pprint(ast)
            return

        if args.symbols:
            symbols, errors = check_program(ast)
            pprint(symbols.diagnostic_view())
            if errors:
                raise CodeGenerationError(
                    "Erros semânticos:\n" + "\n".join(f"- {error}" for error in errors)
                )
            return

        ewvm_code = generate_program(ast)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(ewvm_code)
        else:
            print(ewvm_code, end="")

    except SyntaxError as error:
        print(f"Erro sintático: {error}", file=sys.stderr)
        sys.exit(1)

    except CodeGenerationError as error:
        print(f"Erro de compilação: {error}", file=sys.stderr)
        sys.exit(1)

    except OSError as error:
        print(f"Erro ao ler/escrever ficheiro: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
