# Protótipo: parser de históricos UNICAMP e USP

Script standalone em Python 3 (somente biblioteca padrão) que lê históricos
escolares em PDF e gera um JSON normalizado. Usa `pdftotext -bbox-layout`
(poppler) para reconstruir linhas e colunas por coordenadas — necessário porque
os dois layouts têm nomes quebrados em várias linhas e colunas opcionais que
deslocam os números.

## Requisitos

- Python 3.10+ (testado com 3.14)
- `pdftotext` (pacote `poppler-utils`)
- Nenhum pacote Python externo

## Uso

```bash
python3 -I parse_transcripts.py HISTORICO.pdf [OUTRO.pdf ...] \
  --out-dir /tmp/transcript-parser --sample 5
```

- `-I` evita importar módulos do diretório atual.
- O JSON sai em `<out-dir>/<instituicao>_<sha256-curto>.json`.
- O script não copia os PDFs e não extrai nome, RA/RG, nascimento ou outros
  dados de identidade; apenas as linhas acadêmicas.
- O JSON contém dados acadêmicos. Guarde em local privado e não commite.

## O que é extraído

- Instituição (detectada automaticamente).
- Curso/habilitação/módulo (USP; a UNICAMP não traz isso no PDF e exige seleção
  manual do curso/catálogo).
- Disciplinas: período, código original e normalizado, nome, horas, créditos
  (UNICAMP) ou AU/TR (USP), CE/CP/EXT/ATPA, frequência, média, situação e página.
- Resumo: disciplinas, aprovadas, horas, créditos, totais declarados e
  conferência.
- `validacao_codigos`: compara a quantidade de códigos visível no texto com a
  quantidade efetivamente parseada.

## Validação local

O parser foi validado localmente com dois históricos reais; os PDFs e os JSONs
normalizados **não são versionados**. A validação cobre:

- códigos com espaço, nomes quebrados em várias linhas e colunas opcionais;
- situações não numéricas (proficiência, suficiência, desistência) e TCC/estágio;
- reconciliação dos totais de horas/créditos declarados no próprio documento;
- contagem de códigos no texto versus códigos parseados.

Para reproduzir, use seus próprios PDFs; nenhum histórico é incluído no
repositório.

## Limitações

- Depende de `pdftotext`; no browser, a lógica de coordenadas deve ser portada
  para `pdf.js` (`getTextContent()` + `transform`).
- Ajustado aos layouts atuais da UNICAMP (DAC) e USP (Júpiter). Outras versões
  ou instituições precisam de adaptador e fixtures próprios.
- A UNICAMP não informa curso/catálogo no PDF; o usuário seleciona manualmente.
- O parser não busca ementas; os códigos são a chave para buscar no DAC
  (UNICAMP) e no Jupiterweb (USP).
- O JSON é pessoal; não commitar.

## Matcher PoC

`match_curricula.py` cruza um histórico normalizado com um currículo normalizado (ex.: UNINTER ADS/Eng. Software) e gera um relatório de matches, restantes e componentes não abatíveis.

```bash
python3 -I match_curricula.py \
  --transcript /tmp/transcript-parser/SEU_HISTORICO.json \
  --curriculum ../data/spike/curriculos/uninter_ads.json \
  --out /tmp/spike-matching/resultado.json --top 10
```

O pareamento atual é uma atribuição ótima **1-para-1** (algoritmo húngaro), por
nome + carga horária. Sem ementa, a confiança é menor; componentes de
estágio/TCC/extensão/projetos são separados como não abatíveis. O modelo
definitivo será **m-para-n** (capacidade de horas e cobertura de conteúdo); ver
[`docs/MATCHING.md`](../docs/MATCHING.md).

## Próximos passos

- Portar a lógica de linhas/colunas para `pdf.js` em Web Worker.
- Adicionar adaptadores e fixtures para outros layouts.
- Ligar os códigos às ementas (UNICAMP DAC, USP Jupiterweb) e ao motor de
  matching.
- Adicionar testes sintéticos para `parse_pages`, `map_situacao` e
  `declared_totals`.
