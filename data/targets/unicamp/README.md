# Currículos-alvo — UNICAMP 2026

Conversão dos currículos públicos da UNICAMP 2026 para o schema de curso-alvo
do site. Os dados de origem ficam em
[`data/sources/unicamp`](../../sources/unicamp/README.md); esta pasta contém
apenas os alvos que o site carrega.

## Arquivos

- [`unicamp-ec-2026-aa.json`](unicamp-ec-2026-aa.json) — Engenharia de
  Computação, habilitação **AA — Sistemas de Computação**.
- [`unicamp-ec-2026-ab.json`](unicamp-ec-2026-ab.json) — Engenharia de
  Computação, habilitação **AB — Sistemas e Processos Industriais**.
- [`unicamp-ee-2026.json`](unicamp-ee-2026.json) — Engenharia Elétrica, currículo
  pleno **41G**.

AA e AB são habilitações distintas e aparecem como alvos separados. A variante
AX (matrícula antes da opção) não é oferecida como alvo.

## Conversão

- O núcleo comum e as obrigatórias da variante viram slots fixos de 15/30/60/90h.
- Cada grupo de eletivas vira **um slot de créditos**, com demanda
  `créditos_exigidos × 15h`, e não uma disciplina única.
- Grupos com `EX---`, `MX---` ou `IX---` são marcados como `livre`: qualquer
  disciplina elegível da origem pode preencher a demanda, com confiança baixa.
- Grupos com lista fechada guardam os nomes das disciplinas como opções.
- A carga total é a soma dos grupos: 3.645h (EC AA), 3.705h (EC AB) e 3.780h
  (EE 41G).
- A duração segue a proposta de cumprimento do catálogo: 10 semestres para EC e
  14 semestres para EE.

## Proveniência

- Fonte: Catálogo dos Cursos de Graduação 2026 da UNICAMP (DAC), páginas de
  currículo e de sugestão de cumprimento.
- Coleta: 2026-10-26.
- `mec.status` ficou como `nao_verificado`: o catálogo é oficial, mas o ato de
  reconhecimento não foi consultado no e-MEC nesta etapa. Isso **não** significa
  que o curso não seja reconhecido; a UNICAMP é uma universidade pública e o
  seletor mostra “instituição pública” e “ato não consultado”.
- `dados.completude = grade_com_ch`: há grade e carga horária; não há ementa
  nem PPC incorporados.

## Regenerar

```bash
python3 -I tools/build_unicamp_targets.py
```

O script lê `data/sources/unicamp/*.json` e reescreve os três JSONs. Ele não
baixa nada e não usa dados de histórico.

## Limitações

- A conversão é uma modelagem do catálogo, não uma decisão de equivalência. As
regras de cobertura temática por ementa (geradas automaticamente) ficam em
[`data/ontology`](../../ontology/README.md).
- Grupos de eletivas livres podem ser mais restritos na regra real da IES.
- A grade de 2026 pode não corresponder ao catálogo de quem se formou antes.
- As ementas usadas nas regras de cobertura são coletadas à parte pelo
  catálogo da UNICAMP e ficam em [`data/ontology`](../../ontology/README.md);
  sem uma regra aplicável, o matching usa nome + carga horária.
