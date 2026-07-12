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

## Testes

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Exemplos

- `examples/hello.pas`: escrita simples;
- `examples/fatorial.pas`: leitura, expressões e ciclo `for`;
- `examples/numero_primo.pas`: booleanos, `while`, `if`/`else`, `div`, `mod` e `and`;
- `examples/soma_array.pas`: alocação, leitura e soma de elementos de um array;
- `examples/erro_semantico.pas`: utilização intencional de variável não declarada.

## Limitações

- arrays são unidimensionais e têm tamanho estático;
- apenas arrays de `integer` estão garantidos;
- índices literais são verificados estaticamente, mas não existe verificação
  dinâmica de limites para índices calculados;
- o tipo `real` não está implementado;
- `function` e `procedure` ainda não estão implementadas;
- não existem arrays multidimensionais nem otimizações.
