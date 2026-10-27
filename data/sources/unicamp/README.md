# Currículos de origem — UNICAMP 2026

Dados públicos do **Catálogo dos Cursos de Graduação 2026** da UNICAMP (DAC),
usados para classificar disciplinas de origem como obrigatórias, eletivas ou
dependentes de habilitação/ênfase. Os JSONs desta pasta continuam sendo dados
de **origem**; a conversão para o schema de alvo do site fica em
[`data/targets/unicamp`](../../targets/unicamp/README.md) e é gerada pelo
script [`tools/build_unicamp_targets.py`](../../../tools/build_unicamp_targets.py).

## Arquivos

- [`eng_computacao_2026.json`](eng_computacao_2026.json) — curso 34G.
- [`eng_eletrica_2026.json`](eng_eletrica_2026.json) — curso 41G.
- [`../../../tools/extract_unicamp_2026.py`](../../../tools/extract_unicamp_2026.py) — extrator reprodutível.

## Fontes

- Catálogo 2026 — Engenharia de Computação (34G):
  <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/cursos/34g/curriculo.html>
- Catálogo 2026 — Engenharia Elétrica (41G):
  <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/cursos/41g/curriculo.html>
- Propostas para cumprimento de currículo:
  <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/cursos/34g/sugestao.html>
  e <https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/cursos/41g/sugestao.html>
- Certificados de Estudos da FEEC (PDF):
  <http://www.dac.unicamp.br/portal/storage/app/media/Certificado%20de%20Estudo/Certificado_de_Estudos_FEEC-Catalogo_2025.pdf>

Coleta: 2026-10-26.

## Habilitações e ênfases

### Engenharia de Computação (34G)

O currículo tem um **núcleo comum** e duas habilitações distintas:

- **AA — Sistemas de Computação:** 13 disciplinas obrigatórias da habilitação;
  grupos de eletivas com 13, 12, 12 e 12 créditos.
- **AB — Sistemas e Processos Industriais:** 20 disciplinas obrigatórias da
  habilitação; grupos de eletivas com 12 e 25 créditos.
- **AX — Para Matrícula Antes da Opção:** grade provisória para quem ainda não
  escolheu AA/AB. Não é uma terceira habilitação.

O JSON inclui os **6 certificados do IC** e os **13 certificados da FEEC**
(nomes e público-alvo); eles não são habilitações.

**AA e AB não devem ser somadas nem tratadas como a mesma grade.** O perfil de
Engenharia Elétrica com automação/controle tende a estar mais próximo de **AB**
(Sistemas e Processos Industriais), mas isso depende do currículo e da ênfase
concreta — o dado mantém as duas variantes separadas.

### Engenharia Elétrica (41G)

O currículo pleno 2026 **não define habilitações**. Ele tem o núcleo comum e
quatro grupos de eletivas (12, 2, 26 e 4 créditos). As ênfases/tracks aparecem
como **Certificados de Estudos da FEEC**, que não são habilitações.

Para o perfil de **Automação e Controle**, os certificados mais próximos são:

- **Sistemas de Controle**
- **Automação e Sistemas Inteligentes**

Outros certificados listados: Fundamentos da Engenharia de Computação,
Fundamentos da Engenharia Elétrica, Engenharia de Som, Telecomunicações e
Telemática, Sistemas de Energia Elétrica, Engenharia Biomédica, Sistemas
Distribuídos e Redes de Computadores, Otimização de Sistemas, Técnicas de
Projeto de Sistemas Embarcados, Eletrônica/Microeletrônica/Optoeletrônica e
Aplicações de Energia Elétrica.

## Estrutura do JSON

```json
{
  "instituicao": "UNICAMP",
  "curso": "Engenharia de Computação",
  "codigo_curso": "34G",
  "curriculo_versao": "2026",
  "fonte": "...",
  "proposta_fonte": "...",
  "coletado_em": "2026-10-26",
  "nucleo_comum": [
    {"codigo": "MA111", "codigo_normalizado": "MA111", "nome": "Cálculo I", "horas": 90, "creditos": 6, "tipo": "obrigatoria_comum"}
  ],
  "variantes": [
    {
      "codigo": "AA",
      "nome": "Sistemas de Computação",
      "tipo": "habilitacao",
      "obrigatorias": [],
      "eletivas": [
        {
          "grupo": "Eletivas I",
          "creditos_exigidos": 13,
          "disciplinas": [
            {"codigo": "EX---", "nome": "Qualquer disciplina ...", "horas": null, "creditos": null, "tipo": "eletiva_livre"}
          ]
        }
      ]
    }
  ],
  "certificados": []
}
```

Classificação usada:

- `obrigatoria_comum`: núcleo comum.
- `obrigatoria_habilitacao`: obrigatória de uma habilitação específica.
- `eletiva`: disciplina de um grupo de eletivas.
- `eletiva_livre`: regra de prefixo (`EX---`, `MX---`, `IX---`) — qualquer
  disciplina da UNICAMP que atenda ao prefixo/regra.
- `creditos_exigidos`: créditos que o grupo exige; não é a carga de uma
  disciplina única.
- `certificados`: **nomes** de certificados/trilhas, não habilitações; os
  requisitos completos não foram extraídos neste passo.

## Uso no projeto

Estes dados são para o **lado de origem** do matching:

- classificar disciplinas do histórico como obrigatórias, eletivas ou de
  habilitação/ênfase;
- alimentar a ontologia e o modelo m-para-n;
- comparar um histórico com variantes específicas (ex.: EC AA vs. EC AB), sem
  misturar as grades.

O site lê os alvos convertidos de `data/targets/unicamp` além dos currículos
UNINTER de `data/spike/curriculos`. Estes JSONs de origem não são servidos
diretamente no seletor de alvo; a conversão preserva a separação AA/AB e trata
os grupos de eletivas como requisitos de crédito.

## Regenerar

```bash
python3 -I tools/extract_unicamp_2026.py
# ou, usando HTMLs já baixados:
python3 -I tools/extract_unicamp_2026.py --html-dir /tmp/unicamp-curriculos

# converte as variantes AA/AB e o currículo 41G para alvos do site:
python3 -I tools/build_unicamp_targets.py
```

O extrator usa somente a biblioteca padrão e registra a URL de cada página.

## Limitações

- **Versão 2026:** históricos antigos podem ter sido cumpridos sob outro
  catálogo; a classificação é específica da versão.
- **MEC:** o catálogo é oficial e a UNICAMP é universidade pública, mas o ato de
  reconhecimento não foi consultado no e-MEC; a UI mostra “ato não consultado”,
  não “não reconhecido”.
- Grupos de eletivas são requisitos de crédito, não slots fixos de 45h.
- Os certificados tiveram apenas os nomes extraídos; a lista completa de
  disciplinas de cada certificado está no PDF da FEEC e pode ser adicionada
  depois.
- Dados públicos; nenhum histórico ou identificador pessoal.
