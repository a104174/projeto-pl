import sys
from pprint import pprint

import ply.yacc as yacc

try:
    from .lexer import tokens
except ImportError:
    from lexer import tokens


# Precedência dos operadores.
# Quanto mais em baixo, maior a prioridade.
precedence = (
    ("nonassoc", "IFX"),
    ("nonassoc", "ELSE"),

    ("left", "OR"),
    ("left", "AND"),
    ("right", "NOT"),
    ("nonassoc", "EQ", "NE", "LT", "LE", "GT", "GE"),
    ("left", "PLUS", "MINUS"),
    ("left", "TIMES", "SLASH", "DIV", "MOD"),
    ("right", "UMINUS"),
)


# -------------------------
# Programa principal
# -------------------------

def p_program(p):
    """
    program : PROGRAM ID SEMI declarations compound_statement DOT
    """
    p[0] = ("program", p[2], p[4], p[5])


# -------------------------
# Declarações
# -------------------------

def p_declarations_var(p):
    """
    declarations : VAR var_decl_list
    """
    p[0] = p[2]


def p_declarations_empty(p):
    """
    declarations : empty
    """
    p[0] = []


def p_var_decl_list_multiple(p):
    """
    var_decl_list : var_decl_list var_decl
    """
    p[0] = p[1] + [p[2]]


def p_var_decl_list_single(p):
    """
    var_decl_list : var_decl
    """
    p[0] = [p[1]]


def p_var_decl(p):
    """
    var_decl : id_list COLON type SEMI
    """
    p[0] = ("var_decl", p[1], p[3])


def p_id_list_multiple(p):
    """
    id_list : id_list COMMA ID
    """
    p[0] = p[1] + [p[3]]


def p_id_list_single(p):
    """
    id_list : ID
    """
    p[0] = [p[1]]


def p_type_simple(p):
    """
    type : simple_type
    """
    p[0] = p[1]


def p_type_array(p):
    """
    type : ARRAY LBRACKET NUMBER DOTDOT NUMBER RBRACKET OF simple_type
    """
    p[0] = ("array", p[3], p[5], p[8])


def p_simple_type_integer(p):
    """
    simple_type : INTEGER
    """
    p[0] = ("type", "integer")


def p_simple_type_boolean(p):
    """
    simple_type : BOOLEAN
    """
    p[0] = ("type", "boolean")


def p_simple_type_string(p):
    """
    simple_type : STRING
    """
    p[0] = ("type", "string")


# -------------------------
# Blocos e statements
# -------------------------

def p_compound_statement(p):
    """
    compound_statement : BEGIN optional_statement_list END
    """
    p[0] = ("block", p[2])


def p_optional_statement_list_some(p):
    """
    optional_statement_list : statement_list
    """
    p[0] = p[1]


def p_optional_statement_list_empty(p):
    """
    optional_statement_list : empty
    """
    p[0] = []


def p_statement_list_single(p):
    """
    statement_list : statement
    """
    p[0] = [p[1]]


def p_statement_list_multiple(p):
    """
    statement_list : statement_list SEMI statement
    """
    p[0] = p[1] + [p[3]]


def p_statement_list_trailing_semi(p):
    """
    statement_list : statement_list SEMI
    """
    p[0] = p[1]


def p_statement_compound(p):
    """
    statement : compound_statement
    """
    p[0] = p[1]


def p_statement_assignment(p):
    """
    statement : assignment
    """
    p[0] = p[1]


def p_statement_readln(p):
    """
    statement : readln_statement
    """
    p[0] = p[1]


def p_statement_writeln(p):
    """
    statement : writeln_statement
    """
    p[0] = p[1]


def p_statement_if(p):
    """
    statement : if_statement
    """
    p[0] = p[1]


def p_statement_while(p):
    """
    statement : while_statement
    """
    p[0] = p[1]


def p_statement_for(p):
    """
    statement : for_statement
    """
    p[0] = p[1]


# -------------------------
# Statements concretos
# -------------------------

def p_assignment(p):
    """
    assignment : variable ASSIGN expression
    """
    p[0] = ("assign", p[1], p[3])


def p_readln_statement(p):
    """
    readln_statement : READLN LPAREN variable_list RPAREN
    """
    p[0] = ("readln", p[3])


def p_variable_list_multiple(p):
    """
    variable_list : variable_list COMMA variable
    """
    p[0] = p[1] + [p[3]]


def p_variable_list_single(p):
    """
    variable_list : variable
    """
    p[0] = [p[1]]


def p_writeln_statement_with_args(p):
    """
    writeln_statement : WRITELN LPAREN expression_list RPAREN
    """
    p[0] = ("writeln", p[3])


def p_writeln_statement_empty(p):
    """
    writeln_statement : WRITELN LPAREN RPAREN
    """
    p[0] = ("writeln", [])


def p_expression_list_multiple(p):
    """
    expression_list : expression_list COMMA expression
    """
    p[0] = p[1] + [p[3]]


def p_expression_list_single(p):
    """
    expression_list : expression
    """
    p[0] = [p[1]]


def p_if_statement_with_else(p):
    """
    if_statement : IF expression THEN statement ELSE statement
    """
    p[0] = ("if", p[2], p[4], p[6])


def p_if_statement_without_else(p):
    """
    if_statement : IF expression THEN statement %prec IFX
    """
    p[0] = ("if", p[2], p[4], None)


def p_while_statement(p):
    """
    while_statement : WHILE expression DO statement
    """
    p[0] = ("while", p[2], p[4])


def p_for_statement(p):
    """
    for_statement : FOR ID ASSIGN expression direction expression DO statement
    """
    p[0] = ("for", p[2], p[4], p[5], p[6], p[8])


def p_direction_to(p):
    """
    direction : TO
    """
    p[0] = "to"


def p_direction_downto(p):
    """
    direction : DOWNTO
    """
    p[0] = "downto"


# -------------------------
# Variáveis
# -------------------------

def p_variable_id(p):
    """
    variable : ID
    """
    p[0] = ("var", p[1])


def p_variable_array_access(p):
    """
    variable : ID LBRACKET expression RBRACKET
    """
    p[0] = ("array_access", p[1], p[3])


# -------------------------
# Expressões
# -------------------------

def p_expression_number(p):
    """
    expression : NUMBER
    """
    p[0] = ("int", p[1])


def p_expression_string(p):
    """
    expression : STRING_LITERAL
    """
    p[0] = ("string", p[1])


def p_expression_true(p):
    """
    expression : TRUE
    """
    p[0] = ("bool", True)


def p_expression_false(p):
    """
    expression : FALSE
    """
    p[0] = ("bool", False)


def p_expression_variable(p):
    """
    expression : variable
    """
    p[0] = p[1]


def p_expression_group(p):
    """
    expression : LPAREN expression RPAREN
    """
    p[0] = p[2]


def p_expression_unary_minus(p):
    """
    expression : MINUS expression %prec UMINUS
    """
    p[0] = ("unop", "-", p[2])


def p_expression_not(p):
    """
    expression : NOT expression
    """
    p[0] = ("unop", "not", p[2])


def p_expression_binary(p):
    """
    expression : expression PLUS expression
               | expression MINUS expression
               | expression TIMES expression
               | expression SLASH expression
               | expression DIV expression
               | expression MOD expression
               | expression EQ expression
               | expression NE expression
               | expression LT expression
               | expression LE expression
               | expression GT expression
               | expression GE expression
               | expression AND expression
               | expression OR expression
    """
    p[0] = ("binop", p[2], p[1], p[3])


# -------------------------
# Auxiliar
# -------------------------

def p_empty(p):
    """
    empty :
    """
    p[0] = None


def p_error(p):
    if p:
        raise SyntaxError(
            f"Erro sintático perto de '{p.value}' na linha {p.lineno}"
        )
    raise SyntaxError("Erro sintático: fim inesperado do ficheiro")


parser = yacc.yacc()


def parse(source_code):
    return parser.parse(source_code)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/parser.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)
    pprint(ast)