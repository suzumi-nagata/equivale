# Equivale

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
  matcher **max-cost flow m-para-n**. Publicado em
  <https://suzumi-nagata.github.io/equivale/>.
- **Matcher:** o PoC Python é 1-para-1; o site implementa **max-cost flow**
  (capacidade de horas + cobertura de conteúdo), com testes sintéticos. Ver
  [`docs/MATCHING.md`](docs/MATCHING.md).
- **Dados de origem:** currículos públicos UNICAMP 2026 de Engenharia de
  Computação (habilitações AA/AB) e Engenharia Elétrica (41G), com classificação
  de obrigatórias/eletivas/ênfases. Ver
  [`data/sources/unicamp/README.md`](data/sources/unicamp/README.md).
- **Dados-alvo:** conversão dos currículos UNICAMP 2026 para o schema do site,
  incluindo grupos de eletivas por crédito. Ver
  [`data/targets/unicamp/README.md`](data/targets/unicamp/README.md).
- **Alvos USP:** Engenharia Elétrica (ênfase Automação e Controle, ciclo básico
  + ênfase) e Engenharia de Computação (currículo 2012 disponível no
  Jupiterweb), da Poli-USP. Ver
  [`data/targets/usp/README.md`](data/targets/usp/README.md).
- **Cobertura temática:** regras geradas automaticamente a partir das ementas
  públicas da UNICAMP e da Poli-USP (TF-IDF + similaridade de nomes, sem LLM em
  runtime). As regras da UNICAMP ligam componentes da EC/EE a disciplinas do
  catálogo; as da USP ligam componentes da UNICAMP a disciplinas das grades da
  Poli. Ver [`data/ontology/README.md`](data/ontology/README.md).
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
    lib/                 # normalização, matcher max-cost flow, parse JSON/CSV
    data/demo.ts         # histórico fictício
  scripts/sync-data.mjs  # copia dados públicos para public/data
prototype/
  parse_transcripts.py   # parser UNICAMP/USP -> JSON normalizado
  match_curricula.py     # matcher PoC 1-para-1 (húngaro)
tools/
  extract_unicamp_2026.py   # extrai currículos públicos UNICAMP 2026
  build_unicamp_targets.py  # converte origem UNICAMP -> alvos do site
  build_unicamp_cobertura.py # extrai ementas e gera cobertura temática UNICAMP
  build_usp_cobertura.py    # gera cobertura temática USP -> alvos UNICAMP
  extract_usp_poli.py       # extrai alvos EE/EC da Poli-USP (Jupiterweb)
data/sources/unicamp/
  README.md              # escopo, habilitações/ênfases e proveniência
  eng_computacao_2026.json # 34G: núcleo comum + AA/AB (e AX)
  eng_eletrica_2026.json   # 41G: núcleo comum + eletivas + certificados
data/targets/unicamp/
  README.md              # conversão para o schema de alvo
  unicamp-ec-2026-aa.json
  unicamp-ec-2026-ab.json
  unicamp-ee-2026.json
data/targets/usp/
  README.md              # proveniência e limitações das grades Poli-USP
  usp-poli-ee-ac-2027.json
  usp-poli-ec-2012.json
data/ontology/
  README.md              # regras de cobertura temática por ementa
  unicamp_2026_regras.json
  usp_2026_regras.json
data/spike/
  README.md              # spike de IES privadas EAD
  cursos.json            # 8 cursos com status MEC, grade/PPC, ingresso etc.
  curriculos/            # grades públicas (UNINTER ADS e Eng. Software)
docs/
  MATCHING.md            # 1-para-1, max-cost flow e desenho do modelo
.github/workflows/
  ci.yml                 # lint + testes + build em PRs
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
`data/spike/curriculos`, `data/targets/unicamp` e `data/targets/usp`, além das
regras de `data/ontology`, para `site/public/data` (gerado; não versionado). O
site importa histórico em JSON/CSV e já abre com um histórico fictício de
demonstração.

### Testes do matcher

```bash
cd site
npm test
```

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

O PoC Python é uma atribuição ótima **1-para-1**: cada disciplina de origem
ocupa no máximo um componente do currículo alvo. Isso é um **limite inferior** —
na prática, uma disciplina pode cobrir vários componentes (por exemplo, uma
disciplina ampla de física ou matemática) e vários componentes podem ser
cobertos pela combinação de mais de uma disciplina de origem.

O site implementa **max-cost flow m-para-n**:

- cada disciplina de origem tem capacidade de horas;
- cada componente do alvo tem demanda de horas;
- uma origem pode ser dividida entre vários alvos e vários alvos podem combinar
  origens;
- o fluxo maximiza `Σ score × horas`, com um bônus mínimo para aproveitar mais
  horas em caso de empate;
- grupos de eletivas por crédito são slots de demanda; grupos livres aceitam
  qualquer disciplina elegível com confiança baixa;
- regras de cobertura temática geradas a partir de ementas (`data/ontology`)
  adicionam arestas quando o nome não coincide, como Física III/IV da EC
  cobertas por disciplinas da EE ou disciplinas da Poli-USP cobrindo
  componentes da UNICAMP;
- regras institucionais mais específicas (1-para-1 administrativo, teto de
  aproveitamento, optativa restrita, pré-requisitos) ainda não são configuráveis;
- sem ementa, o matching cai para nome + carga, com confiança menor.

Os testes sintéticos do site ficam em `site/src/lib/match.test.ts`.

Além disso, o histórico sozinho não diz se uma disciplina era obrigatória,
optativa ou dependente de ênfase. Essa classificação precisa vir do currículo
de origem (público) ou do próprio usuário — e afeta a estimativa.

## Licença

A definir.
