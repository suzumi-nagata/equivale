# Vetores de disciplinas

Índice pré-computado que o site baixa junto com as grades. O cálculo é local,
determinístico e não usa LLM nem chamadas de runtime.

## Arquivo

- [`cursos.json`](cursos.json) — vetores densos de disciplinas da UNICAMP e da
  USP, gerados a partir de `data/catalog` e das grades-alvo.

Cada documento tem instituição, código, nome, horas, origem do texto
(`ementa` ou `titulo`), URL da fonte e um vetor quantizado em `int8` codificado
em base64. O campo `dimensao` e `escala` permitem ao site decodificar e comparar
os vetores sem bibliotecas externas.

## Método

[`tools/build_course_embeddings.py`](../../tools/build_course_embeddings.py)
usa TF-IDF + **SVD truncado (LSA)**:

1. Normaliza português, remove stopwords gramaticais e aplica stemming simples.
2. Usa a ementa + objetivos + conteúdo quando existem; senão, usa o título.
3. Dá peso maior aos tokens do título e a bigramas do título.
4. Monta a matriz esparsa documento × termo com pesos TF-IDF e normaliza cada
   documento em L2.
5. Aproxima os `dimensao` principais componentes por **randomized SVD** com duas
   iterações de potência, implementado no próprio script. O NumPy é usado só
   para álgebra linear; não há modelo neural, API ou LLM.
6. Normaliza os vetores em L2 e os quantiza em `int8` (escala 127).

O método alternativo `--metodo hash` usa feature hashing determinístico com
BLAKE2b e não precisa de NumPy, mas é mais lexical e menos estável. O método
recomendado e o arquivo versionado usam LSA.

## Regenerar

```bash
# O método LSA precisa de NumPy apenas na regeneração:
python3 -m pip install -r requirements-embeddings.txt
python3 -I tools/build_course_embeddings.py

# Dimensão menor (arquivo menor, menos resolução):
python3 -I tools/build_course_embeddings.py --dimensao 96

# Alternativa sem NumPy (feature hashing):
python3 -I tools/build_course_embeddings.py --metodo hash
```

O `--seed` (default 42) e o `--iteracoes` (default 2) controlam o randomized
SVD. O JSON registra o método, a dimensão, a seed e a data no cabeçalho.

O script lê, nesta ordem:

- `data/catalog/unicamp_2026_disciplinas.json`
- `data/catalog/usp_jupiterweb_disciplinas.json`
- `data/spike/curriculos/*.json`
- `data/targets/unicamp/*.json`
- `data/targets/usp/*.json`

Disciplinas de grade sem ementa entram como vetor de título. Códigos sem
documento no catálogo também entram com o nome da grade, para não deixar o alvo
sem vetor.

## Uso no site

O `sync-data` copia o arquivo para `site/public/data/embeddings.json`. O matcher:

- procura o vetor do alvo por código (ou nome, para componentes sem código);
- procura o vetor da origem por código (ou nome);
- calcula similaridade de cosseno;
- adiciona uma aresta de cobertura quando o cosseno é >= 0.38, há token ou
  conceito específico compartilhado e as guardas de sequência e
  teoria/laboratório permitem;
- mantém a carga da origem como limite, exceto no modo opcional de ignorar
  carga horária;
- só adiciona pares que ainda não têm aresta de nome/regra (não substitui a
  cobertura existente);
- marca a alocação com `metodo: "vetor"` e registra um aviso no resultado.

O índice completo é baixado de forma assíncrona. Se ele faltar ou estiver
corrompido, o site continua funcionando com nome + regras de ementa.

## Limitações

- LSA em ementas curtas ainda é uma aproximação; aumentar `--dimensao` ou o
  corpus ajuda, mas não substitui leitura humana.
- TF-IDF não entende sinônimos que não aparecem nas ementas.
- O modo `hash` sofre colisões; o modo LSA é o recomendado.
- Ementas muito genéricas (laboratórios, introduções) podem gerar similaridade
  alta sem equivalência real; por isso o matcher mantém as guardas e a carga.
- A decisão final é da instituição de destino.
