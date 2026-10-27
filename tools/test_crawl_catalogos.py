from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import crawl_catalogos as crawler  # noqa: E402


UNICAMP_FIXTURE = """
<html><body>
<div id="disc-f_328">
  F 328 - Física Geral III
  Coordenadoria Comissão de Graduação
  Total de Horas de Atividades Teóricas: 45
  Total de Horas de Atividades Práticas: 15
  Total de Horas de Laboratório: 0
  Total de Créditos: 4
  Período de Oferecimento Todos os períodos
  Avaliação Nota e Frequência
  Pré-requisitos F 128
  Ementa Eletromagnetismo, circuitos elétricos e ondas.
  Bibliografia Referências públicas.
</div>
<div id="disc-be310">
  BE310 - Ciências do Ambiente
  Coordenadoria Comissão de Graduação
  Total de Horas/Aula Realizadas em Sala de Aula: 30
  Total de Créditos: 2
  Período de Oferecimento Todos os períodos
  Avaliação Nota e Frequência
  Ementa População humana, energia e sustentabilidade.
  Bibliografia Referências públicas.
</div>
</body></html>
"""


USP_FIXTURE = """
<html><body>
Júpiter - Sistema de Gestão Acadêmica da Pró-Reitoria de Graduação
Escola Politécnica
Engenharia de Computação
Disciplina: PCS3110 - Algoritmos e Estruturas de Dados
Algorithms and Data Structures
Créditos Aula: 4
Créditos Trabalho: 0
Carga Horária Total: 60 h
Tipo: Semestral
Ativação: 01/01/2025
Desativação:
Ementa Conceitos de algoritmos e estruturas de dados.
Conceitos em inglês.
Objetivos Fornecer capacidade de análise.
Conteúdo Programático Programa: 1. Histórico. 2. Grafos.
Bibliografia Referências públicas.
</body></html>
"""


COURSE_ROOT_FIXTURE = """
<html><body>
<a href="./cursos/99g/index.html">Curso 99</a>
<a href="./cursos/99g/curriculo.html">Currículo</a>
<a href="./cursos/99g/sugestao.html">Proposta</a>
<a href="./cursos/99g/membros.html">Membros</a>
</body></html>
"""

COURSE_INDEX_FIXTURE = """
<html><body>
<h1>Catálogo dos Cursos de Graduação - UNICAMP - 2026</h1>
<h1>Curso 99 - Curso de Teste</h1>
<li><a href="../../cursos/99g/membros.html">Instituto de Teste - Membros da Comissão</a></li>
<h2>Turno: Integral</h2>
<h3>AA - Bacharelado em Teste</h3>
<h3>AB - Licenciatura em Teste</h3>
</body></html>
"""

COURSE_CURRICULUM_FIXTURE = """
<html><body>
<h2>99 - Curso de Teste - Currículo Pleno</h2>
<h3>Núcleo Comum ao Curso</h3>
<table>
<tr><td>AA001</td><td>60</td><td>4</td><td>Disciplina Comum</td></tr>
</table>
<h2>AB - Licenciatura em Teste</h2>
<h3>Disciplinas Obrigatórias</h3>
<table>
<tr><td>AB001</td><td>30</td><td>2</td><td>Disciplina da Habilitação</td></tr>
</table>
<h3>Disciplinas Eletivas</h3>
<p>Disciplinas eletivas I: 2 créditos</p>
<table>
<tr><td>EX---</td><td>30</td><td>2</td><td>Qualquer disciplina</td></tr>
</table>
</body></html>
"""

COURSE_PROPOSAL_FIXTURE = """
<html><body>
<h1>Curso 99G - Curso de Teste - Proposta para Cumprimento de Currículo</h1>
<h2>AA - Bacharelado em Teste</h2>
<h3>1º Semestre - 4 créditos</h3>
<p>AA001 (4) e 2 créditos eletivos</p>
<h2>AB - Licenciatura em Teste</h2>
<h3>1º Semestre - 6 créditos</h3>
<p>AA001 (4) e AB001 (2)</p>
</body></html>
"""

USP_COURSE_LIST_FIXTURE = """
<html><body><table>
<tr><td>3033 0</td><td>Ciclo Básico - Engenharia Elétrica</td><td>integral</td>
<td><a href="listarGradeCurricular?codcg=3&codcur=3033&codhab=0&tipo=N">grade</a></td></tr>
<tr><td>3033 3150</td><td>Habilitação: Automação e Controle</td><td>integral</td>
<td><a href="listarGradeCurricular?codcg=3&codcur=3033&codhab=3150&tipo=N">grade</a></td></tr>
</table></body></html>
"""

USP_COURSE_GRADE_FIXTURE = """
<html><body>
<h1>Grade Curricular</h1>
Curso: Engenharia Curso: Ciclo Básico - Engenharia Elétrica
Data de Início: 01/01/2027
Duração Ideal 10 semestres Mínima 8 semestres Máxima 15 semestres
<table>
<tr><td>Disciplinas Obrigatórias</td></tr>
<tr><td>1º Período Ideal</td></tr>
<tr><td>ABC123</td><td>Disciplina de Teste</td><td>4</td><td>0</td><td>60</td></tr>
</table>
</body></html>
"""


class UnicampCourseCrawlerTest(unittest.TestCase):
    def test_discovers_course_pages(self) -> None:
        links = crawler.unicamp_course_links(COURSE_ROOT_FIXTURE)
        self.assertEqual(list(links), ["99G"])
        self.assertTrue(links["99G"].endswith("/cursos/99g/index.html"))

    def test_parses_course_metadata(self) -> None:
        metadata = crawler.parse_unicamp_course_index(
            COURSE_INDEX_FIXTURE,
            "99G",
            "https://example.test/cursos/99g/index.html",
        )
        self.assertEqual(metadata["nome"], "Curso de Teste")
        self.assertEqual(metadata["unidade"], "Instituto de Teste")
        self.assertEqual(metadata["turno"], "Integral")
        self.assertEqual(
            [item["codigo"] for item in metadata["habilitacoes"]], ["AA", "AB"]
        )

    def test_parses_curriculum_and_proposal(self) -> None:
        groups = crawler.parse_unicamp_curriculum(COURSE_CURRICULUM_FIXTURE)
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0]["tipo"], "obrigatoria_comum")
        self.assertEqual(groups[0]["disciplinas"][0]["codigo"], "AA001")
        self.assertEqual(groups[1]["tipo"], "obrigatoria_habilitacao")
        self.assertEqual(groups[2]["tipo"], "eletiva")

        proposal = crawler.parse_unicamp_proposal(COURSE_PROPOSAL_FIXTURE)
        self.assertEqual([item["codigo"] for item in proposal], ["AA", "AB"])
        self.assertEqual(proposal[0]["semestres"][0]["creditos"], 4)
        self.assertEqual(
            [item["codigo"] for item in proposal[0]["semestres"][0]["itens"]],
            ["AA001", "ELETIVA"],
        )


class UspCourseCrawlerTest(unittest.TestCase):
    def test_parses_course_rows(self) -> None:
        rows = crawler.parse_usp_course_rows(
            USP_COURSE_LIST_FIXTURE, "3", "Escola Politécnica"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["codcur"], "3033")
        self.assertEqual(rows[0]["codhab"], "0")
        self.assertEqual(rows[1]["curso"], "Habilitação: Automação e Controle")

    def test_parses_grade_metadata(self) -> None:
        row = crawler.parse_usp_course_rows(
            USP_COURSE_LIST_FIXTURE, "3", "Escola Politécnica"
        )[0]
        metadata = crawler.parse_usp_course_metadata(USP_COURSE_GRADE_FIXTURE, row)
        self.assertTrue(metadata["grade_disponivel"])
        self.assertEqual(metadata["carga_horaria_total"], 60)
        self.assertEqual(metadata["duracao_ideal_semestres"], 10)
        self.assertEqual(metadata["grade"][0]["codigo"], "ABC123")


class UnicampCrawlerTest(unittest.TestCase):
    def test_discovers_letter_pages(self) -> None:
        html = """
        <a href="../disciplinas/index.html">índice</a>
        <a href="../disciplinas/ac.html">AC</a>
        <a href="../disciplinas/f_.html">F</a>
        """
        self.assertEqual(
            [url.rsplit("/", 1)[-1] for url in crawler.unicamp_letter_urls(html)],
            ["ac.html", "f_.html"],
        )

    def test_parses_codes_names_hours_and_ementa(self) -> None:
        docs = crawler.parse_unicamp_page(
            UNICAMP_FIXTURE,
            "https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/f_.html",
        )
        self.assertEqual([doc["codigo"] for doc in docs], ["F 328", "BE310"])
        f328 = docs[0]
        self.assertEqual(f328["nome"], "Física Geral III")
        self.assertEqual(f328["horas"], 60)
        self.assertEqual(f328["horas_teoricas"], 45)
        self.assertEqual(f328["pre_requisitos"], "F 128")
        self.assertIn("Eletromagnetismo", f328["ementa"])
        self.assertTrue(f328["fonte"].endswith("#disc-f_328"))
        self.assertEqual(docs[1]["codigo"], "BE310")
        self.assertEqual(docs[1]["horas"], 30)


class UspCrawlerTest(unittest.TestCase):
    def test_parses_discipline_page(self) -> None:
        doc = crawler.parse_usp_page(
            USP_FIXTURE,
            "https://uspdigital.usp.br/jupiterweb/obterDisciplina?sgldis=PCS3110",
        )
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc["codigo"], "PCS3110")
        self.assertIn("Algoritmos", doc["nome"])
        self.assertEqual(doc["horas"], 60)
        self.assertEqual(doc["creditos_aula"], 4)
        self.assertEqual(doc["ementa"], "Conceitos de algoritmos e estruturas de dados. Conceitos em inglês.")
        self.assertIn("Fornecer", doc["objetivos"] or "")
        self.assertIn("Grafos", doc["conteudo"] or "")

    def test_rejects_pages_without_discipline_header(self) -> None:
        self.assertIsNone(crawler.parse_usp_page("<html>Sem disciplina</html>", "https://example.test"))

    def test_discovers_units_and_codes(self) -> None:
        units_html = """
        <a href="jupColegiadoMenu.jsp?codcg=3&amp;tipo=D&amp;nomclg=Escola+Polit%C3%A9cnica">
          Escola Politécnica
        </a>
        <a href="jupColegiadoMenu.jsp?codcg=7&tipo=D">Outra unidade</a>
        """
        units = crawler.parse_usp_units(units_html)
        self.assertEqual([unit["codcg"] for unit in units], ["3", "7"])
        self.assertEqual(units[0]["nome"], "Escola Politécnica")

        list_html = """
        <A HREF=jupDisciplinaLista?codcg=3&letra=A-B&tipo=D class="link_gray">[A-B]</A>
        <a href="obterDisciplina?sgldis=PRO3510&amp;verdis=2">PRO3510</a>
        <a href="obterDisciplina?sgldis=PRO3510&amp;verdis=2">duplicado</a>
        <a href="obterDisciplina?sgldis=PCS3110&amp;verdis=1">PCS3110</a>
        """
        self.assertEqual(
            [url.split("letra=")[1].split("&")[0] for url in crawler.parse_usp_letter_urls(list_html)],
            ["A-B"],
        )
        self.assertEqual(crawler.parse_usp_codes(list_html), ["PCS3110", "PRO3510"])


class OutputTest(unittest.TestCase):
    def test_payload_counts_and_hash(self) -> None:
        disciplines = [
            {"codigo": "A1", "nome": "A", "ementa": "conteúdo"},
            {"codigo": "B2", "nome": "B", "ementa": ""},
        ]
        payload = crawler.catalog_payload("X", "Catálogo", "https://example.test", "teste", disciplines)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["com_ementa"], 1)
        self.assertEqual(payload["sem_ementa"], ["B2"])
        self.assertEqual(len(payload["hash_disciplinas"]), 64)


if __name__ == "__main__":
    unittest.main()
