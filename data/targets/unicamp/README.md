# Currículos-alvo — UNICAMP 2026

Conversão dos currículos públicos da UNICAMP 2026 para o schema de curso-alvo
do site. Os dados de origem ficam em
[`data/sources/unicamp`](../../sources/unicamp/README.md); esta pasta contém
apenas os alvos que o site carrega.

## Arquivos

Alvos manualmente convertidos e auditados:

- [`unicamp-ec-2026-aa.json`](unicamp-ec-2026-aa.json) — Engenharia de
  Computação, habilitação **AA — Sistemas de Computação**.
- [`unicamp-ec-2026-ab.json`](unicamp-ec-2026-ab.json) — Engenharia de
  Computação, habilitação **AB — Sistemas e Processos Industriais**.
- [`unicamp-ee-2026.json`](unicamp-ee-2026.json) — Engenharia Elétrica, currículo
  pleno **41G**.

Alvos de engenharia gerados automaticamente pelo catálogo:

- 16 arquivos `unicamp-engenharia-*-2026*.json`, cobrindo os demais cursos de
  engenharia do catálogo 2026, incluindo as duas ênfases de Engenharia Física.
- A conversão é feita por
  [`tools/build_targets_from_catalog.py`](../../../tools/build_targets_from_catalog.py);
  os arquivos gerados não passaram pela mesma auditoria manual dos três alvos
  acima.

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
- Reconhecimento: os alvos de engenharia foram conferidos nos atos do
  **CEE-SP**, que regula os cursos da UNICAMP. O mapa
  [`data/targets/mec_status.json`](../mec_status.json) e o script
  [`tools/apply_mec_status.py`](../../../tools/apply_mec_status.py) aplicam
  `status = reconhecido_cee_sp`, o número do ato e a URL da fonte.
  - `Portaria CEE-GP 236/2025`: Engenharia Civil, de Alimentos, de Computação,
    de Controle e Automação, de Produção, Elétrica, Mecânica e Química.
  - `Parecer CEE 85/2023`: Engenharia Agrícola.
  - `Parecer CEE 04/2026`: Engenharia Ambiental.
  - `Parecer CEE 124/2026`: Engenharia de Manufatura.
  - `Parecer CEE 315/2021`: Engenharia Física.
  - `Portaria CEE/GP 488/2017`, renovada pela `449/2021`: Engenharia de
    Telecomunicações.
  - `Parecer CEE 110/2024` / `Portaria CEE/GP 118/2024`: Engenharia de
    Transportes.
- Em universidades estaduais paulistas, o e-MEC pode não exibir o ato de
  reconhecimento de curso; a referência é o CEE-SP. O seletor não usa mais
  “ato não consultado” para esses alvos.
- `dados.completude = grade_com_ch`: há grade e carga horária; não há ementa
  nem PPC incorporados.

## Regenerar

```bash
# Os três alvos manuais (AA/AB/41G)
python3 -I tools/build_unicamp_targets.py

# Os alvos de engenharia gerados a partir do catálogo
python3 -I tools/build_targets_from_catalog.py --only-unicamp

# Reaplica os atos de reconhecimento do CEE-SP
python3 -I tools/apply_mec_status.py
```

O primeiro script lê `data/sources/unicamp/*.json`; o segundo lê
`data/catalog/unicamp_2026_cursos.json` e nunca sobrescreve 34G/41G. Nenhum
deles baixa dados ou usa histórico escolar.

## Limitações

- A conversão é uma modelagem do catálogo, não uma decisão de equivalência. As
regras de cobertura temática por ementa (geradas automaticamente) ficam em
[`data/ontology`](../../ontology/README.md).
- Grupos de eletivas livres podem ser mais restritos na regra real da IES.
- A grade de 2026 pode não corresponder ao catálogo de quem se formou antes.
- As ementas usadas nas regras de cobertura são coletadas à parte pelo
  catálogo da UNICAMP e ficam em [`data/ontology`](../../ontology/README.md);
  sem uma regra aplicável, o matching usa nome + carga horária.
