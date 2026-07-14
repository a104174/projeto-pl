import sys
import ply.lex as lex


# Palavras reservadas da linguagem pascal que vamos suportar
# Guardamos tudo em minúsculas porque pascal não distingue maiusculas/minusculas
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


# Ignorar espaços e tabs - não aparece a nova linha porque temos a função t_newline a contar
t_ignore = " \t\r"

# Suporta 3 tipos de comentários: { ... }, (* ... *) e // ... (até ao fim da linha)
def t_COMMENT(t):
    r"\{[^}]*\}|\(\*(.|\n)*?\*\)|//[^\n]*"
    t.lexer.lineno += t.value.count("\n") 
    pass

# Literais string - ('Ola' ou 'D''Artagnan')
def t_STRING_LITERAL(t):
    r"'([^'\n]|'')*'"
    # Remove as aspas exteriores e trata '' como uma aspa simples dentro da string
    t.value = t.value[1:-1].replace("''", "'")
    return t

# Números inteiros - passamos de string para int
def t_NUMBER(t):
    r"\d+"
    t.value = int(t.value)
    return t

# Identificadores e palavras reservadas
def t_ID(t):
    r"[A-Za-z_][A-Za-z0-9_]*"
    value = t.value.lower()

    # Se for palavra reservada, muda o tipo do token
    # Caso contrário, é um id 
    t.type = reserved.get(value, "ID")
    t.value = value
    return t

# contar novas linhas para manter o número de linhas 
def t_newline(t):
    r"\n+"
    t.lexer.lineno += len(t.value)

# caso nenhum token reconhece um carácter, levanta um erro de sintaxe
# decidi parar a execução quando o lexer encontra um erro, 
# mas com o skip(1) podia avançar para o próximo token e continuar a análise, devolvendo depois no final todos os erros encontrados, numa lista
def t_error(t):
    raise SyntaxError(
        f"Carácter inválido '{t.value[0]}' na linha {t.lexer.lineno}"
    )

# controi o lexer com base nas regras definidas acima
lexer = lex.lex()

# Função que recebe o código fonte e devolve uma lista de tokens
def tokenize(source_code):
    lexer.input(source_code)
    return list(lexer)

# Permite executar o lexer diretamente, sem passar pelo compilador completo
# Foi útil para testar o lexer independetemente do parser e do resto do compilador
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/lexer.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    for tok in tokenize(source):
        print(tok)
