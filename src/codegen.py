import sys

try:
    from .parser import parse
    from .semantic import check_program, infer_expression_type
except ImportError:
    from parser import parse
    from semantic import check_program, infer_expression_type


class CodeGenerationError(Exception):
    pass


class CodeGenerator:
    def __init__(self, symbols):
        self.symbols = symbols
        self.layout = self.build_memory_layout(symbols)
        self.instructions = []
        self.label_counter = 0

    def build_memory_layout(self, symbols):
        """
        Atribui um offset de memória global a cada variável.

        Exemplo:
        n   -> offset 0
        i   -> offset 1
        fat -> offset 2
        """
        layout = {}
        next_offset = 0

        for name, info in symbols.items():
            entry = dict(info)
            entry["offset"] = next_offset

            if info["kind"] == "array":
                next_offset += info["size"]
            else:
                next_offset += 1

            layout[name] = entry

        return layout

    def emit(self, instruction):
        self.instructions.append(instruction)

    def new_label(self, prefix="L"):
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def escape_string(self, value):
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def expression_type(self, expression):
        errors = []
        expr_type = infer_expression_type(expression, self.symbols, errors)

        if errors:
            raise CodeGenerationError("; ".join(errors))

        return expr_type

    def emit_global_initialization(self):
        """
        Reserva espaço para as variáveis globais antes do START.
        Na EWVM, variáveis globais são guardadas na stack global.
        """
        ordered_vars = sorted(
            self.layout.items(),
            key=lambda item: item[1]["offset"]
        )

        for name, info in ordered_vars:
            if info["kind"] == "array":
                if info["type"] in ("integer", "boolean"):
                    self.emit(f"PUSHN {info['size']}")
                else:
                    for _ in range(info["size"]):
                        self.emit('PUSHS ""')
            else:
                if info["type"] in ("integer", "boolean"):
                    self.emit("PUSHI 0")
                elif info["type"] == "string":
                    self.emit('PUSHS ""')
                else:
                    raise CodeGenerationError(
                        f"Tipo não suportado: {info['type']}"
                    )

    def generate_program(self, ast):
        if ast[0] != "program":
            raise CodeGenerationError("AST inválida: raiz não é program")

        _, program_name, declarations, block = ast

        self.emit_global_initialization()
        self.emit("START")
        self.generate_statement(block)
        self.emit("STOP")

        return "\n".join(self.instructions) + "\n"

    def generate_statement(self, statement):
        kind = statement[0]

        if kind == "block":
            _, statements = statement
            for stmt in statements:
                self.generate_statement(stmt)

        elif kind == "assign":
            _, target, expression = statement
            self.generate_expression(expression)
            self.store_variable(target)

        elif kind == "readln":
            _, variables = statement

            for variable in variables:
                var_type = self.variable_type(variable)

                self.emit("READ")

                if var_type == "integer":
                    self.emit("ATOI")
                elif var_type == "string":
                    pass
                else:
                    raise CodeGenerationError(
                        f"readln não suportado para tipo {var_type}"
                    )

                self.store_variable(variable)

        elif kind == "writeln":
            _, expressions = statement

            for expression in expressions:
                expr_type = self.expression_type(expression)

                self.generate_expression(expression)

                if expr_type == "integer":
                    self.emit("WRITEI")
                elif expr_type == "boolean":
                    self.emit("WRITEI")
                elif expr_type == "string":
                    self.emit("WRITES")
                else:
                    raise CodeGenerationError(
                        f"writeln não suportado para tipo {expr_type}"
                    )

            self.emit("WRITELN")

        elif kind == "if":
            _, condition, then_stmt, else_stmt = statement

            else_label = self.new_label("ELSE")
            end_label = self.new_label("ENDIF")

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

            start_label = self.new_label("WHILE")
            end_label = self.new_label("ENDWHILE")

            self.emit(f"{start_label}:")
            self.generate_expression(condition)
            self.emit(f"JZ {end_label}")

            self.generate_statement(body)
            self.emit(f"JUMP {start_label}")
            self.emit(f"{end_label}:")

        elif kind == "for":
            _, var_name, start_expr, direction, end_expr, body = statement

            if var_name not in self.layout:
                raise CodeGenerationError(
                    f"Variável de controlo '{var_name}' não declarada"
                )

            var_offset = self.layout[var_name]["offset"]

            start_label = self.new_label("FOR")
            end_label = self.new_label("ENDFOR")

            # i := valor inicial
            self.generate_expression(start_expr)
            self.emit(f"STOREG {var_offset}")

            self.emit(f"{start_label}:")

            # condição: i <= fim   ou   i >= fim
            self.emit(f"PUSHG {var_offset}")
            self.generate_expression(end_expr)

            if direction == "to":
                self.emit("INFEQ")
            elif direction == "downto":
                self.emit("SUPEQ")
            else:
                raise CodeGenerationError(
                    f"Direção de for desconhecida: {direction}"
                )

            self.emit(f"JZ {end_label}")

            self.generate_statement(body)

            # incremento/decremento
            self.emit(f"PUSHG {var_offset}")
            self.emit("PUSHI 1")

            if direction == "to":
                self.emit("ADD")
            else:
                self.emit("SUB")

            self.emit(f"STOREG {var_offset}")

            self.emit(f"JUMP {start_label}")
            self.emit(f"{end_label}:")

        else:
            raise CodeGenerationError(f"Statement não suportado: {statement}")

    def variable_type(self, variable):
        kind = variable[0]

        if kind == "var":
            _, name = variable
            return self.symbols[name]["type"]

        if kind == "array_access":
            _, name, index_expr = variable
            return self.symbols[name]["type"]

        raise CodeGenerationError(f"Variável inválida: {variable}")

    def store_variable(self, variable):
        kind = variable[0]

        if kind == "var":
            _, name = variable
            offset = self.layout[name]["offset"]
            self.emit(f"STOREG {offset}")
            return

        if kind == "array_access":
            raise CodeGenerationError(
                "Atribuição a arrays ainda não está suportada nesta versão"
            )

        raise CodeGenerationError(f"Variável inválida: {variable}")

    def generate_expression(self, expression):
        kind = expression[0]

        if kind == "int":
            _, value = expression
            self.emit(f"PUSHI {value}")

        elif kind == "string":
            _, value = expression
            self.emit(f'PUSHS "{self.escape_string(value)}"')

        elif kind == "bool":
            _, value = expression
            self.emit("PUSHI 1" if value else "PUSHI 0")

        elif kind == "var":
            _, name = expression
            offset = self.layout[name]["offset"]
            self.emit(f"PUSHG {offset}")

        elif kind == "array_access":
            raise CodeGenerationError(
                "Acesso a arrays ainda não está suportado nesta versão"
            )

        elif kind == "unop":
            _, operator, operand = expression

            if operator == "-":
                self.emit("PUSHI 0")
                self.generate_expression(operand)
                self.emit("SUB")

            elif operator == "not":
                self.generate_expression(operand)
                self.emit("NOT")

            else:
                raise CodeGenerationError(
                    f"Operador unário não suportado: {operator}"
                )

        elif kind == "binop":
            _, operator, left, right = expression

            self.generate_expression(left)
            self.generate_expression(right)

            if operator == "+":
                self.emit("ADD")
            elif operator == "-":
                self.emit("SUB")
            elif operator == "*":
                self.emit("MUL")
            elif operator in ("/", "div"):
                self.emit("DIV")
            elif operator == "mod":
                self.emit("MOD")

            elif operator == "=":
                self.emit("EQUAL")
            elif operator == "<>":
                self.emit("EQUAL")
                self.emit("NOT")
            elif operator == "<":
                self.emit("INF")
            elif operator == "<=":
                self.emit("INFEQ")
            elif operator == ">":
                self.emit("SUP")
            elif operator == ">=":
                self.emit("SUPEQ")

            elif operator == "and":
                self.emit("AND")
            elif operator == "or":
                self.emit("OR")

            else:
                raise CodeGenerationError(
                    f"Operador binário não suportado: {operator}"
                )

        else:
            raise CodeGenerationError(f"Expressão não suportada: {expression}")


def generate_program(ast):
    symbols, semantic_errors = check_program(ast)

    if semantic_errors:
        raise CodeGenerationError(
            "Erros semânticos:\n" +
            "\n".join(f"- {error}" for error in semantic_errors)
        )

    generator = CodeGenerator(symbols)
    return generator.generate_program(ast)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/codegen.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)

    try:
        ewvm_code = generate_program(ast)
        print(ewvm_code)
    except CodeGenerationError as error:
        print(error, file=sys.stderr)
        sys.exit(1)