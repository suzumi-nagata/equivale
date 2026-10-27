# Equivale — site

App estático em Vite + React + TypeScript. Não há backend: o histórico é lido
no navegador e o site só baixa os dados públicos das grades.

## Rodando localmente

```bash
cd site
npm install
npm run dev
```

O `predev` copia os currículos públicos de `../data/spike/curriculos` e o
`cursos.json` para `public/data/` (gerado; não versionado).

Build de produção:

```bash
npm run build
npm run preview
```

## O que já funciona

- Seleção de curso alvo: UNINTER ADS e Engenharia de Software.
- Importação de histórico em **JSON** (saída do parser local) ou **CSV**.
- Histórico fictício de demonstração.
- Matcher **m-para-n guloso** por nome + carga horária: uma origem pode cobrir
  vários componentes e um componente pode combinar várias origens.
- Resumo de horas abatidas, cobertura, disciplinas restantes e semestres
  estimados; tabela de matches, lacunas e componentes não abatíveis.
- Download local do relatório em JSON.

Ainda não incluso:

- Adaptador PDF no navegador (por enquanto, use o parser em `../prototype`).
- Ementas/PPC e matching por conteúdo.
- Fluxo de custo mínimo (o matcher atual é uma heurística gulosa).
- Regras por IES (teto de aproveitamento, optativa livre, pré-requisitos).

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
    match.ts               # alocação m-para-n gulosa
    transcript.ts          # parse JSON/CSV
    types.ts
  data/demo.ts             # histórico fictício
scripts/sync-data.mjs      # copia dados públicos para public/data
```

## Próximos passos

- Portar o parser de PDF para `pdf.js` em Web Worker.
- Trocar a heurística gulosa por max-cost flow.
- Adicionar ementas/PPC e upload local de PPC.
- Adicionar mais cursos/IES com dados públicos e proveniência.
