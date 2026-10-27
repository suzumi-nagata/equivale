# Cobertura temática por ementas — UNICAMP 2026

Regras geradas **automaticamente** a partir das ementas públicas do Catálogo
dos Cursos de Graduação 2026 da UNICAMP (DAC). Não há exceções de curso
digitadas à mão: o pipeline extrai as ementas, compara tópicos e nomes, e grava
as arestas de cobertura que o matcher consome.

Arquivo gerado: [`unicamp_2026_regras.json`](unicamp_2026_regras.json)

Gerador: [`tools/build_unicamp_cobertura.py`](../../tools/build_unicamp_cobertura.py)

## Método

1. Coleta as páginas de disciplinas do catálogo (lista em `PAGES` no script).
2. Extrai código, nome, carga horária e ementa de cada disciplina.
3. Normaliza o português (acentos, stopwords, plurais simples) e calcula
   TF-IDF sobre as ementas.
4. Para cada componente-alvo com código, compara com as disciplinas do
   catálogo:
   - **similaridade de ementa**: cobertura dos termos do alvo, precisão e
     cosseno;
   - **similaridade de nome**: contenção/Jaccard dos tokens, com guardas para
     numeral de sequência (Cálculo I ≠ Cálculo II) e para teoria × laboratório;
   - candidatos com nome >= 0.6 ou conteúdo >= 0.05; até 20 origens por alvo.
5. Gera uma aresta com `horas_cobertura`, `score`, `confianca`, termos
   compartilhados e URLs das duas ementas.

O matcher aplica ainda uma guarda de conceito específico: um alvo como
“Projeto e Análise de Algoritmos” só aceita uma regra de conteúdo se a origem
também tiver o conceito de projeto/análise de algoritmos. Isso evita que um
laboratório de programação cubra PAA.

## O que o site faz com isso

- O JSON é copiado para `site/public/data/regras.json`.
- As arestas entram no max-cost flow junto com os matches por nome.
- As regras têm `origem_instituicao: "UNICAMP"`; o matcher só as aplica quando o
  histórico importado é da UNICAMP. Isso evita falsos positivos por nome com
  históricos de outras instituições.
- Uma regra nunca substitui um match por nome com score maior, exceto quando
  declara cobertura integral (`ignorar_carga_horaria`) para uma origem menor.
- A UI mostra os termos/ementa que fundamentaram a cobertura e a confiança.
- Tudo é uma estimativa: a decisão final é da instituição.

## Exemplos encontrados automaticamente

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

As regras valem para as variantes AA e AB de Engenharia de Computação e para
Engenharia Elétrica, quando o código do componente existe no alvo.

## Fontes

- Catálogo UNICAMP 2026, disciplinas:
  <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/>
- Cada origem e cada alvo no JSON aponta para a âncora da sua ementa.
- Coleta: 2026-10-26.

## Regenerar

```bash
python3 -I tools/build_unicamp_cobertura.py
# ou usando páginas já baixadas:
python3 -I tools/build_unicamp_cobertura.py --html-dir /tmp/unicamp-ementas/cache
```

O script usa apenas a biblioteca padrão. Se uma página falhar, ele avisa e
segue com as demais.

## Limitações

- TF-IDF de ementa não é compreensão semântica; nomes e ementas genéricas
  (especialmente laboratórios) podem gerar candidatos ruins.
- Os limiares e o top 20 são heurísticos e podem ser recalibrados.
- As horas de cobertura são uma aproximação; a IES pode aceitar mais ou menos.
- O catálogo cobre as páginas listadas no script, não necessariamente todas as
  disciplinas da universidade.
- A decisão final é sempre da instituição de destino.
