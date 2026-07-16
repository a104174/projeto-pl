"""
Analisador lexical do subconjunto de Pascal suportado pelo compilador.

Este módulo utiliza ``ply.lex`` para transformar código-fonte Pascal numa
sequência de tokens. São reconhecidos:

- palavras reservadas e identificadores;
- números inteiros e literais string;
- operadores aritméticos, relacionais e de atribuição;
- delimitadores e símbolos de pontuação;
- comentários nos formatos ``{ ... }``, ``(* ... *)`` e ``// ...``.

Como Pascal não distingue maiúsculas de minúsculas nos identificadores,
as palavras e identificadores reconhecidos são normalizados para
minúsculas.

O módulo disponibiliza o lexer construído pelo PLY e a função ``tokenize``,
que permite executar a análise lexical de um programa completo.
"""

import sys

import ply.lex as lex


# ---------------------------------------------------------------------------
# Palavras reservadas
# ---------------------------------------------------------------------------

# Palavras reservadas pertencentes ao subconjunto de Pascal suportado.
# As chaves são guardadas em minúsculas porque a linguagem é
# case-insensitive.
reserved = {
    "program": "PROGRAM",
    "function": "FUNCTION",
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
}


# ---------------------------------------------------------------------------
# Tipos de token
# ---------------------------------------------------------------------------

# O PLY requer que todos os tipos de token possíveis sejam declarados.
# As palavras reservadas são acrescentadas aos restantes tokens da linguagem.
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


# ---------------------------------------------------------------------------
# Operadores e delimitadores
# ---------------------------------------------------------------------------

# Os símbolos com vários caracteres são declarados separadamente das formas
# de um carácter com as quais partilham prefixos, como ":"/":=" e "."/"..".
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


# Espaços, tabulações e carriage returns não têm significado sintático.
# As mudanças de linha são tratadas por uma regra própria para manter
# informação correta para os diagnósticos.
t_ignore = " \t\r"


# ---------------------------------------------------------------------------
# Regras lexicais com processamento adicional
# ---------------------------------------------------------------------------

# Reconhece os três formatos de comentário suportados. Os comentários não
# originam tokens, mas as mudanças de linha no seu interior são contabilizadas.
def t_COMMENT(t):
    r"\{[^}]*\}|\(\*(?:.|\n)*?\*\)|//[^\n]*"
    t.lexer.lineno += t.value.count("\n")


# Reconhece strings delimitadas por aspas simples. Em Pascal, duas aspas
# simples consecutivas representam uma aspa dentro do valor da string.
def t_STRING_LITERAL(t):
    r"'([^'\n]|'')*'"
    t.value = t.value[1:-1].replace("''", "'")
    return t


# Converte imediatamente o lexema numérico para um valor inteiro.
def t_NUMBER(t):
    r"\d+"
    t.value = int(t.value)
    return t


# Reconhece identificadores e distingue-os das palavras reservadas.
def t_ID(t):
    r"[A-Za-z_][A-Za-z0-9_]*"
    value = t.value.lower()

    t.type = reserved.get(value, "ID")
    t.value = value
    return t


# Atualiza o número da linha sem produzir um token.
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)


# O lexer segue uma estratégia fail-fast: a análise termina assim que é
# encontrado um carácter que não pertence ao vocabulário lexical suportado.
def t_error(t):
    raise SyntaxError(
        f"Carácter inválido '{t.value[0]}' na linha {t.lexer.lineno}"
    )


# O PLY inspeciona as regras anteriores e constrói o analisador lexical.
lexer = lex.lex()


def tokenize(source_code):
    """
    Converte código-fonte Pascal numa lista de tokens.

    O contador de linhas é reiniciado em cada execução, permitindo utilizar
    o mesmo lexer para analisar vários programas no mesmo processo.

    Args:
        source_code: Código-fonte Pascal a analisar.

    Returns:
        Lista de tokens produzidos pelo lexer.

    Raises:
        SyntaxError: Se for encontrado um carácter inválido.
    """
    lexer.lineno = 1
    lexer.input(source_code)
    return list(lexer)


# Permite testar o analisador lexical independentemente das restantes fases
# do compilador.
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/lexer.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    for tok in tokenize(source):
        print(tok)