import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELLO = ROOT / "examples" / "hello.pas"


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "compiler.py"), *arguments],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )

    def test_tokens(self):
        result = self.run_cli("--tokens", str(HELLO))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("LexToken(PROGRAM", result.stdout)

    def test_ast(self):
        result = self.run_cli("--ast", str(HELLO))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'program'", result.stdout)
        self.assertIn("'helloworld'", result.stdout)

    def test_symbols(self):
        result = self.run_cli("--symbols", str(ROOT / "examples" / "fatorial.pas"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'globals'", result.stdout)
        self.assertIn("'functions'", result.stdout)

    def test_output_option_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "hello.vm"
            result = self.run_cli(str(HELLO), "-o", str(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.read_text(encoding="utf-8").endswith("STOP\n"))


if __name__ == "__main__":
    unittest.main()
