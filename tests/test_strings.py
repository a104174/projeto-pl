import unittest

from src.codegen import generate_program
from src.parser import parse
from src.semantic import check_program, infer_expression_type


class StringTests(unittest.TestCase):
    def check(self, expression):
        source = f"program T; var s: string; n: integer; begin {expression} end."
        return check_program(parse(source))[1]

    def test_length_string_and_strlen(self):
        source = "program T; var s: string; n: integer; begin n := length(s); end."
        ast = parse(source)
        self.assertEqual(ast[4][1][0][2], ("call", "length", [("var", "s")]))
        self.assertIn("PUSHG 0\nSTRLEN\nSTOREG 1", generate_program(ast))

    def test_length_invalid_type(self):
        self.assertTrue(any("tem de ser string" in error for error in self.check("n := length(n);")))

    def test_length_wrong_arity(self):
        self.assertTrue(any("exatamente um" in error for error in self.check("n := length(s, s);")))

    def test_length_cannot_be_redefined(self):
        source = "program T; function length(s: string): integer; begin length := 1; end; begin end."
        errors = check_program(parse(source))[1]
        self.assertTrue(any("não pode ser redefinida" in error for error in errors), errors)

    def test_string_indexing_has_internal_char_type(self):
        ast = parse("program T; var s: string; i: integer; begin i := i; end.")
        symbols, errors = check_program(ast)
        expression = ("array_access", "s", ("var", "i"))
        self.assertEqual(infer_expression_type(expression, symbols, errors), "char")
        self.assertEqual(errors, [])

    def test_string_index_requires_integer(self):
        for index in ("true", "'x'"):
            with self.subTest(index=index):
                errors = self.check(f"if s[{index}] = '1' then n := 1;")
                self.assertTrue(any("tem de ser integer" in error for error in errors), errors)

    def test_char_comparisons_with_one_character_literals(self):
        for condition in ("s[n] = '1'", "'1' = s[n]", "s[n] <> '0'", "'0' <> s[n]"):
            with self.subTest(condition=condition):
                self.assertEqual(self.check(f"if {condition} then n := 1;"), [])

    def test_char_comparison_with_long_string_is_rejected(self):
        errors = self.check("if s[n] = '10' then n := 1;")
        self.assertTrue(any("tipos incompatíveis" in error for error in errors), errors)

    def test_char_comparison_with_string_variable_is_rejected(self):
        errors = self.check("if s[n] = s then n := 1;")
        self.assertTrue(any("tipos incompatíveis" in error for error in errors), errors)

    def test_assignment_to_string_character_is_rejected(self):
        errors = self.check("s[n] := '1';")
        self.assertTrue(any("destino de atribuição" in error for error in errors), errors)

    def test_readln_string_character_is_rejected(self):
        errors = self.check("readln(s[n]);")
        self.assertTrue(any("destino de readln" in error for error in errors), errors)

    def test_string_index_codegen_uses_charat_and_normalizes_index(self):
        source = "program T; var s: string; n: integer; begin if s[n] = '1' then n := 1; end."
        code = generate_program(parse(source))
        self.assertIn("PUSHG 0\nPUSHG 1\nPUSHI 1\nSUB\nCHARAT", code)
        self.assertIn('PUSHS "1"\nCHRCODE\nEQUAL', code)
        self.assertNotIn("LOADN", code)

    def test_literal_on_left_is_converted_with_chrcode(self):
        source = "program T; var s: string; n: integer; begin if '1' = s[n] then n := 1; end."
        code = generate_program(parse(source))
        self.assertIn('PUSHS "1"\nCHRCODE\nPUSHG 0', code)

    def test_array_still_uses_loadn_not_charat(self):
        source = "program T; var a: array[1..2] of integer; n: integer; begin n := a[n]; end."
        code = generate_program(parse(source))
        self.assertIn("LOADN", code)
        self.assertNotIn("CHARAT", code)

    def test_string_parameter_uses_pushl_for_charat(self):
        source = (
            "program T; function F(s: string; i: integer): boolean; "
            "begin F := s[i] = '1'; end; var ok: boolean; begin ok := F('1', 1); end."
        )
        code = generate_program(parse(source))
        self.assertIn("PUSHL -1\nPUSHL -2\nPUSHI 1\nSUB\nCHARAT", code)

    def test_binario_para_inteiro_semantics_and_codegen(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "examples" / "binario_para_inteiro.pas").read_text(
            encoding="utf-8"
        )
        ast = parse(source)
        self.assertEqual(check_program(ast)[1], [])
        code = generate_program(ast)
        for instruction in (
            "STRLEN", "CHARAT", "CHRCODE", "PUSHA FUNC1",
            "CALL", "POP 1", "STOREL -2", "RETURN",
        ):
            self.assertIn(instruction, code)
        self.assertIn("FUNC1:", code)
        self.assertNotIn("FUNC_BINTOINT", code)

    def test_negative_array_bounds(self):
        source = "program T; var a: array[-2..2] of integer; begin a[-1] := 3; end."
        self.assertEqual(check_program(parse(source))[1], [])

    def test_zero_lower_bound_omits_sub(self):
        source = "program T; var a: array[0..2] of integer; i: integer; begin i := a[i]; end."
        code = generate_program(parse(source))
        self.assertIn("PUSHG 0\nPUSHG 1\nLOADN", code)
        self.assertNotIn("PUSHI 0\nSUB\nLOADN", code)


if __name__ == "__main__":
    unittest.main()
