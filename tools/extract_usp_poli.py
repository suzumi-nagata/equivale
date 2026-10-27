#!/usr/bin/env python3
"""Extrai os currículos da Poli-USP usados como alvos de comparação.

Fontes públicas (Jupiterweb):
  - Engenharia Elétrica, ênfase Automação e Controle (2027)
  - Engenharia de Computação (currículo 2012 disponível no Jupiterweb)

Uso:
    python3 -I tools/extract_usp_poli.py
    python3 -I tools/extract_usp_poli.py --html-dir /tmp/usp-poli-cache
"""

from __future__ import annotations

import argparse
import html
import re
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "targets" / "usp"

SOURCES = {
    "ee_basic": {
        "url": "https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3033&codhab=0&tipo=N&print=true",
        "label": "Ciclo Básico - Engenharia Elétrica",
    },
    "ee_ac": {
        "url": "https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3032&codhab=3150&tipo=V&print=true",
        "label": "Engenharia Elétrica - Ênfase em Automação e Controle",
    },
    "ec": {
        "url": "https://uspdigital.usp.br/jupiterweb/listarGradeCurricular?codcg=3&codcur=3121&codhab=10&tipo=V&print=true",
        "label": "Engenharia de Computação",
    },
}


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_page(page_html: str) -> list[dict]:
    section = None
    period = None
    rows: list[dict] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", page_html, flags=re.S | re.I):
        cells = [
            clean(cell)
            for cell in re.findall(r"<t[dh]\b.*?</t[dh]>", row_html, flags=re.S | re.I)
        ]
        joined = " ".join(cells)
        if re.search(r"Disciplinas\s+Obrigat[oó]rias", joined, re.I):
            section = "required"
            continue
        if re.search(r"Disciplinas\s+Optativas", joined, re.I):
            section = "optional"
            continue
        period_match = re.search(r"(\d+)\s*[º°o]?\s*Per[ií]odo\s+Ideal", joined, re.I)
        if period_match:
            period = int(period_match.group(1))
            continue
        if section != "required" or period is None or len(cells) < 5:
            continue
        code = cells[0].strip()
        if not re.fullmatch(r"[A-Z0-9]{3,}", code):
            continue
        name = cells[1].strip()
        numbers = []
        for cell in cells[2:5]:
            match = re.search(r"\d+", cell)
            numbers.append(int(match.group()) if match else None)
        credits_aula, credits_trab, hours = numbers
        if hours is None or hours <= 0 or not name:
            continue
        rows.append(
            {
                "periodo": period,
                "codigo": code,
                "nome": name,
                "creditos_aula": credits_aula,
                "creditos_trabalho": credits_trab,
                "horas": hours,
            }
        )
    # Um mesmo código pode aparecer em mais de uma tabela; preserva a primeira.
    seen: set[str] = set()
    unique = []
    for row in rows:
        if row["codigo"] in seen:
            continue
        seen.add(row["codigo"])
        unique.append(row)
    return unique


def fetch(url: str, html_dir: Path | None, key: str) -> str:
    if html_dir is not None:
        path = html_dir / f"{key}.html"
        if not path.exists():
            raise SystemExit(f"Arquivo não encontrado: {path}")
        return path.read_text(encoding="latin-1", errors="replace")

    request = urllib.request.Request(url, headers={"User-Agent": "equivale-usp-collector/1.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("latin-1", errors="replace")
        except Exception as error:  # noqa: BLE001 - relatório de coleta
            last_error = error
            if attempt < 2:
                time.sleep(1 + attempt)
    raise SystemExit(f"Falha ao baixar {url}: {last_error}")


def groups_from(rows: list[dict]) -> list[dict]:
    by_period: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_period[row["periodo"]].append(row)

    groups = []
    for period in sorted(by_period):
        disciplines = [
            {
                "codigo": row["codigo"],
                "nome": row["nome"],
                "horas": row["horas"],
                "tipo": "obrigatoria",
            }
            for row in sorted(by_period[period], key=lambda item: item["nome"])
        ]
        groups.append(
            {
                "ordem": len(groups) + 1,
                "nome": f"{period}º período",
                "horas": sum(item["horas"] for item in disciplines),
                "disciplinas": disciplines,
            }
        )
    return groups


def build_target(
    target_id: str,
    course: str,
    habilitacao: str | None,
    version: str,
    groups: list[dict],
    fonte: str,
    observacoes: list[str],
) -> dict:
    total = sum(group["horas"] for group in groups)
    return {
        "id": target_id,
        "instituicao": "USP",
        "curso": course,
        "grau": "bacharelado",
        "modalidade": "presencial",
        "duracao_meses": 60,
        "carga_horaria_total": total,
        "curriculo_versao": version,
        "habilitacao": habilitacao,
        "fonte": fonte,
        "mec": {
            "status": "nao_verificado",
            "verificado": False,
            "instituicao_publica": True,
            "observacao": (
                "USP é universidade pública; a grade é do Jupiterweb. "
                "O ato de reconhecimento do curso não foi consultado no e-MEC nesta versão."
            ),
            "fonte": fonte,
        },
        "dados": {
            "completude": "grade_com_ch",
            "grade_disponivel": True,
            "grade_com_carga_horaria": True,
            "ppc_disponivel": True,
            "ementa_disponivel": False,
        },
        "grupos": groups,
        "eletivas": {},
        "observacoes": observacoes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-dir", type=Path, default=None)
    args = parser.parse_args()

    pages = {
        key: fetch(meta["url"], args.html_dir, key)
        for key, meta in SOURCES.items()
    }
    ee_basic = parse_page(pages["ee_basic"])
    ee_ac = parse_page(pages["ee_ac"])
    ec = parse_page(pages["ec"])

    # EE: núcleo básico 1º-6º + ênfase 7º-10º.
    ee_rows = [row for row in ee_basic if row["periodo"] <= 6] + [
        row for row in ee_ac if row["periodo"] >= 7
    ]
    ee_groups = groups_from(ee_rows)

    # EC: a tabela profissional começa no 5º período; usa-se a base comum
    # 1º-4º do ciclo básico como base compartilhada.
    ec_rows = [row for row in ee_basic if row["periodo"] <= 4] + [
        row for row in ec if row["periodo"] >= 5
    ]
    ec_groups = groups_from(ec_rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ee_target = build_target(
        "usp-poli-ee-ac-2027",
        "Engenharia Elétrica",
        "Automação e Controle",
        "2027",
        ee_groups,
        SOURCES["ee_ac"]["url"],
        [
            "Grade extraída do Jupiterweb: ciclo básico 3033 (1º-6º) + ênfase Automação e Controle 3032/3150 (7º-10º).",
            "A carga total é a soma das disciplinas obrigatórias extraídas; o resumo oficial inclui optativas, AAC, AEX e extensão.",
            "Currículo em construção no Jupiterweb (2027); os semestres são acrescentados anualmente.",
        ],
    )
    ec_target = build_target(
        "usp-poli-ec-2012",
        "Engenharia de Computação",
        "Habilitação Engenharia de Computação",
        "2012 (tabela Jupiterweb)",
        ec_groups,
        SOURCES["ec"]["url"],
        [
            "Grade profissional extraída do Jupiterweb (currículo 2012, períodos 5º-13º).",
            "A base comum 1º-4º usa a tabela do ciclo básico 3033 disponível no Jupiterweb; pode variar em relação ao currículo antigo.",
            "A carga total é a soma das disciplinas obrigatórias extraídas; o resumo oficial inclui optativas e estágios cooperativos.",
            "O curso atual de Engenharia de Computação (3122/3000) tem resumo público, mas a tabela de disciplinas não está disponível na página consultada.",
        ],
    )

    for target, filename in [
        (ee_target, "usp-poli-ee-ac-2027.json"),
        (ec_target, "usp-poli-ec-2012.json"),
    ]:
        output = OUT_DIR / filename
        output.write_text(
            __import__("json").dumps(target, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"{output}: {len(target['grupos'])} grupos, "
            f"{target['carga_horaria_total']}h"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
