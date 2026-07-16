"""
Analisador sintático do subconjunto de Pascal suportado.

O módulo utiliza ``ply.yacc`` para construir um parser LALR. As produções
definidas nas funções ``p_*`` reconhecem a estrutura do programa e constroem
uma AST representada por tuplos e listas.

A função ``parse`` recebe código-fonte Pascal e devolve a AST correspondente.
As verificações de tipos, declarações e utilização de identificadores são
realizadas posteriormente pela análise semântica.
"""

import sys
from pprint import pprint

import ply.yacc as yacc

# O primeiro import é utilizado quando o módulo pertence ao pacote ``src``.
# O segundo permite executar diretamente: python src/parser.py ficheiro.pas
try:
    from .lexer import lexer, tokens
except ImportError:
    from lexer import lexer, tokens


# =============================================================================
# Precedência e associatividade
# =============================================================================

# A precedência está ordenada da menor para a maior prioridade.
#
# IFX e UMINUS são marcadores internos: não são tokens produzidos pelo lexer.
# IFX resolve a associação do ELSE ao IF mais próximo, enquanto UMINUS
# distingue o menos unário da subtração binária.
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


# =============================================================================
# Programa, funções e parâmetros
# =============================================================================

# Nó produzido:
# ("program", nome, declaracoes_globais, funcoes, bloco_principal)
def p_program(p):
    """
    program : PROGRAM ID SEMI function_declarations declarations compound_statement DOT
    """
    p[0] = ("program", p[2], p[5], p[4], p[6])


# As listas são construídas por recursão à esquerda, adequada ao parser LALR.
def p_function_declarations_multiple(p):
    """
    function_declarations : function_declarations function_decl
    """
    p[0] = p[1] + [p[2]]


def p_function_declarations_empty(p):
    """
    function_declarations : empty
    """
    p[0] = []


# Nó produzido:
# ("function_decl", nome, parametros, tipo_retorno, declaracoes_locais, corpo)
#
# O retorno de uma função Pascal é posteriormente identificado através de uma
# atribuição ao nome da própria função.
def p_function_decl(p):
    """
    function_decl : FUNCTION ID LPAREN optional_parameters RPAREN COLON simple_type SEMI declarations compound_statement SEMI
    """
    p[0] = ("function_decl", p[2], p[4], p[7], p[9], p[10])


def p_optional_parameters_some(p):
    """
    optional_parameters : parameter_groups
    """
    p[0] = p[1]


def p_optional_parameters_empty(p):
    """
    optional_parameters : empty
    """
    p[0] = []


# Os diferentes grupos, separados por ponto e vírgula, são combinados numa
# única lista plana de parâmetros.
def p_parameter_groups_multiple(p):
    """
    parameter_groups : parameter_groups SEMI parameter_group
    """
    p[0] = p[1] + p[3]


def p_parameter_groups_single(p):
    """
    parameter_groups : parameter_group
    """
    p[0] = p[1]


# Cada identificador do grupo origina um nó de parâmetro individual.
# Os parâmetros são limitados aos tipos simples suportados.
def p_parameter_group(p):
    """
    parameter_group : id_list COLON simple_type
    """
    p[0] = [("param", name, p[3]) for name in p[1]]


# =============================================================================
# Declarações e tipos
# =============================================================================

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


# Nó produzido:
# ("var_decl", lista_de_nomes, tipo)
def p_var_decl(p):
    """
    var_decl : id_list COLON type SEMI
    """
    p[0] = ("var_decl", p[1], p[3])


# Uma lista de identificadores contém obrigatoriamente pelo menos um elemento.
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


# Os arrays suportados são unidimensionais e têm limites inteiros conhecidos
# durante a compilação.
#
# Nó produzido:
# ("array", limite_inferior, limite_superior, tipo_dos_elementos)
def p_type_array(p):
    """
    type : ARRAY LBRACKET integer_literal DOTDOT integer_literal RBRACKET OF simple_type
    """
    p[0] = ("array", p[3], p[5], p[8])


# NUMBER e PLUS NUMBER originam o mesmo valor positivo. Em ambas as produções,
# o número encontra-se na última posição de ``p``.
def p_integer_literal_positive(p):
    """
    integer_literal : NUMBER
                    | PLUS NUMBER
    """
    p[0] = p[len(p) - 1]


def p_integer_literal_negative(p):
    """
    integer_literal : MINUS NUMBER
    """
    p[0] = -p[2]


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


# =============================================================================
# Blocos e listas de statements
# =============================================================================

# Um compound statement agrupa zero ou mais comandos entre BEGIN e END.
#
# Nó produzido:
# ("block", lista_de_statements)
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


# Permite um ponto e vírgula depois do último statement do bloco.
def p_statement_list_trailing_semi(p):
    """
    statement_list : statement_list SEMI
    """
    p[0] = p[1]


# As produções seguintes promovem cada comando concreto ao não terminal
# genérico ``statement``. Não é criado um nó adicional na AST.
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


# =============================================================================
# Statements concretos e estruturas de controlo
# =============================================================================

# O destino de uma atribuição pode ser uma variável simples ou um acesso
# indexado.
#
# Nó produzido:
# ("assign", destino, expressao)
def p_assignment(p):
    """
    assignment : variable ASSIGN expression
    """
    p[0] = ("assign", p[1], p[3])


# READLN recebe variáveis, uma vez que cada valor lido necessita de um local
# onde possa ser armazenado.
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


# WRITELN aceita expressões, permitindo apresentar valores calculados.
def p_writeln_statement_with_args(p):
    """
    writeln_statement : WRITELN LPAREN expression_list RPAREN
    """
    p[0] = ("writeln", p[3])


# WRITELN sem argumentos representa apenas uma mudança de linha.
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


# Nó produzido:
# ("if", condicao, ramo_then, ramo_else)
def p_if_statement_with_else(p):
    """
    if_statement : IF expression THEN statement ELSE statement
    """
    p[0] = ("if", p[2], p[4], p[6])


# IFX atribui uma precedência inferior à de ELSE, fazendo com que um ELSE seja
# associado ao IF ainda incompleto mais próximo.
def p_if_statement_without_else(p):
    """
    if_statement : IF expression THEN statement %prec IFX
    """
    p[0] = ("if", p[2], p[4], None)


# Nó produzido:
# ("while", condicao, corpo)
def p_while_statement(p):
    """
    while_statement : WHILE expression DO statement
    """
    p[0] = ("while", p[2], p[4])


# Nó produzido:
# ("for", nome_variavel, inicio, direcao, fim, corpo)
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


# =============================================================================
# Variáveis e acessos indexados
# =============================================================================

# Nó produzido:
# ("var", nome)
def p_variable_id(p):
    """
    variable : ID
    """
    p[0] = ("var", p[1])


# O índice pode ser qualquer expressão sintaticamente válida.
#
# Nó produzido:
# ("array_access", nome, indice)
#
# Apesar do nome, este nó também é posteriormente utilizado para a leitura
# indexada de strings.
def p_variable_array_access(p):
    """
    variable : ID LBRACKET expression RBRACKET
    """
    p[0] = ("array_access", p[1], p[3])


# =============================================================================
# Expressões
# =============================================================================

# Literais.
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


# Uma variável ou acesso indexado pode ser utilizado como expressão.
def p_expression_variable(p):
    """
    expression : variable
    """
    p[0] = p[1]


# Nó produzido:
# ("call", nome, lista_de_argumentos)
def p_expression_call_with_args(p):
    """
    expression : ID LPAREN expression_list RPAREN
    """
    p[0] = ("call", p[1], p[3])


def p_expression_call_without_args(p):
    """
    expression : ID LPAREN RPAREN
    """
    p[0] = ("call", p[1], [])


# Os parênteses alteram a associação durante o parsing, mas não necessitam de
# um nó próprio: a estrutura resultante da AST já preserva essa associação.
def p_expression_group(p):
    """
    expression : LPAREN expression RPAREN
    """
    p[0] = p[2]


# UMINUS atribui ao menos unário uma precedência diferente da subtração.
#
# Nó produzido:
# ("unop", "-", operando)
def p_expression_unary_minus(p):
    """
    expression : MINUS expression %prec UMINUS
    """
    p[0] = ("unop", "-", p[2])


# Nó produzido:
# ("unop", "not", operando)
def p_expression_not(p):
    """
    expression : NOT expression
    """
    p[0] = ("unop", "not", p[2])


# Todos os operadores binários partilham a mesma representação:
#
# ("binop", operador, operando_esquerdo, operando_direito)
#
# A precedência e a associatividade são determinadas pela tabela declarada no
# início do módulo.
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


# =============================================================================
# Produções auxiliares e tratamento de erros
# =============================================================================

# Produção vazia reutilizada nas estruturas opcionais da gramática.
def p_empty(p):
    """
    empty :
    """
    p[0] = None


# O parser segue uma estratégia fail-fast: interrompe a análise no primeiro
# token inesperado ou quando o ficheiro termina antes de completar o programa.
def p_error(p):
    if p:
        raise SyntaxError(
            f"Erro sintático perto de '{p.value}' na linha {p.lineno}"
        )

    raise SyntaxError("Erro sintático: fim inesperado do ficheiro")


# =============================================================================
# Construção e interface pública do parser
# =============================================================================

# O PLY inspeciona ``tokens``, ``precedence`` e as funções ``p_*`` para gerar
# as tabelas e os estados do parser LALR.
parser = yacc.yacc()


def parse(source_code):
    """
    Analisa código-fonte Pascal e constrói a respetiva AST.

    O contador de linhas do lexer é reiniciado em cada execução e o objeto
    lexical é fornecido explicitamente ao parser.

    Args:
        source_code: Código-fonte Pascal a analisar.

    Returns:
        AST do programa, representada através de tuplos e listas.

    Raises:
        SyntaxError: Se o programa não respeitar a gramática suportada.
    """
    lexer.lineno = 1
    return parser.parse(source_code, lexer=lexer)


# =============================================================================
# Execução independente
# =============================================================================

# Permite testar o parser sem executar as fases semântica e de geração de
# código:
#
#     python src/parser.py examples/fatorial.pas
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python src/parser.py <ficheiro.pas>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        source = f.read()

    ast = parse(source)
    pprint(ast)