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
        self.current_function = None

    def build_memory_layout(self, symbols):
        layout = {}
        for offset, (name, info) in enumerate(symbols.items()):
            layout[name] = dict(info, offset=offset)
        return layout

    def emit(self, instruction):
        self.instructions.append(instruction)

    def new_label(self, prefix="L"):
        self.label_counter += 1
        return f"{prefix}{self.label_counter}"

    def escape_string(self, value):
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def context(self):
        if self.current_function is None:
            return None
        return {"name": self.current_function[0], "function": self.current_function[1]}

    def expression_type(self, expression):
        errors = []
        result = infer_expression_type(expression, self.symbols, errors, self.context())
        if errors:
            raise CodeGenerationError("; ".join(errors))
        return result

    def resolve_storage(self, name):
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
        self.emit('PUSHS ""' if value_type == "string" else "PUSHI 0")

    def emit_global_initialization(self):
        for info in self.layout.values():
            self.emit_default_value(info["type"])

    def emit_array_allocation(self):
        for info in self.layout.values():
            if info["kind"] == "array":
                self.emit(f"PUSHI {info['size']}")
                self.emit("ALLOCN")
                self.emit(f"STOREG {info['offset']}")

    def generate_array_address(self, name, index_expression):
        region, info = self.resolve_storage(name)
        self.emit(f"PUSH{region} {info['offset'] if region == 'G' else info['index']}")
        self.generate_expression(index_expression)
        if info["start"] != 0:
            self.emit(f"PUSHI {info['start']}")
            self.emit("SUB")

    def generate_string_access(self, name, index_expression):
        """Gera um acesso Pascal base 1 usando CHARAT, que é base zero."""
        region, info = self.resolve_storage(name)
        index = info["offset"] if region == "G" else info["index"]
        self.emit(f"PUSH{region} {index}")
        self.generate_expression(index_expression)
        self.emit("PUSHI 1")
        self.emit("SUB")
        self.emit("CHARAT")

    def generate_indexed_access(self, name, index_expression):
        _, info = self.resolve_storage(name)
        if info["kind"] == "array":
            self.generate_array_address(name, index_expression)
            self.emit("LOADN")
        elif info["type"] == "string":
            self.generate_string_access(name, index_expression)
        else:
            raise CodeGenerationError(f"Símbolo '{name}' não pode ser indexado")

    def generate_program(self, ast):
        if ast[0] != "program":
            raise CodeGenerationError("AST inválida: raiz não é program")
        _, program_name, declarations, function_declarations, block = ast
        self.emit_global_initialization()
        self.emit("START")
        self.emit_array_allocation()
        self.generate_statement(block)
        self.emit("STOP")
        for declaration in function_declarations:
            self.generate_function(declaration)
        return "\n".join(self.instructions) + "\n"

    def generate_function(self, declaration):
        _, name, parameters, return_node, local_declarations, body = declaration
        function = self.symbols.functions[name]
        self.current_function = (name, function)
        self.emit(f"{function['label']}:")
        for info in function["locals"].values():
            self.emit_default_value(info["type"])
        self.generate_statement(body)
        self.emit("RETURN")
        self.current_function = None

    def generate_statement(self, statement):
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

    def variable_type(self, variable):
        _, info = self.resolve_storage(variable[1])
        return info["type"]

    def store_variable(self, variable):
        _, name = variable
        region, info = self.resolve_storage(name)
        index = info["offset"] if region == "G" else info["index"]
        self.emit(f"STORE{region} {index}")

    def generate_call(self, name, arguments):
        if name == "length":
            self.generate_expression(arguments[0])
            self.emit("STRLEN")
            return
        function = self.symbols.functions[name]
        self.emit_default_value(function["return_type"])
        for argument in arguments:
            self.generate_expression(argument)
        self.emit(f"PUSHA {function['label']}")
        self.emit("CALL")
        self.emit(f"POP {len(arguments)}")

    def generate_expression(self, expression):
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


def generate_program(ast):
    symbols, errors = check_program(ast)
    if errors:
        raise CodeGenerationError("Erros semânticos:\n" + "\n".join(f"- {error}" for error in errors))
    return CodeGenerator(symbols).generate_program(ast)


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
