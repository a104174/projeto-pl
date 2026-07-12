import unittest

from src.codegen import generate_program
from src.lexer import tokenize
from src.parser import parse
from src.semantic import check_program


def source(functions, globals_text="x: integer;", main="x := 0;"):
    return f"program Teste; {functions} var {globals_text} begin {main} end."


SIMPLE = """
function Dobro(n: integer): integer;
var r: integer;
begin
  r := n * 2;
  Dobro := r;
end;
"""


class FunctionTests(unittest.TestCase):
    def errors(self, text):
        return check_program(parse(text))[1]

    def assert_error(self, text, fragment):
        errors = self.errors(text)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_function_token(self):
        self.assertIn("FUNCTION", [token.type for token in tokenize(source(SIMPLE))])

    def test_parse_function_without_parameters(self):
        text = source("function Um(): integer; begin Um := 1; end;", main="x := Um();")
        self.assertEqual(parse(text)[3][0][2], [])

    def test_parse_one_parameter_and_local(self):
        function = parse(source(SIMPLE))[3][0]
        self.assertEqual(function[0], "function_decl")
        self.assertEqual(function[2], [("param", "n", ("type", "integer"))])
        self.assertEqual(function[4][0][1], ["r"])

    def test_parse_grouped_parameters(self):
        function = "function Escolhe(a, b: integer; ativo: boolean): integer; begin Escolhe := a; end;"
        params = parse(source(function))[3][0][2]
        self.assertEqual([param[1] for param in params], ["a", "b", "ativo"])

    def test_call_and_result_assignment_ast(self):
        ast = parse(source(SIMPLE, main="x := Dobro(3);"))
        self.assertEqual(ast[3][0][5][1][-1][1], ("var", "dobro"))
        self.assertEqual(ast[4][1][0][2], ("call", "dobro", [("int", 3)]))

    def test_duplicate_function(self):
        one = "function F(): integer; begin F := 1; end;"
        self.assert_error(source(one + one), "declarada mais do que uma vez")

    def test_duplicate_parameter(self):
        function = "function F(a, a: integer): integer; begin F := a; end;"
        self.assert_error(source(function), "Parâmetro 'a' duplicado")

    def test_duplicate_local(self):
        function = "function F(): integer; var a, a: integer; begin F := 1; end;"
        self.assert_error(source(function), "declarada mais do que uma vez")

    def test_parameter_local_conflict(self):
        function = "function F(a: integer): integer; var a: integer; begin F := a; end;"
        self.assert_error(source(function), "entra em conflito")

    def test_undeclared_function(self):
        self.assert_error(source("", main="x := Falta(1);"), "não declarada")

    def test_wrong_argument_count(self):
        self.assert_error(source(SIMPLE, main="x := Dobro();"), "espera 1 argumento")

    def test_wrong_argument_type(self):
        self.assert_error(source(SIMPLE, main="x := Dobro(true);"), "esperado integer")

    def test_wrong_return_type(self):
        function = "function F(): integer; begin F := true; end;"
        self.assert_error(source(function), "Atribuição inválida")

    def test_missing_result_assignment(self):
        function = "function F(): integer; begin x := 1; end;"
        self.assert_error(source(function), "não atribui um valor")

    def test_local_not_visible_in_main(self):
        self.assert_error(source(SIMPLE, main="x := r;"), "usada sem declaração")

    def test_parameter_and_global_visible_in_function(self):
        function = "function F(a: integer): integer; begin F := a + x; end;"
        self.assertEqual(self.errors(source(function, main="x := F(1);")), [])

    def test_local_shadows_global(self):
        function = "function F(): boolean; var x: boolean; begin x := true; F := x; end;"
        self.assertEqual(self.errors(source(function, main="x := 0;")), [])

    def test_variable_cannot_be_called(self):
        self.assert_error(source("", main="x := x();"), "usada como função")

    def test_parameter_cannot_use_function_name(self):
        function = "function F(F: integer): integer; begin F := 1; end;"
        self.assert_error(source(function), "mesmo nome da função")

    def test_local_cannot_use_function_name(self):
        function = "function F(): integer; var F: integer; begin F := 1; end;"
        self.assert_error(source(function), "mesmo nome da função")

    def test_function_conflicts_with_global(self):
        function = "function F(): integer; begin F := 1; end;"
        self.assert_error(source(function, globals_text="f: integer;"), "conflito com uma variável global")

    def test_length_cannot_be_shadowed(self):
        cases = (
            source("", globals_text="length: integer;"),
            source("function F(length: integer): integer; begin F := 1; end;"),
            source("function F(): integer; var length: integer; begin F := 1; end;"),
        )
        for text in cases:
            with self.subTest(text=text):
                self.assert_error(text, "função built-in")

    def test_function_cannot_be_used_without_call(self):
        self.assert_error(source(SIMPLE, main="x := Dobro;"), "usada sem chamada")

    def test_codegen_calling_convention(self):
        code = generate_program(parse(source(SIMPLE, main="x := Dobro(3);")))
        self.assertIn("PUSHI 0\nPUSHI 3\nPUSHA FUNC1\nCALL\nPOP 1", code)

    def test_function_after_stop_and_return(self):
        code = generate_program(parse(source(SIMPLE, main="x := Dobro(3);")))
        self.assertLess(code.index("STOP"), code.index("FUNC1:"))
        self.assertTrue(code.endswith("RETURN\n"))

    def test_parameter_local_and_return_layout(self):
        code = generate_program(parse(source(SIMPLE, main="x := Dobro(3);")))
        function_code = code.split("FUNC1:", 1)[1]
        self.assertIn("PUSHL -1", function_code)
        self.assertIn("STOREL 0", function_code)
        self.assertIn("PUSHL 0", function_code)
        self.assertIn("STOREL -2", function_code)

    def test_local_for_uses_local_region(self):
        function = "function F(n: integer): integer; var i: integer; begin for i := 1 to n do F := i; end;"
        code = generate_program(parse(source(function, main="x := F(2);")))
        function_code = code.split("FUNC1:", 1)[1]
        self.assertIn("STOREL 0", function_code)
        self.assertIn("PUSHL 0", function_code)

    def test_function_labels_are_alphanumeric_and_match_calls(self):
        code = generate_program(parse(source(SIMPLE, main="x := Dobro(3);")))
        self.assertIn("PUSHA FUNC1", code)
        self.assertIn("FUNC1:", code)
        self.assertNotIn("FUNC_", code)

    def test_similar_function_names_receive_distinct_labels(self):
        functions = (
            "function a_b(): integer; begin a_b := 1; end; "
            "function ab(): integer; begin ab := 2; end;"
        )
        ast = parse(source(functions, main="x := a_b() + ab();"))
        symbols, errors = check_program(ast)
        self.assertEqual(errors, [])
        self.assertEqual(symbols.functions["a_b"]["label"], "FUNC1")
        self.assertEqual(symbols.functions["ab"]["label"], "FUNC2")
        code = generate_program(ast)
        for label in ("FUNC1", "FUNC2"):
            self.assertIn(f"PUSHA {label}", code)
            self.assertIn(f"{label}:", code)


if __name__ == "__main__":
    unittest.main()
