#!/usr/bin/env python3
"""Aplica aos alvos o status de reconhecimento verificado no CEE-SP.

Fonte: data/targets/mec_status.json. O script atualiza apenas o bloco `mec`
dos JSONs de alvo; não altera currículo, carga horária nem grupos.

Uso:
    python3 -I tools/apply_mec_status.py
    python3 -I tools/apply_mec_status.py --check
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / "data" / "targets" / "mec_status.json"
TARGET_DIRS = [
    ROOT / "data" / "targets" / "unicamp",
    ROOT / "data" / "targets" / "usp",
]


def load_status() -> dict:
    payload = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    targets = payload.get("alvos")
    if not isinstance(targets, dict):
        raise SystemExit(f"{STATUS_FILE} não contém o mapa 'alvos'.")
    return payload


def target_files() -> list[Path]:
    return sorted(
        path
        for directory in TARGET_DIRS
        if directory.exists()
        for path in directory.glob("*.json")
    )


def apply_status(path: Path, status: dict) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    target_id = payload.get("id")
    info = status.get(target_id)
    if not info:
        return False
    current = payload.get("mec") if isinstance(payload.get("mec"), dict) else {}
    merged = {
        **current,
        **info,
        "instituicao_publica": True,
    }
    payload["mec"] = merged
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="só valida, sem escrever")
    args = parser.parse_args()

    payload = load_status()
    status = payload["alvos"]
    files = target_files()
    seen: set[str] = set()
    applied = 0
    missing: list[str] = []
    for path in files:
        target = json.loads(path.read_text(encoding="utf-8"))
        target_id = target.get("id")
        if target_id in status:
            seen.add(target_id)
            if args.check:
                print(f"OK {target_id}: {status[target_id].get('ato')}")
            elif apply_status(path, status):
                applied += 1
                print(f"{path.relative_to(ROOT)}: {status[target_id].get('ato')}")
        elif target.get("instituicao") in {"UNICAMP", "USP"}:
            missing.append(str(target_id))

    unknown = sorted(set(status) - seen)
    if unknown:
        print("aviso: status para alvos inexistentes: " + ", ".join(unknown))
    if missing:
        print("aviso: alvos UNICAMP/USP sem status verificado: " + ", ".join(missing))
    if not args.check:
        print(f"{applied} alvos atualizados")
    return 0 if not unknown else 1


if __name__ == "__main__":
    raise SystemExit(main())
