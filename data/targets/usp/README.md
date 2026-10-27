# Currículos-alvo — Poli-USP

Dados públicos do Jupiterweb (USP) usados como alvos de comparação. A coleta
foi feita em 2026-10-27; a grade pode mudar.

## Arquivos

- [`usp-poli-ee-ac-2027.json`](usp-poli-ee-ac-2027.json) — Engenharia Elétrica,
  ênfase **Automação e Controle**, ciclo básico + ênfase.
- [`usp-poli-ec-2012.json`](usp-poli-ec-2012.json) — Engenharia de Computação,
  currículo **2012** (tabela disponível no Jupiterweb).

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
  1º–4º do ciclo básico disponível no Jupiterweb. O currículo atual
  (3122/3000) tem resumo público, mas a tabela de disciplinas não estava
  disponível na página consultada.
- MEC: USP é universidade pública; o ato de reconhecimento não foi consultado
  no e-MEC. O site mostra “ato não consultado” + “instituição pública”, não
  “não reconhecido”.

## Regenerar

```bash
python3 -I tools/extract_usp_poli.py
# ou usando páginas já baixadas:
python3 -I tools/extract_usp_poli.py --html-dir /tmp/usp-poli-cache
```

O script usa apenas a biblioteca padrão. Ele não lê históricos escolares.
