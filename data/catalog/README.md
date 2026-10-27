# Catálogo de cursos, disciplinas e ementas

Dados públicos extraídos **uma vez** pelo crawler e usados para gerar regras de
cobertura, vetores de ementa e, no futuro, novos cursos-alvo. O crawler não
infere equivalências, não lê históricos e não usa LLM.

## Arquivos

Cursos e seus currículos:

- [`unicamp_2026_cursos.json`](unicamp_2026_cursos.json) — **66 cursos** do
  Catálogo 2026 da UNICAMP, com metadados, currículo pleno e proposta de
  cumprimento por habilitação.
- [`usp_jupiterweb_cursos.json`](usp_jupiterweb_cursos.json) — **23 cursos e
  habilitações** da Poli-USP; 20 com grade curricular publicada no Jupiterweb.

Disciplinas e ementas:

- [`unicamp_2026_disciplinas.json`](unicamp_2026_disciplinas.json) — todas as
  disciplinas das páginas de letras do Catálogo 2026 da UNICAMP (DAC), com
  código, nome, horas, créditos, período de oferecimento, pré-requisitos,
  ementa e URL da fonte.
- [`usp_jupiterweb_disciplinas.json`](usp_jupiterweb_disciplinas.json) —
  disciplinas ativas/inativas da Poli-USP e códigos citados nas grades-alvo da
  USP no Jupiterweb, com ementa, objetivos, conteúdo programático, créditos e
  URL da fonte.

Cada arquivo tem `schema_version`, `coletado_em`, contagens e hash de
integridade. Nos catálogos de disciplinas as contagens são `com_ementa` e
`sem_ementa`; nos de cursos são `com_grade`. A ausência de ementa não remove a
disciplina: o gerador de embeddings cai para o título. Curso e disciplina são
coisas diferentes: um curso-alvo precisa de grade completa; uma disciplina
isolada pode não ter currículo associado.

O catálogo de cursos é a base para novos alvos. O seletor do site continua
mostrando apenas os cursos convertidos e auditados em `data/targets/`; os 66 +
23 cursos deste diretório ainda não são todos alvos do site.

## Fontes

- UNICAMP, cursos: <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/>
- UNICAMP, disciplinas: <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/>
- USP, cursos e grades: <https://uspdigital.usp.br/jupiterweb/jupCarreira.jsp?codmnu=8275>
- USP, disciplinas: <https://uspdigital.usp.br/jupiterweb/jupDisciplinaBusca?tipo=D&codmnu=6755>
- Cada registro contém a URL exata da página de origem.

## Crawler

[`tools/crawl_catalogos.py`](../../tools/crawl_catalogos.py) usa apenas a
biblioteca padrão. Ele:

- descobre os cursos e as páginas de letras da UNICAMP a partir do índice
  oficial;
- descobre as unidades, cursos/habilitações e disciplinas no Jupiterweb;
- coleta currículo pleno e proposta de cumprimento dos cursos da UNICAMP;
- coleta a grade curricular dos cursos/habilitações da USP;
- inclui os códigos citados em `data/targets/usp`, mesmo quando a disciplina é
  de outra unidade da USP;
- mantém cache HTTP persistente, com `ETag`/`Last-Modified`, retry e fallback
  para a última resposta válida;
- retoma de onde parou e grava os JSONs de forma atômica.

O cache fica fora do repositório, por padrão em
`~/.cache/equivale/crawler`. Ele não é versionado; os JSONs extraídos são.

### Comandos

```bash
# Cursos + disciplinas (UNICAMP + Poli-USP + códigos das grades-alvo)
python3 -I tools/crawl_catalogos.py

# Só cursos/currículos
python3 -I tools/crawl_catalogos.py --no-disciplinas

# Só disciplinas/ementas
python3 -I tools/crawl_catalogos.py --no-cursos

# Só a UNICAMP
python3 -I tools/crawl_catalogos.py --scope unicamp

# Só a USP
python3 -I tools/crawl_catalogos.py --scope usp --usp-scope poli

# Todas as unidades da USP (pode demorar; use em uma máquina/sessão longa)
python3 -I tools/crawl_catalogos.py --scope usp --usp-scope all

# Revalidar tudo, ignorando a idade do cache
python3 -I tools/crawl_catalogos.py --refresh

# Reparsear sem rede (cache obrigatório)
python3 -I tools/crawl_catalogos.py --offline
```

O `--delay` (default 0.15s) controla a pausa entre requisições. O `--cache-dir`
permite apontar para outro diretório. Em caso de falha de rede, o crawler usa a
última cópia em cache e avisa no stderr; sem cache, a página é registrada como
falha e o restante continua.

### Validação

Os parsers têm testes sintéticos:

```bash
python3 -I -m unittest discover -s tools -p 'test_*.py' -v
```

Eles não acessam a rede. A coleta real é validada pelas contagens de
`com_ementa` e `sem_ementa` no JSON e pelo `hash_disciplinas`.

## Como atualizar

1. Rode o crawler com `--refresh` quando quiser buscar mudanças no catálogo.
2. Revise o diff dos JSONs; códigos novos/removidos são visíveis.
3. Regenere os vetores:

   ```bash
   python3 -I tools/build_course_embeddings.py
   ```

4. Rode os testes Python e do site.
5. Commite `data/catalog`, `data/embeddings` e os arquivos de ontologia
   alterados. O cache HTTP não entra no commit.

## Limitações

- O catálogo da UNICAMP é uma fotografia do ano letivo 2026; disciplinas antigas
  podem não estar nele.
- A USP usa a lista da Poli mais os códigos das grades-alvo; uma disciplina ou
  curso de outra unidade que não apareça nessas grades não é coletado por
  padrão. Use `--usp-scope all` para varrer todas as unidades.
- Alguns cursos/habilitações da USP não têm grade publicada na página
  consultada; eles entram com `grade_disponivel: false` para não sumirem do
  catálogo. Em algumas habilitações o Jupiterweb devolve apenas o ciclo básico;
  o campo `grade_disponivel` não garante que todos os períodos da ênfase
  estejam presentes.
- A proposta de cumprimento é uma sugestão da instituição, não uma regra
  obrigatória.
- A ementa publicada pode estar desatualizada em relação ao PPC vigente.
- O crawler não decide equivalência; ele apenas coleta o que a instituição
  publica.
