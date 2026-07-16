"""
Ponto de entrada do compilador de Pascal para EWVM.

Este módulo coordena as diferentes fases do compilador:

    código Pascal
        → análise lexical
        → análise sintática e construção da AST
        → análise semântica
        → geração de código EWVM

Pode ser utilizado de duas formas:

1. Como aplicação de linha de comandos, através da função ``main``;
2. Como módulo Python, através da função ``compile_file``.

A interface de linha de comandos também disponibiliza modos de diagnóstico
para observar os tokens, a árvore de sintaxe abstrata e a tabela de símbolos.
"""

import argparse
import sys
from pprint import pprint

from src.lexer import tokenize
from src.parser import parse
from src.codegen import generate_program, CodeGenerationError
from src.semantic import check_program


def compile_file(input_path):
    """
    Compila diretamente um ficheiro Pascal para código EWVM.

    Esta função constitui uma interface simplificada para utilização por
    outros módulos ou pelos testes automáticos. Ao contrário de ``main``,
    não processa argumentos da linha de comandos nem apresenta modos de
    diagnóstico.

    Args:
        input_path: Caminho para o ficheiro Pascal de entrada.

    Returns:
        Uma string com o código EWVM gerado.

    Raises:
        OSError: Se ocorrer um erro ao ler o ficheiro.
        SyntaxError: Se o programa contiver um erro lexical ou sintático.
        CodeGenerationError: Se a compilação não puder ser concluída,
            nomeadamente devido a erros semânticos ou de geração de código.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)
    return generate_program(ast)


def main():
    """
    Executa o compilador através da interface de linha de comandos.

    O ficheiro Pascal é recebido como argumento obrigatório. Por omissão,
    o programa gera código EWVM e apresenta-o no terminal, podendo este ser
    guardado num ficheiro através da opção ``-o``.

    Os modos ``--tokens``, ``--ast`` e ``--symbols`` permitem inspecionar
    fases intermédias da compilação e terminam sem gerar código EWVM.
    """
    arg_parser = argparse.ArgumentParser(
        description="Compilador Pascal para EWVM"
    )

    arg_parser.add_argument(
        "input_file",
        help="Ficheiro Pascal de entrada"
    )

    # Apenas um modo de diagnóstico pode ser utilizado em cada execução.
    diagnostics = arg_parser.add_mutually_exclusive_group()

    diagnostics.add_argument(
        "--tokens",
        action="store_true",
        help="Mostrar tokens e terminar"
    )
    diagnostics.add_argument(
        "--ast",
        action="store_true",
        help="Mostrar a AST e terminar"
    )
    diagnostics.add_argument(
        "--symbols",
        action="store_true",
        help="Mostrar a tabela de símbolos e terminar"
    )

    arg_parser.add_argument(
        "-o",
        "--output",
        help="Ficheiro onde guardar o código EWVM gerado"
    )

    args = arg_parser.parse_args()

    try:
        with open(args.input_file, "r", encoding="utf-8") as source_file:
            source = source_file.read()

        # Modo de diagnóstico lexical: não executa as fases seguintes.
        if args.tokens:
            for token in tokenize(source):
                print(token)
            return

        ast = parse(source)

        # Modo de diagnóstico sintático: apresenta a AST construída.
        if args.ast:
            pprint(ast)
            return

        # Modo de diagnóstico semântico: apresenta a tabela de símbolos.
        if args.symbols:
            symbols, errors = check_program(ast)
            pprint(symbols.diagnostic_view())

            if errors:
                raise CodeGenerationError(
                    "Erros semânticos:\n"
                    + "\n".join(f"- {error}" for error in errors)
                )
            return

        # Caminho normal de compilação.
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