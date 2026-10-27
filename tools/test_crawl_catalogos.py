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
