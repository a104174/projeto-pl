"""
Geração de código EWVM para o subconjunto de Pascal suportado.

O módulo recebe uma AST semanticamente válida, constrói o layout de memória e
traduz declarações, statements, expressões, arrays, strings e funções para
instruções EWVM. ``generate_program`` constitui a interface pública da fase.
"""

import sys

try:
    from .parser import parse
    from .semantic import check_program, infer_expression_type
except ImportError:
    from parser import parse
    from semantic import check_program, infer_expression_type


# =============================================================================
# Erros e estado do gerador
# =============================================================================

class CodeGenerationError(Exception):
    """
    Erro produzido durante a validação ou geração de código EWVM.
    """
    pass


class CodeGenerator:
    """
    Gerador de código EWVM baseado na AST e na tabela de símbolos.

    A instância mantém o layout global, a sequência de instruções, o contador de
    labels e o contexto da função atualmente gerada.
    """
    def __init__(self, symbols):
        """
        Inicializa o estado necessário à geração de um programa.
        """
        self.symbols = symbols
        self.layout = self.build_memory_layout(symbols)
        self.instructions = []
        self.label_counter = 0
        self.current_function = None


    # =============================================================================
    # Layout de memória e operações auxiliares
    # =============================================================================

    def build_memory_layout(self, symbols):
        """
        Atribui uma posição global a cada símbolo do programa.

        Nos arrays, essa posição guarda o endereço base do bloco alocado no heap.
        """
        layout = {}
        # Cada variável global ocupa uma posição. No caso de arrays, essa
        # posição contém o endereço do bloco alocado por ALLOCN.
        for offset, (name, info) in enumerate(symbols.items()):
            layout[name] = dict(info, offset=offset)
        return layout

    def emit(self, instruction):
        """
        Acrescenta uma instrução à sequência de código gerado.
        """
        self.instructions.append(instruction)

    def new_label(self, prefix="L"):
        """
        Produz uma label alfanumérica única com o prefixo indicado.
        """
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def escape_string(self, value):
        """
        Escapa caracteres especiais antes de emitir um literal EWVM.
        """
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def context(self):
        """
        Devolve o contexto semântico da função atualmente gerada.
        """
        if self.current_function is None:
            return None
        return {"name": self.current_function[0], "function": self.current_function[1]}

    def expression_type(self, expression):
        """
        Obtém o tipo semântico de uma expressão.

        Qualquer erro nesta fase é convertido em ``CodeGenerationError``.
        """
        errors = []
        result = infer_expression_type(expression, self.symbols, errors, self.context())
        if errors:
            raise CodeGenerationError("; ".join(errors))
        return result

    def resolve_storage(self, name):
        """
        Determina a região e a posição de armazenamento de um identificador.

        A resolução privilegia parâmetros e variáveis locais da função atual e,
        posteriormente, as variáveis globais.
        """
        if self.current_function:
            function = self.current_function[1]
            if name in function["scope"]:
                return "L", function["scope"][name]
            if name == self.current_function[0]:
                return "L", {
                    "type": function["return_type"],
                    "index": function["return_index"],
                    "kind": "return",
                }
        if name in self.layout:
            return "G", self.layout[name]
        raise CodeGenerationError(f"Símbolo sem layout: {name}")

    def emit_default_value(self, value_type):
        """
        Emite o valor inicial correspondente a um tipo escalar.
        """
        self.emit('PUSHS ""' if value_type == "string" else "PUSHI 0")

    def emit_global_initialization(self):
        """
        Reserva e inicializa uma posição para cada símbolo global.
        """
        for info in self.layout.values():
            self.emit_default_value(info["type"])


    # =============================================================================
    # Arrays e acessos indexados
    # =============================================================================

    def emit_array_allocation(self):
        """
        Aloca no heap os arrays globais e guarda os respetivos endereços base.
        """
        for info in self.layout.values():
            if info["kind"] == "array":
                self.emit(f"PUSHI {info['size']}")
                self.emit("ALLOCN")
                self.emit(f"STOREG {info['offset']}")

    def generate_array_address(self, name, index_expression):
        """
        Coloca na stack o endereço base e o offset normalizado de um array.
        """
        region, info = self.resolve_storage(name)
        self.emit(f"PUSH{region} {info['offset'] if region == 'G' else info['index']}")
        self.generate_expression(index_expression)
        if info["start"] != 0:
            self.emit(f"PUSHI {info['start']}")
            self.emit("SUB")

    def generate_string_access(self, name, index_expression):
        """
        Gera a leitura de um carácter de string.

        A indexação Pascal é tratada como base 1, enquanto ``CHARAT`` utiliza base 0.
        """
        region, info = self.resolve_storage(name)
        index = info["offset"] if region == "G" else info["index"]
        self.emit(f"PUSH{region} {index}")
        self.generate_expression(index_expression)
        self.emit("PUSHI 1")
        self.emit("SUB")
        self.emit("CHARAT")

    def generate_indexed_access(self, name, index_expression):
        """
        Seleciona a geração adequada para arrays ou strings indexadas.
        """
        _, info = self.resolve_storage(name)
        if info["kind"] == "array":
            self.generate_array_address(name, index_expression)
            self.emit("LOADN")
        elif info["type"] == "string":
            self.generate_string_access(name, index_expression)
        else:
            raise CodeGenerationError(f"Símbolo '{name}' não pode ser indexado")


    # =============================================================================
    # Programa principal e funções
    # =============================================================================

    def generate_program(self, ast):
        """
        Gera o código do programa principal e das funções declaradas.
        """
        if ast[0] != "program":
            raise CodeGenerationError("AST inválida: raiz não é program")
        _, program_name, declarations, function_declarations, block = ast
        self.emit_global_initialization()
        self.emit("START")
        self.emit_array_allocation()
        self.generate_statement(block)
        self.emit("STOP")

        # As funções são emitidas depois de STOP para não serem executadas
        # sequencialmente pelo programa principal.
        for declaration in function_declarations:
            self.generate_function(declaration)
        return "\n".join(self.instructions) + "\n"

    def generate_function(self, declaration):
        """
        Gera a label, o frame local, o corpo e o retorno de uma função.
        """
        _, name, parameters, return_node, local_declarations, body = declaration
        function = self.symbols.functions[name]
        self.current_function = (name, function)
        self.emit(f"{function['label']}:")
        for info in function["locals"].values():
            self.emit_default_value(info["type"])
        self.generate_statement(body)
        self.emit("RETURN")
        self.current_function = None


    # =============================================================================
    # Geração de statements
    # =============================================================================

    def generate_statement(self, statement):
        """
        Traduz recursivamente um statement da AST para EWVM.
        """
        kind = statement[0]
        if kind == "block":
            for stmt in statement[1]:
                self.generate_statement(stmt)
        elif kind == "assign":
            _, target, expression = statement
            if target[0] == "array_access":
                self.generate_array_address(target[1], target[2])
                self.generate_expression(expression)
                self.emit("STOREN")
            else:
                self.generate_expression(expression)
                self.store_variable(target)
        elif kind == "readln":
            for variable in statement[1]:
                if variable[0] == "array_access":
                    self.generate_array_address(variable[1], variable[2])
                var_type = self.variable_type(variable)
                self.emit("READ")
                if var_type == "integer":
                    self.emit("ATOI")
                elif var_type != "string":
                    raise CodeGenerationError(f"readln não suportado para tipo {var_type}")
                if variable[0] == "array_access":
                    self.emit("STOREN")
                else:
                    self.store_variable(variable)
        elif kind == "writeln":
            for expression in statement[1]:
                expr_type = self.expression_type(expression)
                self.generate_expression(expression)
                self.emit("WRITES" if expr_type == "string" else "WRITEI")
            self.emit("WRITELN")
        elif kind == "if":
            _, condition, then_stmt, else_stmt = statement
            else_label, end_label = self.new_label("ELSE"), self.new_label("ENDIF")
            self.generate_expression(condition)
            self.emit(f"JZ {else_label}")
            self.generate_statement(then_stmt)
            self.emit(f"JUMP {end_label}")
            self.emit(f"{else_label}:")
            if else_stmt is not None:
                self.generate_statement(else_stmt)
            self.emit(f"{end_label}:")
        elif kind == "while":
            _, condition, body = statement
            start_label, end_label = self.new_label("WHILE"), self.new_label("ENDWHILE")
            self.emit(f"{start_label}:")
            self.generate_expression(condition)
            self.emit(f"JZ {end_label}")
            self.generate_statement(body)
            self.emit(f"JUMP {start_label}")
            self.emit(f"{end_label}:")
        elif kind == "for":
            _, name, start_expr, direction, end_expr, body = statement
            region, info = self.resolve_storage(name)
            index = info["offset"] if region == "G" else info["index"]
            start_label, end_label = self.new_label("FOR"), self.new_label("ENDFOR")
            self.generate_expression(start_expr)
            self.emit(f"STORE{region} {index}")
            self.emit(f"{start_label}:")
            self.emit(f"PUSH{region} {index}")
            self.generate_expression(end_expr)
            self.emit("INFEQ" if direction == "to" else "SUPEQ")
            self.emit(f"JZ {end_label}")
            self.generate_statement(body)
            self.emit(f"PUSH{region} {index}")
            self.emit("PUSHI 1")
            self.emit("ADD" if direction == "to" else "SUB")
            self.emit(f"STORE{region} {index}")
            self.emit(f"JUMP {start_label}")
            self.emit(f"{end_label}:")
        else:
            raise CodeGenerationError(f"Statement não suportado: {statement}")


    # =============================================================================
    # Variáveis, armazenamento e chamadas
    # =============================================================================

    def variable_type(self, variable):
        """
        Obtém o tipo de uma variável a partir do respetivo armazenamento.
        """
        _, info = self.resolve_storage(variable[1])
        return info["type"]

    def store_variable(self, variable):
        """
        Emite a instrução de armazenamento global ou local apropriada.
        """
        _, name = variable
        region, info = self.resolve_storage(name)
        index = info["offset"] if region == "G" else info["index"]
        self.emit(f"STORE{region} {index}")

    def generate_call(self, name, arguments):
        """
        Gera uma chamada à função built-in ``length`` ou a uma função declarada.
        """
        if name == "length":
            self.generate_expression(arguments[0])
            self.emit("STRLEN")
            return
        function = self.symbols.functions[name]
        # O caller reserva primeiro o slot de retorno e coloca depois os
        # argumentos na stack. POP remove apenas os argumentos após CALL.
        self.emit_default_value(function["return_type"])
        for argument in arguments:
            self.generate_expression(argument)
        self.emit(f"PUSHA {function['label']}")
        self.emit("CALL")
        self.emit(f"POP {len(arguments)}")


    # =============================================================================
    # Geração de expressões
    # =============================================================================

    def generate_expression(self, expression):
        """
        Traduz uma expressão da AST, deixando o resultado na stack.
        """
        kind = expression[0]
        if kind == "int": self.emit(f"PUSHI {expression[1]}")
        elif kind == "string": self.emit(f'PUSHS "{self.escape_string(expression[1])}"')
        elif kind == "bool": self.emit("PUSHI 1" if expression[1] else "PUSHI 0")
        elif kind == "var":
            region, info = self.resolve_storage(expression[1])
            index = info["offset"] if region == "G" else info["index"]
            self.emit(f"PUSH{region} {index}")
        elif kind == "array_access":
            self.generate_indexed_access(expression[1], expression[2])
        elif kind == "call":
            self.generate_call(expression[1], expression[2])
        elif kind == "unop":
            if expression[1] == "-":
                self.emit("PUSHI 0")
                self.generate_expression(expression[2])
                self.emit("SUB")
            else:
                self.generate_expression(expression[2])
                self.emit("NOT")
        elif kind == "binop":
            _, operator, left, right = expression
            left_type = self.expression_type(left)
            right_type = self.expression_type(right)
            self.generate_expression(left)
            # CHARAT produz um carácter interno; CHRCODE converte um literal
            # string de comprimento um para uma representação comparável.
            if operator in {"=", "<>"} and left_type == "string" and right_type == "char":
                self.emit("CHRCODE")
            self.generate_expression(right)
            if operator in {"=", "<>"} and right_type == "string" and left_type == "char":
                self.emit("CHRCODE")
            instructions = {
                "+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "div": "DIV",
                "mod": "MOD", "=": "EQUAL", "<": "INF", "<=": "INFEQ",
                ">": "SUP", ">=": "SUPEQ", "and": "AND", "or": "OR",
            }
            if operator == "<>":
                self.emit("EQUAL")
                self.emit("NOT")
            else:
                self.emit(instructions[operator])
        else:
            raise CodeGenerationError(f"Expressão não suportada: {expression}")


# =============================================================================
# Interface pública
# =============================================================================

def generate_program(ast):
    """
    Valida semanticamente a AST e devolve o código EWVM gerado.

    Raises:
        CodeGenerationError: Se existirem erros semânticos ou de geração.
    """
    symbols, errors = check_program(ast)
    if errors:
        raise CodeGenerationError("Erros semânticos:\n" + "\n".join(f"- {error}" for error in errors))
    return CodeGenerator(symbols).generate_program(ast)


# =============================================================================
# Execução independente
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/codegen.py <ficheiro.pas>")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as source_file:
        ast = parse(source_file.read())
    try:
        print(generate_program(ast), end="")
    except CodeGenerationError as error:
        print(error, file=sys.stderr)
        sys.exit(1)