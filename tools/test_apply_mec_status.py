from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import apply_mec_status as status  # noqa: E402


class MecStatusTest(unittest.TestCase):
    def test_mapping_has_sources_and_acts(self) -> None:
        payload = status.load_status()
        targets = payload["alvos"]
        self.assertGreaterEqual(len(targets), 30)
        for target_id, info in targets.items():
            self.assertTrue(target_id)
            self.assertEqual(info["status"], "reconhecido_cee_sp")
            self.assertTrue(info["verificado"])
            self.assertTrue(info["ato"])
            self.assertTrue(info["fonte"].startswith("https://"))

    def test_apply_status_merges_mec_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(
                json.dumps(
                    {
                        "id": "unicamp-engenharia-civil-12g-2026",
                        "mec": {"status": "nao_verificado"},
                    }
                ),
                encoding="utf-8",
            )
            mapping = status.load_status()["alvos"]
            self.assertTrue(status.apply_status(path, mapping))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mec"]["status"], "reconhecido_cee_sp")
            self.assertTrue(payload["mec"]["instituicao_publica"])
            self.assertIn("CEE-GP", payload["mec"]["ato"])

    def test_unknown_target_is_not_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target.json"
            path.write_text(
                json.dumps({"id": "nao-existe", "mec": {"status": "nao_verificado"}}),
                encoding="utf-8",
            )
            self.assertFalse(status.apply_status(path, status.load_status()["alvos"]))
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mec"]["status"], "nao_verificado")


if __name__ == "__main__":
    unittest.main()
