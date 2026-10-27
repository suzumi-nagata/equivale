# Cobertura temática por ementas — UNICAMP e USP

Regras geradas **automaticamente** a partir de ementas públicas. Não há
exceções de curso digitadas à mão: os scripts extraem códigos, nomes, cargas e
ementas, comparam tópicos e nomes, e gravam as arestas de cobertura que o
matcher consome. Nenhum LLM é usado na geração nem no runtime.

Arquivos gerados:

- [`unicamp_2026_regras.json`](unicamp_2026_regras.json) — origens UNICAMP
  (catálogo DAC) para componentes UNICAMP.
- [`usp_2026_regras.json`](usp_2026_regras.json) — origens USP (Jupiterweb,
  grades da Poli) para componentes UNICAMP.

Geradores:

- [`tools/build_unicamp_cobertura.py`](../../tools/build_unicamp_cobertura.py)
- [`tools/build_usp_cobertura.py`](../../tools/build_usp_cobertura.py)

## Método

1. Coleta as páginas públicas de disciplinas:
   - UNICAMP: Catálogo dos Cursos de Graduação 2026 (DAC);
   - USP: Jupiterweb, a partir das grades públicas da Poli e das páginas
     `obterDisciplina`.
2. Extrai código, nome, carga horária e ementa de cada disciplina.
3. Normaliza o português (acentos, stopwords, plurais simples) e calcula
   TF-IDF sobre as ementas.
4. Para cada componente-alvo com código, compara com as disciplinas de origem:
   - **similaridade de ementa**: cobertura dos termos do alvo, precisão e
     cosseno;
   - **similaridade de nome**: contenção/Jaccard dos tokens, com guardas para
     numeral de sequência (Cálculo I ≠ Cálculo II) e para teoria × laboratório;
   - candidatos com nome >= 0.6 ou conteúdo >= 0.05; até 20 origens por alvo na
     UNICAMP e 30 na USP.
5. Gera uma aresta com `horas_cobertura`, `score`, `confianca`, termos
   compartilhados, `ignorar_carga_horaria` quando aplicável e URLs das duas
   ementas.

O matcher aplica ainda guardas de conceito específico, sequência e tipo
(teoria/laboratório). Isso evita que um laboratório de programação cubra
“Projeto e Análise de Algoritmos”, que “Física III” cubra “Física Geral IV” ou
que programação genérica cubra Computação Gráfica.

## O que o site faz com isso

- Os JSONs são mesclados em `site/public/data/regras.json`.
- As arestas entram no max-cost flow junto com os matches por nome.
- Cada regra declara `origem_instituicao`; o matcher só a aplica quando o
  histórico importado é da mesma instituição. Isso evita falsos positivos entre
  históricos USP e UNICAMP.
- Uma regra não substitui um match por nome com score maior, exceto quando
  declara cobertura integral (`ignorar_carga_horaria`) para uma origem menor.
- A UI mostra os termos/ementa que fundamentaram a cobertura e a confiança.
- Tudo é uma estimativa: a decisão final é da instituição.

## Exemplos encontrados automaticamente

UNICAMP → UNICAMP:

- Física Geral III (F 328) coberta por EE521 pela ementa de eletromagnetismo.
- Física Geral IV (F 428) coberta por EE300 pela ementa de relatividade/física
  moderna.
- Resistência dos Materiais (EM424) coberta por EM423; a carga menor da origem
  é aceita pela regra de cobertura integral.
- Sistemas Embarcados e Laboratório de Sistemas Embarcados cobertos por EA075
  e EA076, respectivamente.
- Teoria e laboratório não se misturam: “Análise Linear de Sistemas” é coberta
  por EA616, enquanto “Laboratório de Análise Linear” é coberta por EA619.
- MC404 coberta por EA869.
- Projeto e Análise de Algoritmos I permanece aberta quando a origem não tem o
  conceito específico; o laboratório de programação não a cobre.
- Computação Gráfica e Processamento de Imagem permanece aberta quando a origem
  não tem imagem/gráfica/visão computacional; programação genérica não basta.
- Física Experimental III é coberta por laboratórios com ementa compatível
  (por exemplo, EA619/EA722 no histórico de teste).

USP → UNICAMP:

- Ciências do Ambiente (BE310) coberta por Energia, Meio Ambiente e
  Sustentabilidade (PEA3100).
- Programação Orientada a Objetos (MC302) coberta pela disciplina equivalente
  da Poli, quando a ementa e o conceito coincidem.
- Química I coberta por Química Geral, quando a ementa é compatível.
- Análise Linear de Sistemas e Laboratório de Análise Linear cobertos por
  disciplinas de teoria e laboratório correspondentes, sem cruzamento entre os
  dois tipos.
- Métodos da Engenharia Elétrica coberto pela introdução à engenharia elétrica
  da Poli.

As regras valem para as variantes AA e AB de Engenharia de Computação e para
Engenharia Elétrica, quando o código do componente existe no alvo.

## Fontes

- Catálogo UNICAMP 2026, disciplinas:
  <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/>
- Jupiterweb, disciplinas:
  <https://uspdigital.usp.br/jupiterweb/jupDisciplinaBusca?tipo=D&codmnu=6755>
- Cada origem e cada alvo no JSON aponta para a âncora da sua ementa.
- Coleta: 2026-10-26 (UNICAMP) e 2026-10-27 (USP).

## Regenerar

```bash
# UNICAMP: usa data/catalog automaticamente quando ele existe
python3 -I tools/build_unicamp_cobertura.py
python3 -I tools/build_unicamp_cobertura.py --catalog data/catalog/unicamp_2026_disciplinas.json

# USP -> UNICAMP: usa o catálogo e limita as origens às grades-alvo
python3 -I tools/build_usp_cobertura.py
python3 -I tools/build_usp_cobertura.py --all-usp-sources  # todas as disciplinas do catálogo USP
```

Sem catálogo, os scripts caem para as páginas antigas (`--html-dir`). Os
comandos usam apenas a biblioteca padrão. Se uma página falhar, avisam e seguem
com as demais.

O catálogo completo é produzido por `tools/crawl_catalogos.py`; ver
[`data/catalog`](../catalog/README.md).

## Limitações

- TF-IDF de ementa não é compreensão semântica; nomes e ementas genéricas
  (especialmente laboratórios) podem gerar candidatos ruins.
- Os limiares e o número máximo de origens são heurísticos e podem ser
  recalibrados.
- As horas de cobertura são uma aproximação; a IES pode aceitar mais ou menos.
- A cobertura USP usa, por padrão, as disciplinas citadas nas grades-alvo da
  Poli; `--all-usp-sources` amplia para todo o catálogo, mas aumenta o ruído.
- A decisão final é sempre da instituição de destino.
