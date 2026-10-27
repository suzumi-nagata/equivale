# Spike de dados — privadas EAD (computação)

**Data da coleta:** 2026-10-26  
**Escopo:** cursos de graduação em computação (Ciência da Computação, Engenharia de Software e ADS) em IES privadas, modalidade EAD, para o caso de segunda graduação/concursos.  
**Arquivos:** [`cursos.json`](cursos.json), [`curriculos/uninter_ads.json`](curriculos/uninter_ads.json) e [`curriculos/uninter_eng_software.json`](curriculos/uninter_eng_software.json).

## Método

- 5 IES foco: **UNINTER, Anhanguera, Estácio, Cruzeiro do Sul Virtual e UNIP**.
- Prioridade para páginas oficiais; dados de fontes secundárias (buscas, blogs, agregadores) estão marcados.
- O portal de dados abertos do MEC e o CSV direto retornaram **HTTP 403 (Cloudflare)** neste ambiente, tanto via WebFetch quanto via curl. Não contornamos o bloqueio. O status MEC foi registrado quando a página oficial trazia portaria/ato; caso contrário, ficou como `nao_verificado`.
- Nenhum histórico escolar ou dado pessoal foi usado neste spike.

## Matriz das 5 IES foco

### UNINTER

| Curso | Grau | Duração | CH | Status MEC (página) | Grade | PPC/ementa | Ingresso/2ª grad. | Preço | Completude |
|---|---|---:|---:|---|---|---|---|---|---|
| Tecnologia em ADS | Tecnólogo | 30 meses | 2.035h | Reconhecido — Portaria 155/2023; CPC 3; Nota MEC 4 | **Sim, com CH** | Não | 2ª graduação; regra de dispensa não detalhada | Dinâmico (R$ XXX) | `grade_com_ch` |
| Bacharelado em Eng. Software | Bacharelado | 48 meses | 3.210h | Reconhecido — Portaria SERES 562/2025; Nota MEC 4 | **Sim, com CH** | Não | idem | Dinâmico (R$ XXX) | `grade_com_ch` |
| Bacharelado em CC | Bacharelado | 48 meses | 3.210h | **Aguarda reconhecimento MEC** | Sim, com CH | Não | idem | Dinâmico (R$ XXX) | `grade_com_ch` |

**Leitura:** é a única IES do recorte com grade completa e carga horária pública nos três cursos. O ponto negativo é a ausência de PPC/ementa e o **risco de reconhecimento no CC** — para concurso, ADS ou Eng. Software são mais seguros.

### Anhanguera

| Curso | Grau | Duração | CH | Status MEC (página) | Grade | PPC/ementa | Ingresso/2ª grad. | Preço | Completude |
|---|---|---:|---:|---|---|---|---|---|---|
| ADS | Tecnólogo | 2,5 anos / 5 sem. | ~2.000h | Reconhecido (sem portaria na página) | Não | Não | **2ª graduação sem vestibular**, com aproveitamento de créditos | Não público; indício R$ 108–118 | `so_marketing` |
| CC | Bacharelado | 8 semestres | — | Reconhecido (sem portaria; blog cita CC 4/CPC 3/Enade 2) | Não | Não | Política institucional indica 2ª grad. sem vestibular; confirmar para CC | Indício R$ 118,01 | `so_marketing` |

**Leitura:** é o melhor lead para o critério **“não exige vestibular”**, porque a página oficial de ADS declara explicitamente a segunda graduação sem vestibular com aproveitamento de créditos. Em compensação, **não publica grade, PPC nem ementa**; a estimativa de equivalência exigiria obter o PPC por outro canal.

### Estácio

| Curso | Grau | Duração | CH | Status MEC (página) | Grade | PPC/ementa | Ingresso/2ª grad. | Preço | Completude |
|---|---|---:|---:|---|---|---|---|---|---|
| ADS | Tecnólogo | 30 meses* | 2.080h* | Não verificado (só link e-MEC) | Não na página oficial | Não | Simplificado, ENEM, Transferência, 2ª Graduação | Indício R$ 129 | `so_marketing` |

\* duração, CH e 30 disciplinas aparecem em fontes secundárias; a página oficial não exibiu esses dados na leitura automatizada.

**Leitura:** o curso é rápido e barato, mas a grade oficial fica no SIA/portal do aluno e não há PPC/ementa público. Para o MVP, entraria como “rota rápida com dados insuficientes”.

### Cruzeiro do Sul Virtual

| Curso | Grau | Duração | CH | Status MEC (página) | Grade | PPC/ementa | Ingresso/2ª grad. | Preço | Completude |
|---|---|---:|---:|---|---|---|---|---|---|
| ADS | Tecnólogo | 4 semestres* | — | Não verificado; snippet indica MEC 4 / ENADE 3 | Não (página 403) | Não | Início imediato* | Não verificado | `minimo` |

\* dados de snippet de busca; a página oficial bloqueou leitura automatizada (HTTP 403).

**Leitura:** é o lead de **maior velocidade** (4 semestres), com momentos presenciais obrigatórios. A falta de acesso à página impede confirmar grade, ingresso e preço; é um candidato para contato/verificação manual.

### UNIP

| Curso | Grau | Duração | CH | Status MEC (página) | Grade | PPC/ementa | Ingresso/2ª grad. | Preço | Completude |
|---|---|---:|---:|---|---|---|---|---|---|
| ADS | Tecnólogo | 2,5 anos | — | Reconhecido — Portaria 155/2023 | Não na página | PPC nos polos, não online | Vestibular on-line, ENEM, Transferência, 2ª Graduação | Não encontrado | `so_marketing` |

**Leitura:** o status MEC é explícito, mas a grade e o PPC não estão online; a própria página diz que o PPC está disponível nos polos, atendimento e bibliotecas. É o caso típico de “dado oficial existe, mas não é público na web”.

## Complementares investigados

- **UNICESUMAR:** não tem CC EAD; tem **ADS EAD (30 meses)** e **Eng. Software EAD (4 anos)**, mas a página não publica grade/CH. Existe **PPC presencial com ementas**, não o PPC EAD. O status é divulgado como “nota máxima no MEC”, sem portaria na página.
- **Multivix:** CC EAD (bacharelado, 4 anos/8 períodos) com **grade pública apenas por nomes, sem CH**; sem PPC/ementa. A página lista “Segunda Graduação ou novo curso” e “Análise do Histórico Escolar” entre as formas de ingresso.
- **Facunicamps:** resultados de busca indicam matriz de CC EAD em PDF público com CH, mas o download não foi concluído e a instituição/curso não foi verificada com segurança neste spike; fica como lead para uma próxima rodada.

## Achados principais

1. **ADS é o caminho mais rápido.** As ofertas do recorte ficam entre **24 e 30 meses**: UNINTER 30m/2.035h, Anhanguera 2,5 anos/~2.000h, Estácio 30m/2.080h (secundário), Cruzeiro 4 semestres, UNIP 2,5 anos. Para um edital que aceite “curso superior em TI” ou tecnólogo, ADS é a rota mais curta.
2. **Tecnólogo ≠ bacharelado.** Se o edital exigir “Ciência da Computação” ou “bacharelado”, ADS não atende. O site precisa de `grau` e `nome_exato` como **filtros duros**, não como pontuação.
3. **Grade pública é exceção.** Só a UNINTER publica grade completa com CH nos três cursos; a Multivix publica nomes sem CH; UNIP e UNICESUMAR deixam o PPC nos polos/presencial; Estácio, Anhanguera e Cruzeiro não publicam grade/PPC/ementa na página do curso.
4. **Ementa é o gargalo.** Nenhuma das cinco IES foco publica ementas online. A UNICESUMAR tem PPC presencial com ementas, mas não o EAD. Sem ementa, o matching cai para nome + carga, com confiança menor.
5. **Segunda graduação sem vestibular: só a Anhanguera declara explicitamente.** UNINTER, UNIP e Estácio listam “2ª Graduação”, mas não detalham dispensa de vestibular. É um campo a confirmar por instituição/curso.
6. **Status MEC não é padronizado.** UNIP e UNINTER mostram portarias; a UNINTER CC está **aguardando reconhecimento** (risco para concurso); a Anhanguera afirma “reconhecido” sem portaria; Estácio, Cruzeiro e UNICESUMAR não exibem ato. O e-MEC em bulk está bloqueado por Cloudflare; a verificação precisa ser manual/CI.
7. **Preço não é dado estático.** As páginas usam cotação dinâmica por polo/campanha. Os valores “a partir de” (Anhanguera R$ 108–118; Estácio R$ 129) são indícios secundários, não preço final.
8. **Nenhum curso combina todos os critérios.** Não há, no recorte, um curso simultaneamente rápido, reconhecido, com grade+CH, PPC/ementa público e ingresso sem vestibular. O MVP terá que lidar com dados parciais e mostrar confiança.

## Implicações para o MVP

- **Seed com UNINTER ADS e Eng. Software.** São as únicas com grade completa + CH; servem para construir e validar o motor de matching. O CC da UNINTER entra com aviso de reconhecimento pendente.
- **Anhanguera ADS como lead de ingresso.** É o caso que atende “segunda graduação sem vestibular”; a grade/PPC precisa ser obtida manualmente ou via upload local.
- **Estácio e Cruzeiro ADS como rotas rápidas.** Entram no ranking, mas marcadas como `dados insuficientes` até haver grade/PPC; não podem ser apresentadas como “mais fáceis” sem essa ressalva.
- **Upload local de PPC/ementa.** Como as instituições não publicam ementas, o site deve permitir que o usuário baixe o PPC/ementa no polo/portal e o carregue **localmente** para extração. Isso resolve o gargalo sem backend e mantém a privacidade. O parser de PPC é uma peça separada do parser de histórico.
- **Filtros duros de edital.** `grau` (tecnólogo/bacharelado), `nome_exato`, área CINE e status MEC reconhecido. O ranking só compara o que passou.
- **Confiança no ranking.** Cada curso exibe `completude` (`grade_com_ch`, `grade_sem_ch`, `so_marketing`, `minimo`). Curso com dados só de marketing não pode ser ranqueado como “mais fácil”.
- **Verificação MEC.** Link para o e-MEC por curso; não usar “nota máxima” como prova de reconhecimento. Para o pipeline, tentar o download oficial via navegador/CI ou usar mirror de dados abertos.
- **Preço.** Fora do MVP ou como campo opcional com fonte/data e rótulo “a partir de”; não usar como critério principal sem verificação.

## Próximos passos do spike

1. Verificar no e-MEC o status/ato de cada curso foco (manual ou download oficial em ambiente com navegador).
2. Obter PPC/grade de **Anhanguera ADS**, **Estácio ADS**, **Cruzeiro ADS** e **UNIP ADS** por canal oficial/polo.
3. Confirmar as regras de **2ª graduação/aproveitamento** (limite, nota mínima, validade, procedimento).
4. Montar o seed dataset: UNINTER ADS + Eng. Software (grades completas) e Anhanguera ADS (ingresso).
5. Desenhar o fluxo de **upload local de PPC/ementa** e o extrator de ementas.

## Limitações

- “Não encontrado” não significa que o dado não exista; muitas páginas são dinâmicas, exigem portal do aluno ou atendimento no polo.
- Páginas e ofertas mudam; a data de coleta é 2026-10-26.
- Dados de Cruzeiro e parte de Estácio/Anhanguera vêm de snippets/buscas e estão marcados.
- O status MEC das páginas não substitui a consulta oficial ao e-MEC.
- Nenhum dado pessoal foi coletado.

## Fontes

- UNINTER — ADS EAD: <https://www.uninter.com/graduacao/a-distancia/tecnologia-em-analise-e-desenvolvimento-de-sistemas/>
- UNINTER — Engenharia de Software EAD: <https://www.uninter.com/graduacao/a-distancia/bacharelado-em-engenharia-de-software/>
- UNINTER — Ciência da Computação EAD: <https://www.uninter.com/graduacao/a-distancia/bacharelado-em-ciencia-da-computacao/>
- Anhanguera — ADS: <https://www.anhanguera.com/curso/analise_e_desenvolvimento_de_sistemas/>
- Anhanguera — CC EAD (blog): <https://blog.anhanguera.com/ciencia-da-computacao-ead/>
- Anhanguera — nota MEC do CC: <https://blog.anhanguera.com/nota-curso-de-ciencia-computacao-anhanguera/>
- Anhanguera — nota MEC do ADS: <https://blog.anhanguera.com/nota-curso-analise-desenvolvimento-sistemas-anhanguera-mec/>
- Estácio — ADS: <https://estacio.br/cursos/graduacao/analise-e-desenvolvimento-de-sistemas>
- Cruzeiro do Sul Virtual — ADS EAD: <https://cursos.cruzeirodosulvirtual.com.br/grad-analise-e-desenvolvimento-de-sistemas-cruzeiro-do-sul-virtual/p>
- UNIP — ADS EAD: <https://www.unip.br/cursos/graduacao/tecnologicos/analise_desenvolvimento_sistemas.aspx>
- UNIP — CC EAD: <https://www.unip.br/cursos/graduacao/tradicionais/ciencia_computacao.aspx>
- UNICESUMAR — ADS EAD: <https://www.unicesumar.edu.br/cursos/graduacao/tecnologo-em-analise-e-desenvolvimento-de-sistemas/ead/>
- UNICESUMAR — Eng. Software EAD: <https://inscricoes.unicesumar.edu.br/curso/engenharia-de-software>
- Multivix — CC EAD: <https://multivix.edu.br/graduacao-ead/ciencia-da-computacao/>
- e-MEC: <https://emec.mec.gov.br/>
- Dados Abertos MEC: <https://dadosabertos.mec.gov.br/> (403 neste ambiente)
