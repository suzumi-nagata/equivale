# Equivale — site

App estático em Vite + React + TypeScript. Não há backend: o histórico é lido
no navegador e o site só baixa os dados públicos das grades.

## Rodando localmente

```bash
cd site
npm install
npm run dev
```

O `predev` copia os currículos públicos de `../data/spike/curriculos`,
`../data/targets/unicamp` e `../data/targets/usp`, o `cursos.json` e as regras
de `../data/ontology` para `public/data/` (gerado; não versionado).

Build de produção:

```bash
npm run build
npm run preview
```

Testes do matcher:

```bash
npm test
```

## O que já funciona

- Seleção de curso alvo: UNINTER ADS/Engenharia de Software, UNICAMP 2026
  (Engenharia de Computação AA/AB e Engenharia Elétrica 41G) e Poli-USP
  (Engenharia Elétrica Automação e Controle 2027 e Engenharia de Computação
  2012). O seletor tem busca e filtros por instituição, modalidade e grau.
- Importação de histórico em **JSON** (saída do parser local) ou **CSV**.
- Histórico fictício de demonstração.
- Matcher **max-cost flow m-para-n** por nome + carga horária: uma origem pode
  cobrir vários componentes, um componente pode combinar várias origens e
  grupos de eletivas aceitam alocações parciais. Regras de cobertura temática
  geradas a partir de ementas adicionam arestas quando o nome não coincide.
- Cobertura temática por ementas da UNICAMP e da Poli-USP (TF-IDF + nome,
  gerada offline por `../tools/build_unicamp_cobertura.py` e
  `../tools/build_usp_cobertura.py`), com termos compartilhados, confiança e URL
  da ementa. As regras são aplicadas apenas a históricos da mesma instituição
  de origem.
- Modo opcional **“Ignorar diferença de carga horária”** no seletor: quando
  ligado, uma origem de 30h pode cobrir um componente de 90h por conteúdo. O
  padrão continua conservador.
- MEC: para UNICAMP e USP, o catálogo oficial é a fonte da grade, mas o ato de
  reconhecimento ainda não foi consultado no e-MEC; o seletor mostra “ato não
  consultado” e “instituição pública”, não “não reconhecido”.
- Resumo de horas abatidas, cobertura, disciplinas restantes e semestres
  estimados; tabela de matches, lacunas e componentes não abatíveis.
- Download local do relatório em JSON.

Ainda não incluso:

- Adaptador PDF no navegador (por enquanto, use o parser em `../prototype`).
- Ementas para outras IES e matching semântico mais profundo; o pipeline atual
  é TF-IDF para a UNICAMP e para as disciplinas da Poli-USP.
- Upload local de PPC/ementa pelo usuário.
- Regras por IES (teto de aproveitamento, optativa livre específica,
  pré-requisitos, nota mínima, validade temporal).


## Privacidade

- Nenhum histórico é enviado a servidor.
- O site só faz `fetch` dos JSONs públicos em `data/`.
- Sem analytics, sem cookies, sem scripts de terceiros.
- Fontes self-hosted via `@fontsource` (sem requisições a Google Fonts).
- O relatório baixado inclui o histórico importado; o download é uma ação
  local do usuário.

## Deploy no GitHub Pages

O workflow está em [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

1. No GitHub, abra **Settings → Pages** e defina **Source: GitHub Actions**.
2. Faça push para a branch `main` (ou rode o workflow manualmente).
3. O workflow instala, builda `site/` e publica `site/dist`.

O `BASE_PATH` vem de `actions/configure-pages`, então o site funciona tanto em
`usuario.github.io/repo` quanto em domínio próprio.

## Estrutura

```text
src/
  App.tsx                  # estado, importação, layout
  components/
    TargetPicker.tsx       # escolha do curso alvo
    TranscriptPanel.tsx    # importação JSON/CSV + preview
    SummaryPanel.tsx       # resumo/cobertura
    ResultLedger.tsx       # tabela de matches, lacunas, não abatíveis
  lib/
    normalize.ts           # normalização, conceitos, score
    match.ts               # max-cost flow m-para-n
    match.test.ts          # testes sintéticos do matcher
    transcript.ts          # parse JSON/CSV
    types.ts
  data/demo.ts             # histórico fictício
scripts/sync-data.mjs      # copia dados públicos para public/data
```

## Próximos passos

- Portar o parser de PDF para `pdf.js` em Web Worker.
- Adicionar ementas/PPC e upload local de PPC.
- Adicionar mais cursos/IES com dados públicos e proveniência.
- Expor regras institucionais configuráveis no matching.
