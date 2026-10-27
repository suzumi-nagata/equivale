# Catálogo de disciplinas e ementas

Dados públicos extraídos **uma vez** pelos scripts de crawl e usados para gerar
as regras de cobertura e os vetores de ementa. O crawler não infere
equivalências, não lê históricos e não usa LLM.

## Arquivos

- [`unicamp_2026_disciplinas.json`](unicamp_2026_disciplinas.json) — todas as
  disciplinas das páginas de letras do Catálogo dos Cursos de Graduação 2026 da
  UNICAMP (DAC), com código, nome, horas, créditos, período de oferecimento,
  pré-requisitos, ementa e URL da fonte.
- [`usp_jupiterweb_disciplinas.json`](usp_jupiterweb_disciplinas.json) —
  disciplinas ativas/inativas da Poli-USP e códigos citados nas grades-alvo da
  USP no Jupiterweb, com ementa, objetivos, conteúdo programático, créditos e
  URL da fonte.

Cada arquivo tem `schema_version`, `coletado_em`, contagens (`total`,
`com_ementa`, `sem_ementa`) e `hash_disciplinas` para verificar a integridade
do conteúdo. A ausência de ementa não remove a disciplina: o gerador de
embeddings cai para o título.

## Fontes

- UNICAMP: <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/>
- USP: <https://uspdigital.usp.br/jupiterweb/jupDisciplinaBusca?tipo=D&codmnu=6755>
- Cada registro contém a URL exata da página de origem.

## Crawler

[`tools/crawl_catalogos.py`](../../tools/crawl_catalogos.py) usa apenas a
biblioteca padrão. Ele:

- descobre as páginas de letras da UNICAMP a partir do índice oficial;
- descobre as unidades e as páginas de disciplinas no Jupiterweb;
- inclui os códigos citados em `data/targets/usp`, mesmo quando a disciplina é
  de outra unidade da USP;
- mantém cache HTTP persistente, com `ETag`/`Last-Modified`, retry e fallback
  para a última resposta válida;
- retoma de onde parou e grava os JSONs de forma atômica.

O cache fica fora do repositório, por padrão em
`~/.cache/equivale/crawler`. Ele não é versionado; os JSONs extraídos são.

### Comandos

```bash
# Catálogo completo (UNICAMP + Poli-USP + códigos das grades-alvo)
python3 -I tools/crawl_catalogos.py

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
- A USP usa a lista da Poli mais os códigos das grades-alvo; uma disciplina de
  outra unidade que não apareça nessas grades não é coletada por padrão.
- A ementa publicada pode estar desatualizada em relação ao PPC vigente.
- O crawler não decide equivalência; ele apenas coleta o que a instituição
  publica.
