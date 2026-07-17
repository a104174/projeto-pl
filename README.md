# Compilador de Pascal para EWVM

Componente prática da unidade curricular de **Processamento de Linguagens**.
O projeto implementa, em Python e com recurso ao PLY, um compilador de um
subconjunto de Pascal para código da máquina virtual EWVM fornecida pelos docentes da cadeira.

## Funcionamento

O processo de compilação inclui as principais fases estudadas na unidade
curricular:

```text
Pascal → análise lexical → análise sintática → AST
       → análise semântica → código EWVM
```

- `src/lexer.py` — análise lexical;
- `src/parser.py` — análise sintática e construção da AST;
- `src/semantic.py` — tabela de símbolos e validação semântica;
- `src/codegen.py` — geração de código EWVM;
- `compiler.py` — interface de linha de comandos.

## Subconjunto suportado

- tipos `integer`, `boolean` e `string`;
- declarações, atribuições e expressões;
- estruturas `if`/`else`, `while`, `for to` e `for downto`;
- entrada e saída com `readln` e `writeln`;
- arrays estáticos unidimensionais de inteiros;
- funções com parâmetros por valor e variáveis locais;
- `length` e indexação de strings para leitura;
- comentários nos formatos `{ ... }`, `(* ... *)` e `// ...`.

Não são suportados, entre outros, o tipo `real`, procedimentos, funções
aninhadas, parâmetros por referência, arrays multidimensionais ou otimizações.

## Instalação

Requer Python 3.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Utilização

Compilar para o terminal:

```sh
.venv/bin/python compiler.py examples/hello.pas
```

Guardar o código gerado:

```sh
.venv/bin/python compiler.py examples/soma_array.pas -o soma_array.vm
```

As opções `--tokens`, `--ast` e `--symbols` permitem consultar os resultados
intermédios das diferentes fases.

## Testes

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Os programas de demonstração encontram-se em `examples/` e alguns resultados
gerados em `generated/`. A descrição técnica detalhada está disponível no
[relatório do projeto](docs/relatorio.md).
