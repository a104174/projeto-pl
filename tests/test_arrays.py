import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from compiler import compile_file
from src.codegen import CodeGenerationError, CodeGenerator, generate_program
from src.lexer import tokenize
from src.parser import parse
from src.semantic import check_program


ROOT = Path(__file__).resolve().parents[1]


def program(declarations, statements):
    return f"program Teste; var {declarations} begin {statements} end."


class ArrayCompilerTests(unittest.TestCase):
    def assert_semantic_error(self, source, fragment):
        _, errors = check_program(parse(source))
        self.assertTrue(
            any(fragment in error for error in errors),
            f"Não foi encontrado {fragment!r} em {errors!r}",
        )

    def test_lexer_array_declaration_and_access(self):
        source = program(
            "a: array[1..5] of integer; i: integer;",
            "a[i] := 1;",
        )
        token_types = [token.type for token in tokenize(source)]
        for expected in ("ARRAY", "LBRACKET", "DOTDOT", "RBRACKET", "OF"):
            self.assertIn(expected, token_types)

    def test_parser_array_declaration(self):
        ast = parse(program("a: array[1..5] of integer;", "a[1] := 2;"))
        self.assertEqual(
            ast[2][0],
            ("var_decl", ["a"], ("array", 1, 5, ("type", "integer"))),
        )

    def test_parser_array_access(self):
        ast = parse(program("a: array[1..5] of integer;", "a[2] := 7;"))
        self.assertEqual(ast[4][1][0][1], ("array_access", "a", ("int", 2)))

    def test_symbol_table_array_metadata(self):
        ast = parse(program("a: array[1..5] of integer;", "a[1] := 2;"))
        symbols, errors = check_program(ast)
        self.assertEqual(errors, [])
        self.assertEqual(
            symbols["a"],
            {"kind": "array", "type": "integer", "start": 1, "end": 5, "size": 5},
        )

    def test_array_uses_one_global_offset(self):
        ast = parse(program("a: array[1..5] of integer; x: integer;", "x := 0;"))
        symbols, errors = check_program(ast)
        self.assertEqual(errors, [])
        layout = CodeGenerator(symbols).layout
        self.assertEqual(layout["a"]["offset"], 0)
        self.assertEqual(layout["x"]["offset"], 1)

    def test_inverted_bounds_error(self):
        self.assert_semantic_error(
            program("a: array[5..1] of integer;", "a[5] := 1;"),
            "limites inválidos",
        )

    def test_non_integer_index_errors(self):
        for index in ("true", "'x'"):
            with self.subTest(index=index):
                self.assert_semantic_error(
                    program("a: array[1..5] of integer;", f"a[{index}] := 1;"),
                    "tem de ser integer",
                )

    def test_scalar_index_error(self):
        self.assert_semantic_error(
            program("x: integer;", "x[1] := 2;"),
            "não é um array",
        )

    def test_array_without_index_error(self):
        self.assert_semantic_error(
            program("a: array[1..5] of integer; x: integer;", "x := a;"),
            "usado sem índice",
        )

    def test_literal_out_of_bounds_error(self):
        self.assert_semantic_error(
            program("a: array[1..5] of integer;", "a[6] := 2;"),
            "fora dos limites",
        )

    def test_only_integer_element_arrays_are_supported(self):
        self.assert_semantic_error(
            program("a: array[1..5] of boolean;", "a[1] := true;"),
            "apenas integer é suportado",
        )

    def test_codegen_allocation(self):
        code = generate_program(parse(program("a: array[1..5] of integer;", "a[1] := 2;")))
        self.assertIn("PUSHI 5\nALLOCN\nSTOREG 0", code)

    def test_codegen_read_uses_storen(self):
        code = generate_program(parse(program("a: array[1..5] of integer;", "readln(a[1]);")))
        self.assertIn("READ\nATOI\nSTOREN", code)

    def test_codegen_expression_uses_loadn(self):
        source = program("a: array[1..5] of integer; x: integer;", "x := a[1];")
        self.assertIn("LOADN\nSTOREG 1", generate_program(parse(source)))

    def test_codegen_normalizes_lower_bound(self):
        source = program("a: array[1..5] of integer; i: integer;", "a[i] := 2;")
        code = generate_program(parse(source))
        self.assertIn("PUSHG 0\nPUSHG 1\nPUSHI 1\nSUB\nPUSHI 2\nSTOREN", code)

    def test_assignment_type_mismatch(self):
        self.assert_semantic_error(
            program("a: array[1..5] of integer;", "a[1] := true;"),
            "Atribuição inválida",
        )

    def test_existing_examples_compile(self):
        for name in ("hello.pas", "fatorial.pas", "numero_primo.pas"):
            with self.subTest(name=name):
                code = compile_file(ROOT / "examples" / name)
                self.assertTrue(code.endswith("STOP\n"))

    def test_soma_array_compiles(self):
        code = compile_file(ROOT / "examples" / "soma_array.pas")
        for instruction in ("ALLOCN", "STOREN", "LOADN", "FOR1:", "STOP"):
            self.assertIn(instruction, code)

    def test_compiler_output_option(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "hello.vm"
            result = subprocess.run(
                [sys.executable, str(ROOT / "compiler.py"),
                 str(ROOT / "examples" / "hello.pas"), "-o", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.read_text(encoding="utf-8").endswith("STOP\n"))


if __name__ == "__main__":
    unittest.main()
