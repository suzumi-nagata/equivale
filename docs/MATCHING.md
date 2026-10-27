# Modelo de matching: de 1-para-1 para m-para-n

## Estado atual

Há duas implementações complementares:

- **PoC Python** (`prototype/match_curricula.py`): atribuição ótima
  **1-para-1** (algoritmo húngaro), usada como limite inferior e para validar o
  parser. Cada disciplina de origem ocupa no máximo um slot; cada slot recebe no
  máximo uma origem.
- **Site** (`site/src/lib/match.ts`): **max-cost flow** m-para-n. Cada origem tem
  capacidade de horas, cada slot-alvo tem demanda, e o fluxo divide/combina
  origens e slots. É a implementação usada em produção no site.

O PoC 1-para-1 continua deliberadamente conservador; o site implementa a
relação real m-para-n descrita abaixo.

### Max-cost flow no site

O grafo é:

- nó-fonte → nó de cada disciplina de origem, com capacidade = horas da
  disciplina;
- origem → slot, com capacidade = `min(horas_origem, horas_slot)` e valor por
  hora = `score_do_par + 0.01`;
- slot → nó-sumidouro, com capacidade = horas do slot.

O algoritmo augmenta por caminhos de custo negativo no grafo residual
(SPFA/sucessivos caminhos mais curtos). O `+0.01` faz com que, empatado o score,
o fluxo prefira aproveitar mais horas. Ele para quando não há caminho com valor
positivo — não força um pareamento ruim só para preencher o slot.

Slots fixos aceitam alocações parciais a partir de 20h (ou da carga total, se o
slot for menor). Grupos de eletivas aceitam qualquer fração, porque o requisito
é a soma de créditos. Grupos marcados como `livre` aceitam qualquer disciplina
elegível da origem, com score fixo 0.6 e confiança baixa; a regra efetiva da IES
pode ser mais restrita.

### Política de carga horária e escopo

- O padrão é conservador: a origem só fornece até a própria carga horária.
- O modo opcional `ignoreWorkload` remove esse limite: a capacidade da origem
  sobe até a carga do maior slot que ela pode cobrir, e o par é pontuado sem o
  fator de aderência de carga. Com isso, uma disciplina de 30h pode cobrir um
  componente de 90h. A UI expõe isso como “Ignorar diferença de carga horária”
  e o resultado inclui um aviso; é uma estimativa permissiva, não a regra
  oficial.
- Regras de ementa têm `origem_instituicao`; elas só são aplicadas quando o
  histórico importado é da mesma instituição. Isso evita que uma regra da
  UNICAMP case por nome com uma disciplina da USP.
- Guardas gerais de nome: sequência (Cálculo I ≠ Cálculo II; A/B/C também),
  teoria × laboratório e tokens genéricos (não casar “Introdução aos Sistemas de
  Potência” com “Introdução aos Sistemas Embarcados”). Numerais romanos curtos
  (I, II, IV) são preservados na tokenização para que “Física Geral I” case com
  “Física I”.
- Para evitar falsos positivos, o match por tokens exige pelo menos um token
  específico em comum (fora de palavras genéricas como “geral”, “introdução”,
  “laboratório”, “sistemas”); conceitos específicos podem suprir essa exigência.
- No modo sem carga horária, a cobertura integral vale para slots fixos; grupos
  de eletivas continuam limitados pela carga real da origem para não inflar
  optativas livres.

Os testes sintéticos ficam em `site/src/lib/match.test.ts` e cobrem 1→n,
m→1, capacidade, eletiva livre, TCC não abatível, cobertura temática, escopo
institucional e o modo sem carga horária.

### Cobertura temática por ementas (gerada)

Quando o nome da disciplina de origem não coincide com o componente-alvo, o
matcher pode usar regras geradas por `tools/build_unicamp_cobertura.py` e
`tools/build_usp_cobertura.py` em `data/ontology/`. Os scripts extraem as
ementas públicas do catálogo da UNICAMP e do Jupiterweb, calculam TF-IDF e
similaridade de nomes (com guardas de sequência e de laboratório) e gravam as
arestas candidatas; não há exceções de curso digitadas à mão.

Cada regra liga um componente-alvo a uma ou mais origens e declara:

- `horas_cobertura`: capacidade daquela origem para aquele alvo (cobertura
  parcial, não a carga inteira da disciplina);
- `score` e `confianca`;
- `ignorar_carga_horaria`: permite cobertura integral mesmo quando a origem tem
  menos horas (ex.: EM423 45h cobrindo EM424 60h);
- `prioridade`: desempata quando a mesma origem pode cobrir mais de um alvo
  (ex.: EA869 em MC404 vs. EA960);
- `rotulo` e URL da ementa que fundamenta a regra.

Essas arestas entram no mesmo fluxo que as arestas por nome. Uma regra não
substitui um match por nome com score maior. Elas são uma estimativa temática
conservadora e não uma equivalência oficial.

Primeiro conjunto: Física Geral III/IV e Física Experimental III da Engenharia
de Computação da UNICAMP cobertas por disciplinas da Engenharia Elétrica
(EE521, EE300, EA619/EA722 etc.); Resistência dos Materiais e Sistemas
Embarcados com cobertura integral apesar da diferença de carga; e MC404 coberta
por EA869. O caso de Física é m-para-n quando a origem não cobre sozinha. O
matcher também aplica uma guarda de conceito específico: um laboratório de
programação não cobre PAA I, e programação genérica não cobre Computação
Gráfica/Processamento de Imagem sem os conceitos de imagem/gráfica/visão
computacional. Teoria e laboratório também não se misturam: “Laboratório de
Análise Linear” só casa com outra disciplina de laboratório/experimental, e
“Análise Linear de Sistemas” só com teoria.

### Similaridade por vetores de ementa

Além das regras de cobertura, o site baixa `data/embeddings/cursos.json`, gerado
por `tools/build_course_embeddings.py`. Cada disciplina vira um vetor denso de
256 dimensões (TF-IDF de ementa/título + feature hashing com BLAKE2b,
quantizado em int8/base64). O cálculo é offline, determinístico e sem LLM.

No matching, o site procura o vetor do slot-alvo pelo código (ou pelo nome,
quando não há código) e o vetor da origem pelo código/nome. Se ambos existirem:

- calcula o cosseno;
- exige cosseno >= 0.38;
- aplica as mesmas guardas de sequência, teoria × laboratório e conceito
  específico;
- exige um token específico do nome ou um conceito específico compartilhado;
- cria uma aresta `metodo: "vetor"` com score `0.48 + 0.38 × cosseno`, limitada
  pela carga real da origem (o modo “ignorar carga” continua valendo só para
  slots fixos);
- só adiciona pares que ainda não têm aresta de nome/regra; vetores
  complementam, não substituem a cobertura existente.

Os vetores são decodificados sob demanda, não todos na inicialização. Se o
arquivo faltar ou estiver corrompido, o matching continua por nome + regras. A
cobertura por vetor é uma aproximação lexical, não uma equivalência oficial.


## Por que 1-para-1 é insuficiente

Na prática, a relação é **m-para-n**:

- **Uma origem pode cobrir vários alvos.** Uma disciplina ampla (ex.: Física
  III, 60h) pode cobrir tópicos que aparecem em mais de um componente do curso
  alvo (ex.: dois componentes de 30h). Uma disciplina de 90h pode cobrir dois
  slots de 45h.
- **Vários componentes podem cobrir um alvo.** Dois cursos de origem (ex.:
  Cálculo I + Cálculo II) podem, juntos, cobrir um componente alvo de 90h.
- **Conteúdo não é carga horária.** Um curso de 30h pode cobrir integralmente
  um alvo de 45h se o conteúdo for equivalente; outro de 90h pode cobrir apenas
  parte. A carga é uma restrição, não a medida principal.

O resultado 1-para-1 subestima a quantidade abatível — e, pior, pode alocar uma
disciplina no slot errado quando dois slots disputam o mesmo conteúdo.

## Classificação da origem: obrigatória, optativa ou ênfase

O histórico lista disciplinas cursadas, mas não diz se cada uma era:

- obrigatória do currículo;
- optativa restrita;
- optativa livre;
- dependente de ênfase/habilitação/módulo.

Isso importa para a equivalência: uma disciplina optativa pode não ser aceita
da mesma forma que uma obrigatória, e cursos com ênfases diferentes têm grades
diferentes. O modelo precisa de:

- `origem.tipo`: `obrigatoria | optativa_restrita | optativa_livre | enfase | desconhecido`;
- `origem.curriculo_versao` (ano/catálogo) e `origem.habilitacao/enfase`;
- fonte: currículo público da instituição de origem ou marcação manual do
  usuário.

O histórico sozinho não resolve isso. A UI deve permitir revisar e classificar
as disciplinas, e o dataset deve guardar a classificação com proveniência.

## Modelo proposto: fluxo com capacidade

### Nós e arestas

- **Origem** `i`: capacidade `cap_i` = horas da disciplina (ou 1 unidade, se a
  regra da IES for “cada disciplina só pode ser usada uma vez”).
- **Alvo** `j`: demanda `dem_j` = horas do componente.
- **Aresta** `i → j`: existe se o conteúdo da origem cobre parte do alvo.
  - `score_ij` = cobertura de tópicos (containment), similaridade de nome e
    aderência de carga;
  - capacidade da aresta = `min(cap_i, dem_j)`;
  - custo/lucro = `score_ij` por hora alocada.
- **Fluxo** `f_ij` = horas da origem `i` alocadas ao alvo `j`.

### Objetivo

Maximizar `Σ score_ij × f_ij` sujeito a:

- `Σ_j f_ij ≤ cap_i` (a origem não fornece mais horas do que tem);
- `Σ_i f_ij ≤ dem_j` (o alvo não recebe mais horas do que exige);
- `f_ij ≥ 0`;
- restrições institucionais:
  - máximo de aproveitamento (% do currículo alvo);
  - uma disciplina de origem usada no máximo uma vez (se a IES exigir 1-para-1
    administrativo);
  - nota mínima, validade temporal, tipo de optativa;
  - pré-requisitos e oferta;
  - teto por instituição de origem.

É um problema de **max-cost flow** (ou min-cost flow com custos negativos).
Grafos pequenos (centenas de disciplinas) rodam em Web Worker sem problema.

### Saída

- Horas alocadas por par origem→alvo.
- Componentes cobertos, parcialmente cobertos e descobertos.
- Agrupamento das alocações em **propostas de equivalência** para o dossiê:
  - “Física III cobre Física C (30h) + Física D (30h)”;
  - “Cálculo I + Cálculo II cobrem Cálculo A (90h)”.
- Confiança por alocação; o dossiê deve dizer que a decisão é da IES.

## Exemplos sintéticos

**Uma origem → vários alvos**

```text
Origem: Física III (60h) — tópicos: eletromagnetismo, ondas
Alvo A: Física C (30h) — eletromagnetismo
Alvo B: Física D (30h) — ondas
Fluxo: 30h para A + 30h para B
```

**Várias origens → um alvo**

```text
Origem: Cálculo I (60h) — tópicos: limites, derivadas
Origem: Cálculo II (60h) — tópicos: integrais, séries
Alvo: Cálculo A (90h) — limites, derivadas, integrais
Fluxo: 60h de Cálculo I + 30h de Cálculo II
```

**Conteúdo maior que a carga**

```text
Origem: disciplina de 90h cobre integralmente um alvo de 45h
Fluxo: 45h (o restante da origem não é usado)
```

## Sem ementa

Sem ementa e sem cobertura gerada, a cobertura de tópicos é desconhecida. O
modelo cai para nome + carga e a confiança é menor. Nesse caso:

- use 1-para-1 como limite inferior;
- mostre “dados insuficientes” quando o nome não for claro;
- ofereça upload local de PPC/ementa para o usuário trazer o documento da
  instituição sem enviar nada a servidor.

## Plano de implementação

1. **Feito (calibração contínua):** crawler persistente dos catálogos UNICAMP e
   Jupiterweb, cobertura automática para a UNICAMP e para as disciplinas da
   Poli-USP, e vetores LSA pré-computados. Falta calibrar limiares e ampliar a
   cobertura para outras IES.
2. Definir `origem.tipo` e `curriculo_versao` no schema.
3. **Feito:** implementar max-cost flow no app TypeScript, com fixtures
   sintéticas e testes de regressão.
4. **Pendente:** portar o max-cost flow para o protótipo Python, para comparar
   com o 1-para-1 em testes sintéticos.
5. **Parcial:** comparar o resultado 1-para-1 (limite inferior) com o m-para-n
   no site; falta automatizar essa comparação.
6. Expor no dossiê as propostas agrupadas e a confiança.
7. Adicionar restrições institucionais configuráveis (1-para-1 administrativo,
   teto de aproveitamento, nota mínima, validade temporal, tipo de optativa).

## Limitações e decisões abertas

- A IES pode exigir 1-para-1 administrativo mesmo que o conteúdo seja
  m-para-n; o modelo deve suportar as duas políticas.
- A classificação optativa/ênfase pode não estar no PDF do histórico; exige
  currículo de origem ou input do usuário.
- O teto de aproveitamento e a validade temporal variam por IES.
- A ementa pode estar indisponível; o matching por nome+carga é um fallback.
- O resultado é uma estimativa, não uma decisão oficial.
