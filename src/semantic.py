"""
Análise semântica do subconjunto de Pascal suportado.

O módulo constrói a tabela de símbolos, organiza os âmbitos globais e locais
e percorre a AST para validar declarações, tipos, chamadas, arrays e retornos
de funções. ``check_program`` devolve a tabela de símbolos e os erros detetados.
"""

import sys
from pprint import pprint

try:
    from .parser import parse
except ImportError:
    from parser import parse


# =============================================================================
# Tipos e tabela de símbolos
# =============================================================================

def type_name(type_node):
    """
    Obtém o nome textual de um nó de tipo simples da AST.
    """
    if type_node[0] == "type":
        return type_node[1]
    raise ValueError(f"Tipo inválido: {type_node}")


class SymbolTable(dict):
    """
    Tabela de símbolos globais, complementada por um catálogo de funções.
    """

    def __init__(self):
        super().__init__()
        self.functions = {}

    def diagnostic_view(self):
        """
        Devolve uma representação apropriada para diagnóstico e depuração.
        """
        return {"globals": dict(self), "functions": self.functions}


# =============================================================================
# Declarações, funções e construção de âmbitos
# =============================================================================

def declare_variables(declarations, target, errors, scope_name, arrays_allowed=True):
    """
    Regista declarações de variáveis num determinado âmbito.

    Os erros encontrados são acumulados em ``errors`` para permitir apresentar
    vários diagnósticos numa única análise.
    """
    for declaration in declarations:
        if declaration[0] != "var_decl":
            errors.append(f"Declaração desconhecida: {declaration}")
            continue
        _, names, declared_type = declaration
        for name in names:
            if name in target:
                errors.append(f"Variável '{name}' declarada mais do que uma vez em {scope_name}")
                continue
            if declared_type[0] == "array":
                _, start, end, element_node = declared_type
                element_type = type_name(element_node)
                if not arrays_allowed:
                    errors.append(f"Array local '{name}' não é suportado")
                if start > end:
                    errors.append(f"Array '{name}' tem limites inválidos: {start}..{end}")
                if element_type != "integer":
                    errors.append(
                        f"Array '{name}' tem tipo de elemento não suportado: "
                        f"{element_type}; apenas integer é suportado"
                    )
                target[name] = {
                    "kind": "array", "type": element_type,
                    "start": start, "end": end, "size": end - start + 1,
                }
            else:
                target[name] = {"kind": "scalar", "type": type_name(declared_type)}


def build_symbol_table(declarations):
    """
    Constrói a tabela de símbolos das declarações globais.
    """
    symbols = SymbolTable()
    errors = []
    declare_variables(declarations, symbols, errors, "âmbito global")
    return symbols, errors


def register_functions(function_declarations, symbols, errors):
    """
    Regista as assinaturas e os metadados das funções.

    Nesta fase são validados nomes, parâmetros e tipos de retorno, mas os corpos
    das funções são analisados posteriormente.
    """
    for declaration in function_declarations:
        _, name, parameters, return_node, local_declarations, body = declaration
        if name == "length":
            errors.append("A função built-in 'length' não pode ser redefinida")
            continue
        if name in symbols.functions:
            errors.append(f"Função '{name}' declarada mais do que uma vez")
            continue
        if name in symbols:
            errors.append(f"Função '{name}' entra em conflito com uma variável global")
        params = []
        seen = set()
        for _, param_name, param_node in parameters:
            if param_name in seen:
                errors.append(f"Parâmetro '{param_name}' duplicado na função '{name}'")
                continue
            seen.add(param_name)
            if param_name == name:
                errors.append(f"Parâmetro '{param_name}' tem o mesmo nome da função '{name}'")
            if param_name == "length":
                errors.append(
                    f"Parâmetro 'length' da função '{name}' entra em conflito com a função built-in"
                )
            params.append({"name": param_name, "type": type_name(param_node)})
        symbols.functions[name] = {
            "kind": "function",
            "return_type": type_name(return_node),
            "parameters": params,
            "locals": {},
            "body": body,
            "local_declarations": local_declarations,
            "has_return_assignment": False,
            # As labels EWVM só usam caracteres alfanuméricos. O contador
            # também evita colisões entre nomes como a_b e ab.
            "label": f"FUNC{len(symbols.functions) + 1}",
        }


def prepare_function_scopes(symbols, errors):
    """
    Constrói os âmbitos locais e o layout lógico dos frames das funções.

    Os parâmetros recebem índices negativos, as variáveis locais índices
    não negativos e o resultado da função ocupa o slot anterior aos argumentos.
    """
    for name, function in symbols.functions.items():
        scope = {}
        # Os argumentos encontram-se abaixo do frame pointer e são, por isso,
        # representados por índices locais negativos.
        for index, param in enumerate(function["parameters"]):
            scope[param["name"]] = {
                "kind": "parameter", "type": param["type"], "index": -(index + 1)
            }
        # O subconjunto suportado permite variáveis locais escalares, mas não
        # arrays locais, cuja alocação exigiria tratamento próprio no frame.
        local_symbols = {}
        declare_variables(
            function["local_declarations"], local_symbols, errors,
            f"função '{name}'", arrays_allowed=False,
        )
        for local_name, info in local_symbols.items():
            if local_name == name:
                errors.append(f"Variável local '{local_name}' tem o mesmo nome da função '{name}'")
                continue
            if local_name == "length":
                errors.append(
                    f"Variável local 'length' da função '{name}' entra em conflito com a função built-in"
                )
                continue
            if local_name in scope:
                errors.append(
                    f"Variável local '{local_name}' entra em conflito com um parâmetro "
                    f"da função '{name}'"
                )
                continue
            entry = dict(info)
            entry["kind"] = "local"
            entry["index"] = len(function["locals"])
            function["locals"][local_name] = entry
            scope[local_name] = entry
        function["scope"] = scope

        # O caller reserva o slot de retorno imediatamente antes dos argumentos.
        function["return_index"] = -(len(function["parameters"]) + 1)


# =============================================================================
# Análise do programa e resolução de nomes
# =============================================================================

def check_program(ast):
    """
    Executa a análise semântica completa de uma AST de programa.

    Returns:
        Par ``(symbols, errors)`` com a tabela de símbolos e a lista de erros.
    """
    if not ast or ast[0] != "program":
        return SymbolTable(), ["AST inválida: raiz não é um programa"]
    _, program_name, declarations, function_declarations, block = ast
    # A análise é organizada em fases: globais, assinaturas de funções,
    # âmbitos locais e, por fim, corpos executáveis.
    symbols, errors = build_symbol_table(declarations)
    if "length" in symbols:
        errors.append("A variável global 'length' entra em conflito com a função built-in")
    register_functions(function_declarations, symbols, errors)
    prepare_function_scopes(symbols, errors)
    for name, function in symbols.functions.items():
        context = {"name": name, "function": function}
        check_statement(function["body"], symbols, errors, context)
        if not function["has_return_assignment"]:
            errors.append(f"Função '{name}' não atribui um valor ao seu resultado")
    check_statement(block, symbols, errors, None)
    return symbols, errors


def resolve_variable(name, symbols, context):
    """
    Resolve um identificador no âmbito local da função e, em seguida, no global.
    """
    if context and name in context["function"]["scope"]:
        return context["function"]["scope"][name]
    return symbols.get(name)


# =============================================================================
# Validação de statements
# =============================================================================

def check_statement(statement, symbols, errors, context=None):
    """
    Valida recursivamente um statement da AST.
    """
    kind = statement[0]
    if kind == "block":
        for stmt in statement[1]:
            check_statement(stmt, symbols, errors, context)
    elif kind == "assign":
        _, target, expression = statement
        if target[0] == "var" and context and target[1] == context["name"]:
            target_type = context["function"]["return_type"]
            context["function"]["has_return_assignment"] = True
        elif target[0] == "var" and target[1] in symbols.functions:
            errors.append(f"Resultado da função '{target[1]}' só pode ser atribuído dentro da própria função")
            target_type = None
        else:
            target_type = check_variable(target, symbols, errors, context, as_target=True)
        expression_type = infer_expression_type(expression, symbols, errors, context)
        if target_type and expression_type and target_type != expression_type:
            errors.append(
                f"Atribuição inválida: não é possível atribuir {expression_type} a {target_type}"
            )
    elif kind == "readln":
        for variable in statement[1]:
            var_type = check_variable(
                variable, symbols, errors, context, as_target=True, for_read=True
            )
            if var_type == "boolean":
                errors.append("readln de boolean não é suportado nesta versão")
    elif kind == "writeln":
        for expression in statement[1]:
            infer_expression_type(expression, symbols, errors, context)
    elif kind == "if":
        _, condition, then_stmt, else_stmt = statement
        if infer_expression_type(condition, symbols, errors, context) not in (None, "boolean"):
            errors.append("Condição do if tem de ser boolean")
        check_statement(then_stmt, symbols, errors, context)
        if else_stmt is not None:
            check_statement(else_stmt, symbols, errors, context)
    elif kind == "while":
        _, condition, body = statement
        if infer_expression_type(condition, symbols, errors, context) not in (None, "boolean"):
            errors.append("Condição do while tem de ser boolean")
        check_statement(body, symbols, errors, context)
    elif kind == "for":
        _, var_name, start_expr, direction, end_expr, body = statement
        symbol = resolve_variable(var_name, symbols, context)
        if symbol is None:
            errors.append(f"Variável de controlo '{var_name}' não declarada")
        else:
            if symbol["kind"] == "array":
                errors.append(f"Variável de controlo '{var_name}' não pode ser um array")
            if symbol["type"] != "integer":
                errors.append(f"Variável de controlo '{var_name}' tem de ser integer")
        if infer_expression_type(start_expr, symbols, errors, context) not in (None, "integer"):
            errors.append("Valor inicial do for tem de ser integer")
        if infer_expression_type(end_expr, symbols, errors, context) not in (None, "integer"):
            errors.append("Valor final do for tem de ser integer")
        check_statement(body, symbols, errors, context)
    else:
        errors.append(f"Statement desconhecido: {statement}")


# =============================================================================
# Variáveis e acessos indexados
# =============================================================================

def check_variable(variable, symbols, errors, context=None, as_target=False, for_read=False):
    """
    Valida uma variável simples ou um acesso indexado e devolve o seu tipo.

    O parâmetro ``as_target`` distingue utilizações como valor de utilizações como
    destino de atribuição ou leitura.
    """
    kind = variable[0]
    if kind == "var":
        name = variable[1]
        symbol = resolve_variable(name, symbols, context)
        if symbol is None:
            if name in symbols.functions:
                errors.append(f"Função '{name}' usada sem chamada")
            else:
                errors.append(f"Variável '{name}' usada sem declaração")
            return None
        if symbol["kind"] == "array":
            errors.append(f"Array '{name}' usado sem índice")
        return symbol["type"]
    if kind == "array_access":
        _, name, index_expr = variable
        symbol = resolve_variable(name, symbols, context)
        if symbol is None:
            errors.append(f"Variável indexada '{name}' usada sem declaração")
            return None
        index_type = infer_expression_type(index_expr, symbols, errors, context)
        if index_type and index_type != "integer":
            errors.append(f"Índice de '{name}' tem de ser integer")
        if symbol["kind"] != "array":
            # A indexação de strings produz o tipo interno ``char`` e é
            # suportada apenas em contexto de leitura.
            if symbol["type"] == "string":
                if as_target:
                    operation = "readln" if for_read else "atribuição"
                    errors.append(
                        f"Indexação de string '{name}' não pode ser usada como destino de {operation}"
                    )
                return "char"
            errors.append(f"Variável '{name}' não é um array")
            return symbol["type"]
        if index_expr[0] == "int" and not symbol["start"] <= index_expr[1] <= symbol["end"]:
            errors.append(
                f"Índice {index_expr[1]} fora dos limites do array '{name}' "
                f"[{symbol['start']}..{symbol['end']}]"
            )
        return symbol["type"]
    errors.append(f"Variável inválida: {variable}")
    return None


# =============================================================================
# Chamadas e inferência de tipos
# =============================================================================

def infer_call_type(expression, symbols, errors, context):
    """
    Valida uma chamada de função e devolve o respetivo tipo de retorno.
    """
    _, name, arguments = expression
    if name == "length":
        argument_types = [infer_expression_type(arg, symbols, errors, context) for arg in arguments]
        if len(arguments) != 1:
            errors.append("A função length recebe exatamente um argumento")
        elif argument_types[0] and argument_types[0] != "string":
            errors.append("O argumento de length tem de ser string")
        return "integer"
    function = symbols.functions.get(name)
    if function is None:
        if resolve_variable(name, symbols, context) is not None:
            errors.append(f"Variável '{name}' usada como função")
        else:
            errors.append(f"Função '{name}' não declarada")
        for argument in arguments:
            infer_expression_type(argument, symbols, errors, context)
        return None
    actual_types = [infer_expression_type(arg, symbols, errors, context) for arg in arguments]
    expected = function["parameters"]
    if len(arguments) != len(expected):
        errors.append(
            f"Função '{name}' espera {len(expected)} argumento(s), recebeu {len(arguments)}"
        )
    for position, (actual, parameter) in enumerate(zip(actual_types, expected), 1):
        if actual and actual != parameter["type"]:
            errors.append(
                f"Argumento {position} de '{name}' tem tipo {actual}; "
                f"esperado {parameter['type']}"
            )
    return function["return_type"]


def infer_expression_type(expression, symbols, errors, context=None):
    """
    Infere o tipo de uma expressão e valida a compatibilidade dos operadores.

    O tipo interno ``char`` é usado apenas para representar caracteres obtidos
    através da indexação de strings; não é um tipo declarável em Pascal.
    """
    kind = expression[0]
    if kind == "int": return "integer"
    if kind == "string": return "string"
    if kind == "bool": return "boolean"
    if kind in ("var", "array_access"):
        return check_variable(expression, symbols, errors, context)
    if kind == "call":
        return infer_call_type(expression, symbols, errors, context)
    if kind == "unop":
        _, operator, operand = expression
        operand_type = infer_expression_type(operand, symbols, errors, context)
        expected = "integer" if operator == "-" else "boolean"
        if operand_type and operand_type != expected:
            errors.append(f"Operador '{operator}' só pode ser aplicado a {expected}")
            return None
        return expected
    if kind == "binop":
        _, operator, left, right = expression
        left_type = infer_expression_type(left, symbols, errors, context)
        right_type = infer_expression_type(right, symbols, errors, context)
        if not left_type or not right_type:
            return None
        if operator in {"+", "-", "*", "/", "div", "mod"}:
            if left_type != "integer" or right_type != "integer":
                errors.append(f"Operador '{operator}' só pode ser aplicado a integer")
                return None
            return "integer"
        if operator in {"=", "<>"}:
            # Um carácter obtido por indexação pode ser comparado com um
            # literal string de comprimento um.
            char_comparison = (
                left_type == right_type == "char"
                or (
                    left_type == "char" and right_type == "string"
                    and right[0] == "string" and len(right[1]) == 1
                )
                or (
                    right_type == "char" and left_type == "string"
                    and left[0] == "string" and len(left[1]) == 1
                )
            )
            if left_type != right_type and not char_comparison:
                errors.append(f"Operador '{operator}' usado com tipos incompatíveis: {left_type} e {right_type}")
                return None
            return "boolean"
        if operator in {"<", "<=", ">", ">="}:
            if left_type != "integer" or right_type != "integer":
                errors.append(f"Operador '{operator}' só pode comparar integer")
                return None
            return "boolean"
        if operator in {"and", "or"}:
            if left_type != "boolean" or right_type != "boolean":
                errors.append(f"Operador '{operator}' só pode ser aplicado a boolean")
                return None
            return "boolean"
        errors.append(f"Operador binário desconhecido: {operator}")
        return None
    errors.append(f"Expressão desconhecida: {expression}")
    return None


# =============================================================================
# Execução independente
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/semantic.py <ficheiro.pas>")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as source_file:
        ast = parse(source_file.read())
    symbols, semantic_errors = check_program(ast)
    pprint(symbols.diagnostic_view())
    if semantic_errors:
        for error in semantic_errors:
            print(f"- {error}")
        sys.exit(1)