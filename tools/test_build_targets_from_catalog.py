from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_targets_from_catalog as targets  # noqa: E402


def unicamp_course() -> dict:
    return {
        "codigo": "99G",
        "nome": "Engenharia de Teste",
        "fonte_curriculo": "https://example.test/99g/curriculo.html",
        "fonte_sugestao": "https://example.test/99g/sugestao.html",
        "habilitacoes": [{"codigo": "AA", "nome": "Ênfase de Teste"}],
        "curriculo": [
            {
                "secao_h2": "99 - Engenharia de Teste - Currículo Pleno",
                "secao_h3": "Núcleo Comum ao Curso",
                "tipo": "obrigatoria_comum",
                "creditos_exigidos": None,
                "disciplinas": [
                    {"codigo": "AA001", "nome": "Cálculo", "horas": 60, "creditos": 4}
                ],
            },
            {
                "secao_h2": "AA - Ênfase de Teste",
                "secao_h3": "Disciplinas Obrigatórias",
                "tipo": "obrigatoria_habilitacao",
                "creditos_exigidos": None,
                "disciplinas": [
                    {"codigo": "AA002", "nome": "Projeto", "horas": 30, "creditos": 2}
                ],
            },
            {
                "secao_h2": "AA - Ênfase de Teste",
                "secao_h3": "Disciplinas Eletivas",
                "tipo": "eletiva",
                "creditos_exigidos": 2,
                "disciplinas": [
                    {"codigo": "EX---", "nome": "Qualquer disciplina", "horas": None, "creditos": None}
                ],
            },
        ],
        "proposta": [{"codigo": "AA", "semestres": [{"numero": 1}, {"numero": 8}]}],
    }


def usp_course() -> dict:
    return {
        "codcur": "9999",
        "codhab": "3000",
        "curso": "Habilitação: Engenharia de Teste",
        "fonte": "https://example.test/grade",
        "duracao_ideal_semestres": 10,
        "grade_disponivel": True,
        "grade": [
            {
                "periodo": period,
                "codigo": f"T{period}",
                "nome": f"Disciplina {period}",
                "horas": 60,
                "creditos_aula": 4,
                "creditos_trabalho": 0,
            }
            for period in range(1, 7)
        ],
    }


class TargetConversionTest(unittest.TestCase):
    def test_classifies_non_waivable_types(self) -> None:
        self.assertEqual(targets.classify_type("Trabalho de Formatura"), "tcc")
        self.assertEqual(targets.classify_type("Estágio Supervisionado"), "estagio")
        self.assertEqual(targets.classify_type("Atividades Complementares"), "complementar")
        self.assertEqual(targets.classify_type("Cálculo I"), "obrigatoria")

    def test_builds_unicamp_target_with_variant_and_electives(self) -> None:
        target = targets.build_unicamp_target(unicamp_course(), "AA")
        self.assertEqual(target["id"], "unicamp-engenharia-de-teste-99g-2026-aa")
        self.assertEqual(target["duracao_meses"], 48)
        self.assertEqual(target["habilitacao"], "AA — Ênfase de Teste")
        self.assertEqual(target["carga_horaria_total"], 120)
        self.assertEqual(len(target["grupos"]), 3)
        self.assertTrue(target["eletivas"])
        self.assertTrue(target["grupos"][2]["componentes"][0]["livre"])

    def test_builds_usp_target_from_grade(self) -> None:
        target = targets.build_usp_target(usp_course())
        assert target is not None
        self.assertEqual(target["id"], "usp-poli-9999-3000")
        self.assertEqual(target["curso"], "Engenharia de Teste")
        self.assertEqual(target["duracao_meses"], 60)
        self.assertEqual(target["carga_horaria_total"], 360)
        self.assertEqual(len(target["grupos"]), 6)

    def test_filters_existing_and_non_engineering_courses(self) -> None:
        self.assertFalse(targets.engineering_unicamp({"codigo": "34G", "nome": "Engenharia de Computação"}))
        self.assertTrue(
            targets.engineering_unicamp(
                {"codigo": "99G", "nome": "Engenharia de Teste", "curriculo": [{}]}
            )
        )
        self.assertFalse(
            targets.engineering_usp({"codcur": "3033", "curso": "Engenharia", "grade_disponivel": True})
        )
        self.assertTrue(
            targets.engineering_usp(
                {"codcur": "9999", "curso": "Habilitação: Engenharia de Teste", "grade_disponivel": True}
            )
        )


if __name__ == "__main__":
    unittest.main()
