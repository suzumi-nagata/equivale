# Modelo de matching: de 1-para-1 para m-para-n

## Estado atual (PoC)

O matcher atual (`prototype/match_curricula.py`) usa uma atribuição ótima
**1-para-1** (algoritmo húngaro):

- cada disciplina de origem ocupa no máximo um slot do currículo alvo;
- cada slot recebe no máximo uma disciplina de origem;
- o score combina nome/conceitos + aderência de carga horária;
- estágio, TCC, extensão, atividades complementares e projetos são separados
  como não abatíveis.

Esse modelo é deliberadamente conservador. Ele serve para validar o fluxo e
produz um **limite inferior** da equivalência possível.

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

Sem ementa, a cobertura de tópicos é desconhecida. O modelo cai para nome +
carga e a confiança é menor. Nesse caso:

- use 1-para-1 como limite inferior;
- mostre “dados insuficientes” quando o nome não for claro;
- ofereça upload local de PPC/ementa para o usuário trazer o documento da
  instituição sem enviar nada a servidor.

## Plano de implementação

1. Extrair tópicos/cobertura das ementas (ontologia curada + NLP clássico;
   LLM apenas offline, uma vez, com revisão humana).
2. Definir `origem.tipo` e `curriculo_versao` no schema.
3. Implementar max-cost flow no protótipo Python (para testes sintéticos).
4. Portar para TypeScript/Web Worker no app final.
5. Criar fixtures sintéticas m-para-n e testes de regressão.
6. Comparar o resultado 1-para-1 (limite inferior) com o m-para-n.
7. Expor no dossiê as propostas agrupadas e a confiança.

## Limitações e decisões abertas

- A IES pode exigir 1-para-1 administrativo mesmo que o conteúdo seja
  m-para-n; o modelo deve suportar as duas políticas.
- A classificação optativa/ênfase pode não estar no PDF do histórico; exige
  currículo de origem ou input do usuário.
- O teto de aproveitamento e a validade temporal variam por IES.
- A ementa pode estar indisponível; o matching por nome+carga é um fallback.
- O resultado é uma estimativa, não uma decisão oficial.
