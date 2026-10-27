# Currículos-alvo — Poli-USP

Dados públicos do Jupiterweb (USP) usados como alvos de comparação. A coleta
foi feita em 2026-10-27; a grade pode mudar.

## Arquivos

Alvos manualmente convertidos:

- [`usp-poli-ee-ac-2027.json`](usp-poli-ee-ac-2027.json) — Engenharia Elétrica,
  ênfase **Automação e Controle**, ciclo básico + ênfase.
- [`usp-poli-ec-2012.json`](usp-poli-ec-2012.json) — Engenharia de Computação,
  currículo **2012** (tabela disponível no Jupiterweb).

Alvos de engenharia gerados automaticamente:

- 13 arquivos `usp-poli-<codcur>-<codhab>.json`, cobrindo as habilitações de
  engenharia da Poli com grade publicada. A conversão é feita por
  [`tools/build_targets_from_catalog.py`](../../../tools/build_targets_from_catalog.py).
- O ciclo básico 3033, os ciclos 3201/3251 e o currículo antigo 3121 são
  preservados como alvos manuais; o gerador não os sobrescreve.
- A grade da página pode estar em construção e, em algumas habilitações, cobrir
  apenas o ciclo básico; confira `observacoes` e a fonte.

## Fontes

- Ciclo básico EE 2027:
  <https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3033&codhab=0&tipo=N&print=true>
- Ênfase Automação e Controle 2027:
  <https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3032&codhab=3150&tipo=V&print=true>
- Engenharia de Computação (currículo 2012):
  <https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3121&codhab=10&tipo=V&print=true>
- Página oficial do curso de Engenharia de Computação da Poli:
  <https://www.poli.usp.br/ensino/graduacao/cursos-e-habilitacoes/engenharia-de-computacao/>

## Como ler

- Os grupos correspondem aos períodos da grade; cada disciplina tem código,
  nome e carga horária (CH) extraídos da tabela.
- O total do JSON é a soma das disciplinas obrigatórias extraídas. O resumo
  oficial do Jupiterweb inclui também optativas, AAC, AEX e extensão; isso está
  registrado em `observacoes`.
- Engenharia Elétrica: ciclo básico 1º–6º + ênfase 7º–10º (2027).
- Engenharia de Computação: tabela profissional 5º–13º (2012) + base comum
  1º–4º do ciclo básico disponível no Jupiterweb. O currículo atual aparece como
  `usp-poli-3123-3000.json`, gerado a partir da grade pública do Jupiterweb;
  ele é separado do alvo histórico 2012.
- MEC: USP é universidade pública; o ato de reconhecimento não foi consultado
  no e-MEC. O site mostra “ato não consultado” + “instituição pública”, não
  “não reconhecido”.

## Regenerar

```bash
# Os dois alvos manuais (EE AC 2027 e EC 2012)
python3 -I tools/extract_usp_poli.py

# As demais habilitações de engenharia com grade no catálogo
python3 -I tools/build_targets_from_catalog.py --only-usp
```

Os scripts usam apenas a biblioteca padrão e não leem históricos escolares. O
segundo preserva os alvos 3033/3201/3251 e o currículo antigo 3121.
