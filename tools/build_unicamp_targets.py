#!/usr/bin/env python3
"""Converte os currículos de origem da UNICAMP 2026 em alvos do site.

Lê data/sources/unicamp/*.json e escreve data/targets/unicamp/*.json no
schema de currículo-alvo do site (grupos + eletivas + carga horária).

Uso:
    python3 -I tools/build_unicamp_targets.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "sources" / "unicamp"
TARGET_DIR = ROOT / "data" / "targets" / "unicamp"

# duracao_meses segue a proposta de cumprimento do catálogo 2026.
SPECS = {
    "eng_computacao_2026": {
        "AA": {
            "id": "unicamp-ec-2026-aa",
            "habilitacao": "AA — Sistemas de Computação",
            "duracao_meses": 60,
        },
        "AB": {
            "id": "unicamp-ec-2026-ab",
            "habilitacao": "AB — Sistemas e Processos Industriais",
            "duracao_meses": 60,
        },
    },
    "eng_eletrica_2026": {
        "41G": {
            "id": "unicamp-ee-2026",
            "habilitacao": "41G — Currículo pleno",
            "duracao_meses": 84,
        },
    },
}


def hours_of(item: dict) -> int:
    if item.get("horas") is not None:
        return int(item["horas"])
    return int(item.get("creditos") or 0) * 15


def discipline(item: dict) -> dict:
    return {
        "codigo": item.get("codigo"),
        "nome": item["nome"],
        "horas": hours_of(item),
        "tipo": "obrigatoria",
    }


def build_target(source_key: str, source: dict, variant: dict, spec: dict) -> dict:
    groups: list[dict] = []
    eletivas: dict[str, list[str]] = {}
    total_hours = 0

    common_disciplines = [discipline(item) for item in source["nucleo_comum"]]
    common_hours = sum(item["horas"] for item in common_disciplines)
    if common_disciplines:
        groups.append(
            {
                "ordem": 1,
                "nome": "Núcleo Comum",
                "horas": common_hours,
                "disciplinas": common_disciplines,
            }
        )
        total_hours += common_hours

    required = [discipline(item) for item in variant["obrigatorias"]]
    required_hours = sum(item["horas"] for item in required)
    if required:
        groups.append(
            {
                "ordem": 2,
                "nome": f"Obrigatórias {variant['codigo']}",
                "horas": required_hours,
                "disciplinas": required,
            }
        )
        total_hours += required_hours

    for index, group in enumerate(variant["eletivas"], start=1):
        credits = int(group.get("creditos_exigidos") or 0)
        if credits <= 0:
            continue
        key = f"{variant['codigo']}-E{index}"
        free = any(item.get("tipo") == "eletiva_livre" for item in group["disciplinas"])
        options = [
            item["nome"]
            for item in group["disciplinas"]
            if item.get("tipo") != "eletiva_livre"
        ]
        if free and not options:
            options = ["Qualquer disciplina elegível"]
        eletivas[key] = options
        hours = credits * 15
        groups.append(
            {
                "ordem": len(groups) + 1,
                "nome": f"{group['grupo']} ({credits} créditos)",
                "horas": hours,
                "componentes": [
                    {
                        "nome": group["grupo"],
                        "horas": hours,
                        "tipo": "eletiva",
                        "opcoes_ref": key,
                        "livre": free,
                    }
                ],
            }
        )
        total_hours += hours

    return {
        "id": spec["id"],
        "instituicao": source["instituicao"],
        "curso": source["curso"],
        "grau": "bacharelado",
        "modalidade": "presencial",
        "duracao_meses": spec["duracao_meses"],
        "carga_horaria_total": total_hours,
        "curriculo_versao": source["curriculo_versao"],
        "habilitacao": spec["habilitacao"],
        "fonte": source["fonte"],
        "proposta_fonte": source["proposta_fonte"],
        "coletado_em": source.get("coletado_em"),
        "mec": {
            "status": "nao_verificado",
            "verificado": False,
            "instituicao_publica": True,
            "observacao": (
                "UNICAMP é universidade pública; o catálogo oficial é a fonte da grade. "
                "O ato de reconhecimento do curso não foi consultado no e-MEC nesta versão."
            ),
            "fonte": source["fonte"],
        },
        "dados": {
            "completude": "grade_com_ch",
            "grade_disponivel": True,
            "grade_com_carga_horaria": True,
            "ppc_disponivel": False,
            "ementa_disponivel": False,
        },
        "grupos": groups,
        "eletivas": eletivas,
        "observacoes": [
            "Currículo público UNICAMP 2026 convertido para o schema de alvo do site.",
            "Grupos de eletivas são requisitos de crédito (1 crédito = 15h), não slots fixos.",
            "AA e AB são habilitações distintas; o alvo escolhido é uma única variante.",
        ],
    }


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for source_key, variants in SPECS.items():
        source = json.loads((SOURCE_DIR / f"{source_key}.json").read_text(encoding="utf-8"))
        by_code = {variant["codigo"]: variant for variant in source["variantes"]}
        for variant_code, spec in variants.items():
            variant = by_code.get(variant_code)
            if variant is None:
                raise SystemExit(f"Variante {variant_code} não encontrada em {source_key}")
            target = build_target(source_key, source, variant, spec)
            output = TARGET_DIR / f"{spec['id']}.json"
            output.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(
                f"{output}: {len(target['grupos'])} grupos, "
                f"{target['carga_horaria_total']}h, {len(target['eletivas'])} grupos de eletivas"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
