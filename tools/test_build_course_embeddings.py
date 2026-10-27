from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_course_embeddings as embeddings  # noqa: E402

try:
    import numpy  # noqa: F401

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def document(**overrides) -> embeddings.Document:
    values = {
        "key": "UNICAMP|BE310",
        "instituicao": "UNICAMP",
        "codigo": "BE310",
        "nome": "Ciências do Ambiente",
        "nome_chave": "cienciasdoambiente",
        "horas": 30,
        "ementa": "População humana, energia, clima e sustentabilidade.",
        "objetivos": "",
        "conteudo": "",
        "fonte": "https://example.test/BE310",
        "origem": "catalogo",
    }
    values.update(overrides)
    return embeddings.Document(**values)


class EmbeddingBuilderTest(unittest.TestCase):
    def test_code_and_name_keys_are_stable(self) -> None:
        self.assertEqual(embeddings.code_key("F 328"), "F328")
        self.assertEqual(embeddings.make_key("UNICAMP", "F 328", "Física III"), "UNICAMP|F328")
        self.assertEqual(
            embeddings.make_key("UNINTER", None, "Ciências do Ambiente"),
            "UNINTER|NOME|cienciasdoambiente",
        )

    def test_keeps_domain_terms_in_title(self) -> None:
        counts = embeddings.document_counts(document())
        self.assertIn("ambiente", counts)
        self.assertIn("cienci", counts)
        self.assertIn("sustent", counts)
        self.assertNotIn("de", counts)
        self.assertNotIn("curso", counts)

    def test_hash_is_deterministic(self) -> None:
        first = embeddings.hash_term("eletromagnetismo", 256)
        second = embeddings.hash_term("eletromagnetismo", 256)
        self.assertEqual(first, second)
        self.assertGreaterEqual(first[0], 0)
        self.assertLess(first[0], 256)
        self.assertIn(first[1], (-1.0, 1.0))

    def test_hashing_vector_is_normalized_and_quantized_to_int8(self) -> None:
        counts = [
            embeddings.document_counts(document()),
            embeddings.document_counts(document(key="OUTRO", nome="Física")),
        ]
        idf, _ = embeddings.build_idf(counts)
        vector = embeddings.hashing_vectors(counts, idf, 64)[0]
        self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=6)
        encoded = embeddings.quantize(vector)
        raw = base64.b64decode(encoded)
        self.assertEqual(len(raw), 64)

    def test_title_only_document_has_hash_vector(self) -> None:
        counts = [
            embeddings.document_counts(
                document(ementa="", objetivos="", conteudo="")
            ),
            embeddings.document_counts(document(key="OUTRO", nome="Física")),
        ]
        idf, _ = embeddings.build_idf(counts)
        vector = embeddings.hashing_vectors(counts, idf, 32)[0]
        self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=6)

    @unittest.skipUnless(HAS_NUMPY, "NumPy não instalado")
    def test_lsa_is_deterministic_and_normalized(self) -> None:
        documents = [
            document(
                key=f"UNICAMP|T{index}",
                codigo=f"T{index}",
                nome=f"Disciplina de engenharia {index}",
                ementa=(
                    "Eletromagnetismo, circuitos elétricos e sistemas lineares."
                    if index % 2 == 0
                    else "Programação, algoritmos e estruturas de dados."
                ),
            )
            for index in range(8)
        ]
        counts = [embeddings.document_counts(item) for item in documents]
        idf, _ = embeddings.build_idf(counts)
        first = embeddings.lsa_vectors(counts, idf, 4, iterations=1, seed=7)
        second = embeddings.lsa_vectors(counts, idf, 4, iterations=1, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 4)
        for vector in first:
            self.assertAlmostEqual(sum(value * value for value in vector), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
