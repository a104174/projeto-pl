import sys
from pprint import pprint

try:
    from .parser import parse
except ImportError:
    from parser import parse


def type_name(type_node):
    """
    Converte nós de tipo da AST para uma string simples.

    Exemplos:
    ("type", "integer") -> "integer"
    ("type", "boolean") -> "boolean"
    """
    if type_node[0] == "type":
        return type_node[1]

    raise ValueError(f"Tipo inválido: {type_node}")


def build_symbol_table(declarations):
    """
    Constrói a tabela de símbolos a partir das declarações.

    A tabela de símbolos guarda informação sobre cada variável:
    - nome
    - tipo
    - se é escalar ou array
    - limites, no caso de arrays
    """
    symbols = {}
    errors = []

    for declaration in declarations:
        if declaration[0] != "var_decl":
            errors.append(f"Declaração desconhecida: {declaration}")
            continue

        _, names, declared_type = declaration

        for name in names:
            if name in symbols:
                errors.append(f"Variável '{name}' declarada mais do que uma vez")
                continue

            if declared_type[0] == "array":
                _, start, end, element_type_node = declared_type
                element_type = type_name(element_type_node)

                if start > end:
                    errors.append(
                        f"Array '{name}' tem limites inválidos: {start}..{end}"
                    )

                if element_type != "integer":
                    errors.append(
                        f"Array '{name}' tem tipo de elemento não suportado: "
                        f"{element_type}; apenas integer é suportado"
                    )

                symbols[name] = {
                    "kind": "array",
                    "type": element_type,
                    "start": start,
                    "end": end,
                    "size": end - start + 1,
                }

            else:
                symbols[name] = {
                    "kind": "scalar",
                    "type": type_name(declared_type),
                }

    return symbols, errors


def check_program(ast):
    """
    Função principal da análise semântica.

    Recebe a AST produzida pelo parser e devolve:
    - tabela de símbolos
    - lista de erros semânticos
    """
    if ast[0] != "program":
        return {}, ["AST inválida: raiz não é um programa"]

    _, program_name, declarations, block = ast

    symbols, errors = build_symbol_table(declarations)

    check_statement(block, symbols, errors)

    return symbols, errors


def check_statement(statement, symbols, errors):
    """
    Valida semanticamente um statement.
    """
    kind = statement[0]

    if kind == "block":
        _, statements = statement
        for stmt in statements:
            check_statement(stmt, symbols, errors)

    elif kind == "assign":
        _, target, expression = statement

        target_type = check_variable(target, symbols, errors, as_target=True)
        expression_type = infer_expression_type(expression, symbols, errors)

        if target_type is not None and expression_type is not None:
            if target_type != expression_type:
                errors.append(
                    f"Atribuição inválida: não é possível atribuir "
                    f"{expression_type} a {target_type}"
                )

    elif kind == "readln":
        _, variables = statement

        for variable in variables:
            var_type = check_variable(variable, symbols, errors, as_target=True)

            if var_type == "boolean":
                errors.append(
                    "readln de boolean não é suportado nesta versão"
                )

    elif kind == "writeln":
        _, expressions = statement

        for expression in expressions:
            infer_expression_type(expression, symbols, errors)

    elif kind == "if":
        _, condition, then_stmt, else_stmt = statement

        condition_type = infer_expression_type(condition, symbols, errors)

        if condition_type is not None and condition_type != "boolean":
            errors.append("Condição do if tem de ser boolean")

        check_statement(then_stmt, symbols, errors)

        if else_stmt is not None:
            check_statement(else_stmt, symbols, errors)

    elif kind == "while":
        _, condition, body = statement

        condition_type = infer_expression_type(condition, symbols, errors)

        if condition_type is not None and condition_type != "boolean":
            errors.append("Condição do while tem de ser boolean")

        check_statement(body, symbols, errors)

    elif kind == "for":
        _, var_name, start_expr, direction, end_expr, body = statement

        if var_name not in symbols:
            errors.append(f"Variável de controlo '{var_name}' não declarada")
        else:
            symbol = symbols[var_name]

            if symbol["kind"] != "scalar":
                errors.append(
                    f"Variável de controlo '{var_name}' não pode ser um array"
                )

            if symbol["type"] != "integer":
                errors.append(
                    f"Variável de controlo '{var_name}' tem de ser integer"
                )

        start_type = infer_expression_type(start_expr, symbols, errors)
        end_type = infer_expression_type(end_expr, symbols, errors)

        if start_type is not None and start_type != "integer":
            errors.append("Valor inicial do for tem de ser integer")

        if end_type is not None and end_type != "integer":
            errors.append("Valor final do for tem de ser integer")

        check_statement(body, symbols, errors)

    else:
        errors.append(f"Statement desconhecido: {statement}")


def check_variable(variable, symbols, errors, as_target=False):
    """
    Verifica se uma variável ou acesso a array é válido.

    Retorna o tipo da variável.
    """
    kind = variable[0]

    if kind == "var":
        _, name = variable

        if name not in symbols:
            errors.append(f"Variável '{name}' usada sem declaração")
            return None

        symbol = symbols[name]

        if symbol["kind"] == "array":
            errors.append(
                f"Array '{name}' usado sem índice"
            )
            return symbol["type"]

        return symbol["type"]

    if kind == "array_access":
        _, name, index_expr = variable

        if name not in symbols:
            errors.append(f"Array '{name}' usado sem declaração")
            return None

        symbol = symbols[name]

        if symbol["kind"] != "array":
            errors.append(f"Variável '{name}' não é um array")
            return symbol["type"]

        index_type = infer_expression_type(index_expr, symbols, errors)

        if index_type is not None and index_type != "integer":
            errors.append(f"Índice do array '{name}' tem de ser integer")

        # Verificação extra: se o índice for literal, podemos validar limites
        if index_expr[0] == "int":
            index_value = index_expr[1]

            if index_value < symbol["start"] or index_value > symbol["end"]:
                errors.append(
                    f"Índice {index_value} fora dos limites do array '{name}' "
                    f"[{symbol['start']}..{symbol['end']}]"
                )

        return symbol["type"]

    errors.append(f"Variável inválida: {variable}")
    return None


def infer_expression_type(expression, symbols, errors):
    """
    Infere o tipo de uma expressão.

    Retorna:
    - "integer"
    - "boolean"
    - "string"
    - None, caso haja erro
    """
    kind = expression[0]

    if kind == "int":
        return "integer"

    if kind == "string":
        return "string"

    if kind == "bool":
        return "boolean"

    if kind in ("var", "array_access"):
        return check_variable(expression, symbols, errors)

    if kind == "unop":
        _, operator, operand = expression
        operand_type = infer_expression_type(operand, symbols, errors)

        if operand_type is None:
            return None

        if operator == "-":
            if operand_type != "integer":
                errors.append("Operador unário '-' só pode ser aplicado a integer")
                return None
            return "integer"

        if operator == "not":
            if operand_type != "boolean":
                errors.append("Operador 'not' só pode ser aplicado a boolean")
                return None
            return "boolean"

        errors.append(f"Operador unário desconhecido: {operator}")
        return None

    if kind == "binop":
        _, operator, left, right = expression

        left_type = infer_expression_type(left, symbols, errors)
        right_type = infer_expression_type(right, symbols, errors)

        if left_type is None or right_type is None:
            return None

        arithmetic_ops = {"+", "-", "*", "/", "div", "mod"}
        relational_ops = {"=", "<>", "<", "<=", ">", ">="}
        logical_ops = {"and", "or"}

        if operator in arithmetic_ops:
            if left_type != "integer" or right_type != "integer":
                errors.append(
                    f"Operador '{operator}' só pode ser aplicado a integer"
                )
                return None
            return "integer"

        if operator in relational_ops:
            if operator in {"=", "<>"}:
                if left_type != right_type:
                    errors.append(
                        f"Operador '{operator}' usado com tipos incompatíveis: "
                        f"{left_type} e {right_type}"
                    )
                    return None
                return "boolean"

            if left_type != "integer" or right_type != "integer":
                errors.append(
                    f"Operador '{operator}' só pode comparar integer"
                )
                return None

            return "boolean"

        if operator in logical_ops:
            if left_type != "boolean" or right_type != "boolean":
                errors.append(
                    f"Operador '{operator}' só pode ser aplicado a boolean"
                )
                return None
            return "boolean"

        errors.append(f"Operador binário desconhecido: {operator}")
        return None

    errors.append(f"Expressão desconhecida: {expression}")
    return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/semantic.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)
    symbols, errors = check_program(ast)

    print("Tabela de símbolos:")
    pprint(symbols)

    if errors:
        print("\nErros semânticos:")
        for error in errors:
            print(f"- {error}")
        sys.exit(1)

    print("\nSem erros semânticos.")
