import sys
import ply.lex as lex


# Palavras reservadas da linguagem pascal que vamos suportar
# Guardamos tudo em minúsculas porque pascal não distingue maiusculas/minusculas
reserved = {
    "program": "PROGRAM",
    "var": "VAR",
    "begin": "BEGIN",
    "end": "END",

    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "string": "STRING",

    "array": "ARRAY",
    "of": "OF",

    "if": "IF",
    "then": "THEN",
    "else": "ELSE",

    "while": "WHILE",
    "do": "DO",

    "for": "FOR",
    "to": "TO",
    "downto": "DOWNTO",

    "readln": "READLN",
    "writeln": "WRITELN",

    "true": "TRUE",
    "false": "FALSE",

    "and": "AND",
    "or": "OR",
    "not": "NOT",

    "div": "DIV",
    "mod": "MOD",

    "function": "FUNCTION",
    "procedure": "PROCEDURE",
}


tokens = [
    "ID",
    "NUMBER",
    "STRING_LITERAL",

    "ASSIGN",      # :=
    "PLUS",        # +
    "MINUS",       # -
    "TIMES",       # *
    "SLASH",       # /

    "EQ",          # =
    "NE",          # <>
    "LT",          # <
    "LE",          # <=
    "GT",          # >
    "GE",          # >=

    "LPAREN",      # (
    "RPAREN",      # )
    "LBRACKET",    # [
    "RBRACKET",    # ]

    "SEMI",        # ;
    "COLON",       # :
    "COMMA",       # ,
    "DOT",         # .
    "DOTDOT",      # ..
] + list(reserved.values())


# Operadores e símbolos com mais de um caracter têm de vir antes dos mais pequenos
t_ASSIGN = r":="
t_NE = r"<>"
t_LE = r"<="
t_GE = r">="
t_DOTDOT = r"\.\."

t_PLUS = r"\+"
t_MINUS = r"-"
t_TIMES = r"\*"
t_SLASH = r"/"

t_EQ = r"="
t_LT = r"<"
t_GT = r">"

t_LPAREN = r"\("
t_RPAREN = r"\)"
t_LBRACKET = r"\["
t_RBRACKET = r"\]"

t_SEMI = r";"
t_COLON = r":"
t_COMMA = r","
t_DOT = r"\."


# Ignorar espaços e tabs
t_ignore = " \t\r"


def t_COMMENT(t):
    r"\{[^}]*\}|\(\*(.|\n)*?\*\)|//[^\n]*"
    t.lexer.lineno += t.value.count("\n")
    pass


def t_STRING_LITERAL(t):
    r"'([^'\n]|'')*'"
    # Remove as aspas exteriores e trata '' como uma aspa simples dentro da string
    t.value = t.value[1:-1].replace("''", "'")
    return t


def t_NUMBER(t):
    r"\d+"
    t.value = int(t.value)
    return t


def t_ID(t):
    r"[A-Za-z_][A-Za-z0-9_]*"
    value = t.value.lower()

    # Se for palavra reservada, muda o tipo do token
    # Caso contrário, é um identificador normal
    t.type = reserved.get(value, "ID")
    t.value = value
    return t


def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


def t_error(t):
    raise SyntaxError(
        f"Carácter inválido '{t.value[0]}' na linha {t.lexer.lineno}"
    )


lexer = lex.lex()


def tokenize(source_code):
    lexer.input(source_code)
    return list(lexer)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/lexer.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    for tok in tokenize(source):
        print(tok)