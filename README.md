# Compilador Pascal para EWVM

Projeto académico de Processamento de Linguagens que compila um subconjunto de
Pascal para código da máquina virtual EWVM. Não pretende implementar Pascal
Standard completo.

## Pipeline

O compilador segue as etapas `Pascal -> lexer -> parser -> AST -> análise
semântica -> geração de código -> EWVM`:

- `src/lexer.py`: análise lexical com PLY;
- `src/parser.py`: gramática e construção da AST com PLY;
- `src/semantic.py`: tabela de símbolos e validação de tipos;
- `src/codegen.py`: layout global e geração de instruções EWVM;
- `compiler.py`: interface de linha de comandos.

## Funcionalidades suportadas

- tipos escalares `integer`, `boolean` e `string`;
- declarações e atribuições;
- expressões aritméticas, relacionais e booleanas;
- `if`/`else`, `while`, `for to` e `for downto`;
- `readln` e `writeln`;
- arrays unidimensionais estáticos de `integer`;
- funções de topo com parâmetros por valor e retorno por atribuição ao nome;
- parâmetros e variáveis locais escalares, com resolução local/global;
- função built-in `length` para strings;
- indexação de strings para leitura com `CHARAT`;
- comentários `{ ... }`, `(* ... *)` e `// ...`.

Os arrays usam a forma `array[limite_inferior..limite_superior] of integer`.
Os limites são literais inteiros, podem começar num valor diferente de zero e
o limite inferior tem de ser menor ou igual ao superior. Cada array ocupa uma
posição global com o endereço base de um bloco alocado por `ALLOCN`. Acesso,
atribuição e `readln` de elementos usam `LOADN` e `STOREN`.

## Instalação

Requer Python 3 e PLY 3.11:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Compilação

Mostrar o código EWVM no terminal:

```sh
.venv/bin/python compiler.py examples/hello.pas
```

Guardar o resultado num ficheiro:

```sh
.venv/bin/python compiler.py examples/soma_array.pas -o soma_array.vm
```

Modos de diagnóstico para inspecionar as fases do compilador:

```sh
.venv/bin/python compiler.py --tokens examples/fatorial.pas
.venv/bin/python compiler.py --ast examples/fatorial.pas
.venv/bin/python compiler.py --symbols examples/fatorial.pas
```

## Testes

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Exemplos

- `examples/hello.pas`: escrita simples;
- `examples/fatorial.pas`: leitura, expressões e ciclo `for`;
- `examples/numero_primo.pas`: booleanos, `while`, `if`/`else`, `div`, `mod` e `and`;
- `examples/soma_array.pas`: alocação, leitura e soma de elementos de um array;
- `examples/binario_para_inteiro.pas`: funções, `length` e indexação de strings;
- `examples/erro_semantico.pas`: utilização intencional de variável não declarada.

O relatório de implementação está em
[docs/technical_report.md](docs/technical_report.md).

## Limitações

- arrays são unidimensionais e têm tamanho estático;
- apenas arrays de `integer` estão garantidos;
- índices literais são verificados estaticamente, mas não existe verificação
  dinâmica de limites para índices calculados;
- o tipo `real` não está implementado;
- funções aninhadas, `procedure`, parâmetros por referência, arrays locais e
  arrays como parâmetros não estão implementados;
- a indexação de strings é apenas para leitura; atribuição e `readln` de um
  carácter indexado não são suportados;
- não existem arrays multidimensionais nem otimizações.

Internamente, um acesso como `texto[i]` tem o tipo semântico `char`, que não é
um tipo Pascal declarável. Como Pascal usa índices base 1 neste subconjunto e
`CHARAT` usa base zero, o compilador subtrai 1 ao índice. Comparações com
literais de um carácter usam `CHRCODE` para comparar os códigos ASCII.
