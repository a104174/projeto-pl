# Compilador de Pascal para EWVM

# Universidade do Minho - Licenciatura em Engenharia Informática

# Processamento de Linguagens

# Hélder Tiago Peixoto da Cruz - a104174

# 16/07/2026



## Relatório Técnico

## 1. Introdução

O presente projeto implementa um compilador para um subconjunto da linguagem Pascal, tendo como linguagem-alvo a máquina virtual EWVM fornecida pelos docentes da cadeira. O objetivo principal foi concretizar as etapas fundamentais de um compilador — análise lexical, análise sintática, análise semântica e geração de código — mantendo uma separação clara entre responsabilidades e permitindo observar os resultados intermédios de cada fase.

A implementação não pretende cobrir integralmente o Standard Pascal. Foi definido um subconjunto suficientemente expressivo para suportar declarações, expressões, entrada e saída, estruturas de controlo, arrays estáticos e funções. A tradução para EWVM é realizada diretamente a partir da árvore de sintaxe abstrata, sem uma linguagem intermédia adicional.

## 2. Objetivos e âmbito

O compilador suporta as seguintes construções:

- tipos escalares `integer`, `boolean` e `string`;
- declarações de variáveis globais;
- atribuições e expressões aritméticas, relacionais e booleanas;
- leitura com `readln` e escrita com `writeln`;
- condicionais `if/else`;
- ciclos `while`, `for to` e `for downto`;
- arrays globais, unidimensionais, estáticos e de elementos `integer`;
- funções de topo com parâmetros por valor, variáveis locais escalares e retorno escalar;
- função incorporada `length` para strings;
- indexação de strings para leitura.

Não são suportados procedimentos, funções aninhadas, parâmetros por referência, arrays multidimensionais, arrays locais, arrays como parâmetros ou valores de retorno, tipos `real` e otimizações formais.

## 3. Organização do projeto

A implementação encontra-se organizada em módulos correspondentes às fases do compilador:

```text
compiler.py
src/
├── lexer.py
├── parser.py
├── semantic.py
└── codegen.py
```

O fluxo principal é:

```text
Código Pascal
    ↓
Análise lexical
    ↓
Sequência de tokens
    ↓
Análise sintática
    ↓
AST
    ↓
Análise semântica e tabela de símbolos
    ↓
Geração direta de código EWVM
```

O ficheiro `compiler.py` coordena estas fases e disponibiliza uma interface de linha de comandos. Para além da compilação normal, permite consultar os tokens, a AST e a tabela de símbolos através das opções `--tokens`, `--ast` e `--symbols`.

## 4. Análise lexical

A análise lexical foi implementada com `ply.lex`. O módulo identifica palavras reservadas, identificadores, números inteiros, literais string, operadores e delimitadores.

### 4.1. Normalização de identificadores

Pascal não distingue maiúsculas de minúsculas. Por esse motivo, identificadores e palavras reservadas são normalizados para minúsculas no lexer. Esta decisão centraliza o tratamento de *case-insensitivity* numa única fase e simplifica todas as comparações posteriores na tabela de símbolos.

Assim, nomes como:

```pascal
Resultado
resultado
RESULTADO
```

são tratados como o mesmo identificador.

### 4.2. Strings e comentários

Os literais string utilizam aspas simples. A sequência `''` dentro de uma string é convertida numa aspa simples, seguindo a convenção de Pascal.

São reconhecidos três formatos de comentário:

```pascal
{ comentário }
(* comentário *)
// comentário até ao fim da linha
```

Os comentários são descartados, mas as mudanças de linha no seu interior são contabilizadas para manter diagnósticos corretos.

### 4.3. Estratégia de erro lexical

O lexer segue uma estratégia *fail-fast*: ao encontrar um carácter inválido, interrompe a análise e lança uma exceção. A alternativa seria ignorar o carácter e acumular vários erros, mas essa abordagem exigiria uma política de recuperação mais complexa e poderia produzir tokens pouco fiáveis para o parser.

Para o âmbito do projeto, privilegiou-se um comportamento simples e determinístico: uma entrada lexicalmente inválida não é enviada às fases seguintes.

## 5. Análise sintática

O parser foi implementado com `ply.yacc`, que constrói um parser LALR a partir das produções declaradas nas funções `p_*`.

A gramática adotada organiza um programa da seguinte forma:

```text
programa
├── funções de topo
├── declarações globais
└── bloco principal
```

As produções reconhecem declarações, blocos, comandos e expressões. As ações associadas a essas produções constroem diretamente uma árvore de sintaxe abstrata.

### 5.1. Precedência e associatividade

Foi definida uma tabela de precedência para resolver expressões sem introduzir vários níveis adicionais de não terminais. A prioridade, da menor para a maior, é:

```text
OR
AND
NOT
comparações
+ e -
*, /, div e mod
menos unário
```

Os operadores aritméticos são associativos à esquerda. As comparações são não associativas, impedindo construções como:

```pascal
a < b < c
```

O marcador interno `UMINUS` distingue o menos unário da subtração binária. Do mesmo modo, `IFX` é utilizado para resolver o problema do *dangling else*, associando cada `else` ao `if` incompleto mais próximo.

### 5.2. Construção de listas

Listas de declarações, parâmetros, comandos e expressões são construídas por recursão à esquerda. Esta forma seria problemática num parser descendente recursivo manual, mas é adequada a um parser LALR.

As produções opcionais devolvem listas vazias em vez de `None`. Desta forma, as fases seguintes podem percorrer uniformemente uma estrutura, independentemente de ela conter zero ou vários elementos.

## 6. Representação da AST

A AST é representada por tuplos e listas Python. O primeiro elemento de cada tuplo identifica o tipo do nó.

Exemplos:

```python
("program", nome, globais, funcoes, bloco)
("var_decl", nomes, tipo)
("assign", destino, expressao)
("if", condicao, ramo_then, ramo_else)
("while", condicao, corpo)
("for", variavel, inicio, direcao, fim, corpo)
("call", nome, argumentos)
("binop", operador, esquerda, direita)
```

### 6.1. Justificação da representação

Foi escolhida uma representação leve, em vez de uma hierarquia de classes para cada tipo de nó. Esta decisão apresenta três vantagens no contexto do projeto:

1. permite construir os nós diretamente nas ações do PLY;
2. reduz o número de classes auxiliares e código repetitivo;
3. torna a AST fácil de imprimir e inspecionar através da opção `--ast`.

A principal desvantagem é a dependência de posições nos tuplos. Para reduzir esse risco, todos os nós seguem formatos consistentes, identificados por uma etiqueta textual, e são cobertos pelos testes automáticos.

### 6.2. AST como representação intermédia

Não foi introduzida uma linguagem intermédia adicional. A própria AST desempenha o papel de representação intermédia entre o parser, a análise semântica e o gerador de código.

A geração direta foi escolhida porque as construções suportadas possuem uma correspondência relativamente simples com instruções EWVM. Uma IR adicional aumentaria a complexidade sem trazer benefícios proporcionais para o âmbito atual. Como contrapartida, esta opção limita oportunidades de otimização e torna o backend mais dependente da forma da AST.

## 7. Análise semântica

A análise semântica recebe uma AST sintaticamente válida, constrói a tabela de símbolos e verifica propriedades que não podem ser garantidas pela gramática.

Entre as validações realizadas encontram-se:

- declarações repetidas;
- utilização de variáveis e funções não declaradas;
- conflitos entre identificadores;
- compatibilidade de tipos em atribuições;
- tipos dos operandos;
- tipo das condições de `if` e `while`;
- validade da variável de controlo e dos limites de `for`;
- aridade e tipos dos argumentos de funções;
- validade dos índices;
- existência de uma atribuição ao resultado de cada função.

Ao contrário do lexer e do parser, a análise semântica acumula erros numa lista. Depois de a estrutura sintática estar validada, várias verificações semânticas podem ser efetuadas de forma independente, permitindo apresentar mais do que um diagnóstico numa única compilação.

## 8. Tabela de símbolos e âmbitos

A tabela de símbolos é baseada em dicionários Python. Os símbolos globais são armazenados diretamente na tabela principal e as funções são mantidas num catálogo separado.

Cada entrada de variável contém informação como:

```text
kind
type
offset
```

No caso de arrays, inclui ainda:

```text
start
end
size
```

Cada função guarda:

- tipo de retorno;
- lista de parâmetros;
- variáveis locais;
- corpo;
- âmbito local;
- posição do retorno no frame;
- label EWVM;
- indicação de atribuição ao resultado.

### 8.1. Construção em várias passagens

Primeiro são registadas as variáveis globais e as assinaturas de todas as funções. Só depois são preparados os âmbitos locais e verificados os corpos.

Esta ordem permite validar chamadas com base num catálogo completo de funções e separa a introdução de símbolos da análise das suas utilizações.

### 8.2. Resolução de nomes

Dentro de uma função, a resolução procura primeiro no âmbito local e depois no âmbito global:

```text
parâmetros e locais
        ↓
variáveis globais
```

Isto permite que uma variável local oculte uma variável global com o mesmo nome. Contudo, são rejeitados conflitos entre parâmetros e locais da mesma função, bem como conflitos com o nome da própria função ou com a função incorporada `length`.

## 9. Funções

As funções suportadas são declaradas ao nível superior e recebem parâmetros escalares por valor. Os seus valores de retorno também são escalares.

### 9.1. Retorno através do nome da função

Foi mantida a convenção tradicional de Pascal, na qual o valor devolvido é definido por uma atribuição ao nome da própria função:

```pascal
function Dobro(x: integer): integer;
begin
    Dobro := x * 2
end;
```

O parser representa esta construção como uma atribuição normal:

```python
("assign", ("var", "dobro"), expressao)
```

A distinção é feita semanticamente através do contexto. Se a atribuição ocorrer dentro da função com o mesmo nome, o destino corresponde ao espaço reservado para o retorno.

Esta opção preserva a sintaxe de Pascal e evita introduzir artificialmente um comando `return` que não existe no subconjunto implementado.

A função continua a poder ser chamada normalmente:

```pascal
resultado := Dobro(5);
```

Os parênteses permitem distinguir a chamada da atribuição ao resultado.

### 9.2. Verificação do retorno

A análise semântica confirma que cada função contém pelo menos uma atribuição ao próprio nome. Não é realizada análise de fluxo de controlo para provar que todos os caminhos possíveis atribuem um resultado.

Por exemplo, uma atribuição presente apenas num ramo de um `if` satisfaz a verificação atual, mesmo que outro caminho termine sem definir o retorno. Esta limitação é assumida e identificada como possível trabalho futuro.

### 9.3. Parâmetros e arrays

Os parâmetros foram limitados a tipos simples. Não são aceites arrays como parâmetros nem como valores de retorno.

A passagem de arrays exigiria definir uma convenção adicional: cópia por valor, passagem de endereço ou passagem por referência. Também seria necessário garantir a representação correta do array e o seu tempo de vida. Para manter um modelo de chamadas claro e compatível com os frames utilizados, optou-se por parâmetros escalares.

## 10. Arrays

São suportados arrays globais, unidimensionais, estáticos e de elementos `integer`:

```pascal
valores: array[1..5] of integer;
```

Os limites inferior e superior são conhecidos durante a compilação. O tamanho é calculado por:

```text
tamanho = limite_superior - limite_inferior + 1
```

### 10.1. Limites arbitrários

Os arrays não são obrigados a começar no índice zero ou um. Para traduzir um índice Pascal para o deslocamento interno do bloco, o gerador calcula:

```text
deslocamento = índice - limite_inferior
```

Depois utiliza `LOADN` para leitura e `STOREN` para escrita.

### 10.2. Representação em memória

Cada array global ocupa uma posição na zona global. Essa posição não contém diretamente os elementos, mas o endereço base de um bloco criado pela EWVM:

```text
PUSHI tamanho
ALLOCN
STOREG posição_global
```

Esta representação permite que o layout global permaneça uniforme: tanto escalares como referências para arrays ocupam uma posição global.

### 10.3. Restrições adotadas

O parser reconhece arrays de tipos simples e declarações locais de arrays, mas a análise semântica restringe o suporte efetivo a arrays globais de inteiros.

Arrays locais exigiriam integrar a respetiva alocação e gestão no frame de cada chamada. Como o gerador atual reserva diretamente apenas valores escalares locais, esta funcionalidade foi excluída para evitar uma implementação incompleta ou uma gestão incorreta da memória.

A verificação estática de limites é realizada apenas quando o índice é um literal inteiro. Índices calculados em tempo de execução não possuem verificação dinâmica.

## 11. Strings e tipo interno `char`

As strings são representadas diretamente pelos valores suportados pela EWVM. A função incorporada:

```pascal
length(texto)
```

é reconhecida semanticamente e traduzida para:

```text
STRLEN
```

`length` não foi transformada numa palavra reservada do lexer. Mantê-la como identificador permite usar a mesma estrutura de chamada das funções normais e produzir diagnósticos explícitos quando existe uma tentativa de redefinição.

### 11.1. Indexação de strings

A expressão:

```pascal
texto[i]
```

reutiliza o mesmo nó sintático de acesso indexado usado pelos arrays. A análise semântica consulta o tipo do símbolo para distinguir os dois casos.

A EWVM utiliza `CHARAT` com índices de base zero, enquanto a indexação de strings no subconjunto Pascal é tratada como base um. Por isso, o gerador emite:

```text
índice
PUSHI 1
SUB
CHARAT
```

A indexação de strings é suportada apenas para leitura. Atribuir ou executar `readln` sobre `texto[i]` é rejeitado semanticamente.

### 11.2. Tipo interno `char`

`CHARAT` devolve o código de um carácter. Para representar esse resultado durante a análise semântica foi introduzido o tipo interno `char`.

Este tipo não pode ser declarado pelo programador e não faz parte da gramática. Existe apenas para validar operações internas resultantes da indexação de strings.

Um `char` pode ser comparado com:

- outro `char`;
- um literal string com exatamente um carácter.

Quando é comparado com um literal de um carácter, o gerador utiliza `CHRCODE` para converter explicitamente esse literal no código correspondente.

Esta solução evita considerar todas as strings compatíveis com caracteres e mantém as conversões explícitas no código gerado.

## 12. Geração de código EWVM

O gerador percorre recursivamente a AST e emite instruções EWVM numa lista. No final, as instruções são unidas numa única string.

A geração só é iniciada depois de `check_program` confirmar que não existem erros semânticos. Desta forma, o codegen pode assumir que nomes, tipos e chamadas já foram validados.

### 12.1. Layout global

Cada símbolo global recebe um `offset` sequencial. Antes de `START`, é colocado na pilha um valor inicial para cada posição global:

```text
PUSHI 0       ; integer, boolean ou referência
PUSHS ""      ; string
```

Depois de `START`, os blocos dos arrays são alocados e os respetivos endereços são guardados nas posições globais.

### 12.2. Expressões

Os literais são traduzidos diretamente:

```text
integer  → PUSHI
string   → PUSHS
boolean  → PUSHI 0 ou PUSHI 1
```

Variáveis globais usam `PUSHG` e variáveis locais ou parâmetros usam `PUSHL`.

Os operadores binários são traduzidos para instruções como:

```text
ADD, SUB, MUL, DIV, MOD
EQUAL, INF, INFEQ, SUP, SUPEQ
AND, OR
```

O operador `<>` é implementado como `EQUAL` seguido de `NOT`.

O menos unário é traduzido como a subtração do operando a zero:

```text
PUSHI 0
<operando>
SUB
```

### 12.3. Estruturas de controlo

As estruturas de controlo utilizam labels geradas por um contador global.

Um `if` é traduzido através de `JZ` para o ramo alternativo e `JUMP` para o fim. Um `while` contém uma label de início, avaliação da condição, salto para o fim e regresso ao início.

No `for`, o valor inicial é guardado na variável de controlo. Em cada iteração:

1. compara-se a variável com o limite;
2. executa-se o corpo;
3. incrementa-se ou decrementa-se a variável;
4. regressa-se à condição.

Para `to` é utilizada uma comparação `INFEQ`; para `downto`, `SUPEQ`.

## 13. Modelo de chamadas e frames

A implementação das funções segue um modelo de frames compatível com a EWVM.

Para uma função com `n` parâmetros:

```text
parâmetro 1 → índice -1
parâmetro 2 → índice -2
...
parâmetro n → índice -n
retorno     → índice -(n+1)
locais      → índices 0, 1, 2, ...
```

Os símbolos globais usam instruções `PUSHG` e `STOREG`. Parâmetros, locais e retorno usam `PUSHL` e `STOREL`.

### 13.1. Chamada de uma função

O chamador:

1. reserva uma posição para o retorno;
2. coloca os argumentos;
3. coloca o endereço da função;
4. executa `CALL`;
5. remove os argumentos com `POP`.

Exemplo conceptual para uma função com um argumento inteiro:

```text
PUSHI 0
<argumento>
PUSHA FUNC1
CALL
POP 1
```

O valor de retorno permanece na pilha e pode ser usado pela expressão envolvente.

Para funções que devolvem strings, a reserva inicial é feita com:

```text
PUSHS ""
```

### 13.2. Variáveis locais

No início do código de cada função são colocados os valores iniciais das variáveis locais. Como apenas são permitidos locais escalares, cada local ocupa uma única posição no frame.

A função termina com `RETURN`. A atribuição ao nome da função escreve na posição negativa reservada ao resultado, mas não termina imediatamente a execução do corpo.

### 13.3. Labels de funções

Cada função recebe uma label sequencial alfanumérica:

```text
FUNC1
FUNC2
...
```

Inicialmente seria possível derivar a label diretamente do nome Pascal. Contudo, essa solução poderia introduzir caracteres rejeitados pela EWVM, como `_`, e criar colisões ao sanitizar nomes diferentes.

A utilização de um contador garante:

- compatibilidade com a sintaxe de labels da EWVM;
- unicidade;
- independência relativamente ao nome escrito no programa;
- utilização consistente da mesma label na declaração e nas chamadas.

As funções são emitidas depois de `STOP`, impedindo que a execução principal entre acidentalmente nos seus corpos.

## 14. Tratamento de erros

A estratégia varia consoante a fase:

| Fase | Estratégia | Justificação |
|---|---|---|
| Lexer | Interrompe no primeiro erro | Evita produzir uma sequência de tokens inválida |
| Parser | Interrompe no primeiro erro | Não existe uma AST estruturalmente segura para as fases seguintes |
| Semântica | Acumula vários erros | A AST já é válida e permite verificações independentes |
| Codegen | Lança `CodeGenerationError` | A geração não deve continuar perante uma construção inválida |

O compilador devolve um código de saída diferente de zero quando ocorre um erro e não cria um ficheiro EWVM válido para programas semanticamente incorretos.

## 15. Decisões principais de implementação

| Decisão | Motivação | Consequência |
|---|---|---|
| Normalizar identificadores no lexer | Pascal é *case-insensitive* | Comparações e pesquisas mais simples nas fases seguintes |
| AST em tuplos e listas | Integração direta com ações PLY e menor complexidade estrutural | Menor segurança estática do que uma hierarquia de classes |
| Parser LALR com PLY | Suporte natural para recursão à esquerda, precedência e gramáticas mais expressivas | Dependência das convenções e tabelas geradas pelo PLY |
| Geração direta AST → EWVM | O subconjunto tem tradução direta e controlável | Não existe uma camada própria para otimizações |
| Semântica em várias passagens | Todas as funções ficam registadas antes da verificação dos corpos | Estrutura mais previsível para resolução e validação |
| Retorno pelo nome da função | Preserva a semântica tradicional de Pascal | O contexto deve distinguir retorno de variável normal |
| Parâmetros apenas escalares | Simplifica o frame e evita definir passagem de arrays | Menor cobertura da linguagem |
| Arrays apenas globais e inteiros | Modelo de memória claro com `ALLOCN`, `LOADN` e `STOREN` | Arrays locais e de outros tipos são rejeitados |
| `length` tratada semanticamente | Reutiliza a sintaxe normal de chamadas | É necessário proteger o nome contra redefinições |
| Tipo interno `char` | Permite validar o resultado de `CHARAT` | O tipo existe apenas internamente |
| Labels sequenciais | Evita caracteres inválidos e colisões | As labels não preservam o nome original da função |
| Erros semânticos acumulados | Produz diagnósticos mais úteis numa só compilação | A análise tem de tolerar símbolos parcialmente inválidos |

## 16. Testes e validação

A implementação é acompanhada por uma suite baseada em `unittest`, cobrindo:

- tokenização;
- construção da AST;
- precedência;
- declarações e tipos;
- erros semânticos;
- âmbitos e tabela de símbolos;
- arrays;
- funções, parâmetros, locais e retorno;
- strings, `length`, `CHARAT` e `CHRCODE`;
- geração de instruções EWVM;
- interface de linha de comandos;
- casos de regressão.

A execução final produziu:

```text
Ran 70 tests in 0.168s

OK
```

### 16.1. Validação na EWVM real

Para além dos testes automáticos, o código gerado foi executado na EWVM real.

| Programa | Entrada | Resultado |
|---|---:|---|
| `hello.pas` | — | `Ola, Mundo!` |
| `fatorial.pas` | `5` | `Fatorial de 5: 120` |
| `numero_primo.pas` | `7` | Número primo |
| `numero_primo.pas` | `8` | Número não primo |
| `soma_array.pas` | `1, 2, 3, 4, 5` | Soma igual a `15` |
| `binario_para_inteiro.pas` | `1011` | Valor inteiro `11` |
| `binario_para_inteiro.pas` | `0` | Valor inteiro `0` |

O exemplo `binario_para_inteiro.pas` é particularmente relevante porque combina funções, parâmetros, variáveis locais, `length`, indexação de strings, `downto`, `CHARAT`, `CHRCODE` e retorno.

Foi também validado um programa semanticamente incorreto:

```text
Erro de compilação: Erros semânticos:
- Variável 'x' usada sem declaração
exit_code=1
```

Nesse caso, não foi criado um ficheiro de saída EWVM.

A interface da EWVM apresenta por vezes operações sucessivas de escrita em linhas visuais separadas. A inspeção do código gerado confirmou que cada `writeln` emite `WRITES` ou `WRITEI` para os argumentos e apenas um `WRITELN` no final.

## 17. Considerações de eficiência

A tabela de símbolos utiliza dicionários, permitindo pesquisas com custo médio constante. A maior parte das fases percorre linearmente as listas de tokens, os nós da AST ou as declarações.

A geração de labels e offsets é feita através de contadores sequenciais. Não existem passagens de otimização nem transformação para uma IR adicional, pelo que o custo de compilação permanece proporcional à dimensão do programa e da AST, salvo as pesquisas e validações associadas.

O código gerado privilegia clareza e correção. Por exemplo, a expressão final de um `for` é novamente gerada na verificação de cada iteração, em vez de ser necessariamente guardada numa posição temporária.

## 18. Utilização

Criação do ambiente e instalação das dependências:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Compilação para o terminal:

```bash
.venv/bin/python compiler.py examples/hello.pas
```

Geração de um ficheiro EWVM:

```bash
.venv/bin/python compiler.py examples/fatorial.pas -o generated/fatorial.vm
```

Modos de diagnóstico:

```bash
.venv/bin/python compiler.py examples/fatorial.pas --tokens
.venv/bin/python compiler.py examples/fatorial.pas --ast
.venv/bin/python compiler.py examples/fatorial.pas --symbols
```

Execução dos testes:

```bash
.venv/bin/python -m unittest discover -s tests -v
```


## 19. Conclusão

O projeto concretiza um compilador funcional para um subconjunto relevante de Pascal, desde a tokenização até à execução do código gerado na EWVM. A arquitetura modular separa claramente as responsabilidades de cada fase e disponibiliza mecanismos de diagnóstico úteis para compreender o processo de compilação.

As decisões adotadas privilegiaram simplicidade, rastreabilidade e correção: normalização lexical, AST leve, validação semântica centralizada, frames de funções explícitos, arrays estáticos e geração direta de EWVM.

A suite de 70 testes e a execução dos exemplos na EWVM real confirmam o funcionamento das principais funcionalidades implementadas. Embora existam limitações assumidas, a estrutura atual fornece uma base coerente para extensões futuras.
