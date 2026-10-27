# Course Credits Comparator

Site estático e client-side para comparar currículos de cursos superiores
brasileiros e estimar aproveitamento de estudos (equivalências) para uma segunda
graduação ou concurso.

O objetivo é responder: **dado o meu histórico, quanto de outro curso eu
conseguiria abater, o que faltaria e em quanto tempo?** — sem enviar o histórico
para nenhum servidor.

## Status

- **Parser de históricos:** protótipo para UNICAMP (DAC) e USP (Júpiter), com
  extração por coordenadas (sem OCR). Validado localmente; os PDFs e JSONs de
  teste não são versionados.
- **Site:** protótipo em [`site/`](site/) com Vite + React + TypeScript,
  importação de histórico em JSON/CSV, histórico fictício de demonstração e
  matcher **m-para-n guloso**. Deploy preparado para GitHub Pages.
- **Matcher:** o PoC Python é 1-para-1; o site usa uma heurística m-para-n. O
  modelo definitivo é **max-cost flow** (capacidade de horas + cobertura de
  conteúdo). Ver [`docs/MATCHING.md`](docs/MATCHING.md).
- **Spike de dados:** 5 IES privadas EAD (UNINTER, Anhanguera, Estácio, Cruzeiro
  do Sul Virtual e UNIP), somente com fontes públicas. Ver
  [`data/spike/README.md`](data/spike/README.md).

## Privacidade e dados

- Sem backend: o histórico é lido localmente/no navegador.
- O repositório **não contém** históricos escolares, nomes, RA/RG, notas ou
  resultados de matching derivados de históricos reais.
- Só entram dados públicos: currículos, páginas institucionais, atos do MEC e
  fontes citadas.
- Contribuições de adaptadores devem usar **fixtures sintéticos ou
  anonimizados**; nunca envie um histórico real.
- O [`.gitignore`](.gitignore) cobre PDFs, `private/`, `transcripts/`,
  `reports/` e `data/spike/matching/`.

## Estrutura

```text
site/                    # app estático (Vite + React + TS)
  src/
    components/          # alvo, importação, resumo, resultado
    lib/                 # normalização, matcher m-para-n, parse JSON/CSV
    data/demo.ts         # histórico fictício
  scripts/sync-data.mjs  # copia dados públicos para public/data
prototype/
  parse_transcripts.py   # parser UNICAMP/USP -> JSON normalizado
  match_curricula.py     # matcher PoC 1-para-1 (húngaro)
data/spike/
  README.md              # spike de IES privadas EAD
  cursos.json            # 8 cursos com status MEC, grade/PPC, ingresso etc.
  curriculos/            # grades públicas (UNINTER ADS e Eng. Software)
docs/
  MATCHING.md            # modelo 1-para-1 atual e desenho m-para-n
.github/workflows/
  deploy.yml             # build + deploy do site no GitHub Pages
```

## Rodando os protótipos

### Site

```bash
cd site
npm install
npm run dev       # http://localhost:5173
npm run build     # gera site/dist
```

O `predev`/`prebuild` copia os currículos públicos de
`data/spike/curriculos` para `site/public/data` (gerado; não versionado). O site
importa histórico em JSON/CSV e já abre com um histórico fictício de
demonstração.

### Parser e matcher Python

```bash
# Parser de histórico (local; o JSON fica em /tmp)
python3 -I prototype/parse_transcripts.py HISTORICO.pdf \
  --out-dir /tmp/transcript-parser --sample 5

# Matcher PoC (1-para-1)
python3 -I prototype/match_curricula.py \
  --transcript /tmp/transcript-parser/SEU_HISTORICO.json \
  --curriculum data/spike/curriculos/uninter_ads.json \
  --out /tmp/spike-matching/resultado.json
```

O parser usa `pdftotext` (poppler). Nenhum pacote Python externo é necessário.

## Deploy

O workflow [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) builda
`site/` e publica no GitHub Pages. No GitHub, habilite **Settings → Pages →
Source: GitHub Actions** e faça push para `main`.

## Modelo de matching

O PoC atual é uma atribuição ótima **1-para-1**: cada disciplina de origem ocupa
no máximo um componente do currículo alvo. Isso é um **limite inferior** — na
prática, uma disciplina pode cobrir vários componentes (por exemplo, uma
disciplina ampla de física ou matemática) e vários componentes podem ser
cobertos pela combinação de mais de uma disciplina de origem.

O modelo definitivo é **m-para-n**:

- cada disciplina de origem tem capacidade de horas e uma cobertura de tópicos;
- cada componente do alvo tem demanda de horas e tópicos exigidos;
- o pareamento vira um fluxo (max-cost flow / min-cost flow), permitindo
  dividir uma origem entre vários alvos e combinar várias origens em um alvo;
- regras institucionais (1-para-1 administrativo, teto de aproveitamento,
  optativa livre, pré-requisitos) entram como restrições;
- sem ementa, o matching cai para nome + carga, com confiança menor.

Além disso, o histórico sozinho não diz se uma disciplina era obrigatória,
optativa ou dependente de ênfase. Essa classificação precisa vir do currículo
de origem (público) ou do próprio usuário — e afeta a estimativa.

## Licença

A definir.
