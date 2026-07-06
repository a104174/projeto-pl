import argparse
import sys

from src.parser import parse
from src.codegen import generate_program, CodeGenerationError


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

    arg_parser.add_argument(
        "-o",
        "--output",
        help="Ficheiro onde guardar o código EWVM gerado"
    )

    args = arg_parser.parse_args()

    try:
        ewvm_code = compile_file(args.input_file)

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