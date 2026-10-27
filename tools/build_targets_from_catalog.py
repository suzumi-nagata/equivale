#!/usr/bin/env python3
"""Converte cursos de engenharia do catálogo em alvos do site.

Lê:
  - data/catalog/unicamp_2026_cursos.json
  - data/catalog/usp_jupiterweb_cursos.json

Escreve:
  - data/targets/unicamp/unicamp-<curso>-2026*.json
  - data/targets/usp/usp-poli-<codcur>-<codhab>.json

A conversão é determinística e baseada apenas no que foi publicado no
currículo/grade. Ela não substitui a auditoria humana: cursos já convertidos
manualmente (34G/41G e 3033/3121 antigos) são preservados.

Uso:
    python3 -I tools/build_targets_from_catalog.py
    python3 -I tools/build_targets_from_catalog.py --dry-run
    python3 -I tools/build_targets_from_catalog.py --only-unicamp
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNICAMP_COURSES = ROOT / "data" / "catalog" / "unicamp_2026_cursos.json"
USP_COURSES = ROOT / "data" / "catalog" / "usp_jupiterweb_cursos.json"
UNICAMP_TARGETS = ROOT / "data" / "targets" / "unicamp"
USP_TARGETS = ROOT / "data" / "targets" / "usp"

# Cursos que já têm alvo convertido/auditado manualmente.
UNICAMP_EXISTING = {"34G", "41G"}
USP_EXISTING = {"3033", "3201", "3251"}
NON_ENGINEERING = {"48G"}  # Arquitetura e Urbanismo


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "curso"


def hours_of(item: dict) -> int:
    if item.get("horas") is not None:
        return int(item["horas"])
    return int(item.get("creditos") or 0) * 15


def classify_type(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    if re.search(
        r"\b(tcc|trabalho de (fim|conclusao|formatura) de curso|"
        r"trabalho de formatura|projeto de formatura|"
        r"projeto final de (graduacao|curso))\b",
        normalized,
    ):
        return "tcc"
    if re.search(r"\bestagio\b", normalized):
        return "estagio"
    if re.search(r"\bextensao\b|atividades? extensionistas?", normalized):
        return "extensao"
    if re.search(r"\batividades? complementares?\b", normalized):
        return "complementar"
    if re.search(r"\bprojeto interdisciplinar\b", normalized):
        return "projeto"
    return "obrigatoria"


def discipline(item: dict) -> dict | None:
    hours = hours_of(item)
    if hours <= 0 or not item.get("nome"):
        return None
    return {
        "codigo": item.get("codigo"),
        "nome": item["nome"],
        "horas": hours,
        "tipo": classify_type(item["nome"]),
    }


def is_free_option(item: dict) -> bool:
    code = str(item.get("codigo") or "")
    name = str(item.get("nome") or "").lower()
    return (
        item.get("tipo") == "eletiva_livre"
        or code in {"-----", "EX---", "MX---", "IX---"}
        or "qualquer disciplina" in name
    )


def elective_component(
    group: dict,
    index: int,
) -> tuple[dict, dict] | None:
    credits = int(group.get("creditos_exigidos") or 0)
    if credits <= 0:
        return None
    items = group.get("disciplinas", [])
    free = any(is_free_option(item) for item in items)
    options = [
        item["nome"]
        for item in items
        if not is_free_option(item) and item.get("nome")
    ]
    if free and not options:
        options = ["Qualquer disciplina elegível"]
    if not options:
        return None
    label = group.get("secao_h3") or "Eletivas"
    name = f"{label} ({credits} créditos)"
    if index > 1:
        name = f"{name} · {index}"
    key = f"auto-{slug(name)}-{index}"
    return (
        {
            "ordem": 0,
            "nome": name,
            "horas": credits * 15,
            "componentes": [
                {
                    "nome": label,
                    "horas": credits * 15,
                    "tipo": "eletiva",
                    "opcoes_ref": key,
                    "livre": free,
                }
            ],
        },
        {key: options},
    )


def target_header(
    *,
    target_id: str,
    instituicao: str,
    curso: str,
    habilitacao: str | None,
    duracao_meses: int,
    carga_horaria_total: int,
    fonte: str,
    proposta_fonte: str | None,
    coletado_em: str | None,
    observacoes: list[str],
) -> dict:
    return {
        "id": target_id,
        "instituicao": instituicao,
        "curso": curso,
        "grau": "bacharelado",
        "modalidade": "presencial",
        "duracao_meses": duracao_meses,
        "carga_horaria_total": carga_horaria_total,
        "curriculo_versao": "2026",
        "habilitacao": habilitacao,
        "fonte": fonte,
        "proposta_fonte": proposta_fonte,
        "coletado_em": coletado_em,
        "mec": {
            "status": "nao_verificado",
            "verificado": False,
            "instituicao_publica": True,
            "observacao": (
                "Instituição pública; a grade vem do catálogo oficial. "
                "O ato de reconhecimento não foi consultado no e-MEC nesta versão."
            ),
            "fonte": fonte,
        },
        "dados": {
            "completude": "grade_com_ch",
            "grade_disponivel": True,
            "grade_com_carga_horaria": True,
            "ppc_disponivel": False,
            "ementa_disponivel": True,
        },
        "grupos": [],
        "eletivas": {},
        "observacoes": observacoes,
    }


def proposal_duration(course: dict, variant_code: str | None) -> int | None:
    proposals = course.get("proposta") or []
    if variant_code:
        proposals = [item for item in proposals if item.get("codigo") == variant_code]
    semesters = [
        semester.get("numero")
        for proposal in proposals
        for semester in proposal.get("semestres", [])
        if semester.get("numero")
    ]
    if not semesters:
        return None
    return max(semesters) * 6


def build_unicamp_target(course: dict, variant_code: str | None) -> dict:
    variants = {item["codigo"]: item for item in course.get("habilitacoes", [])}
    variant = variants.get(variant_code) if variant_code else None
    groups = []
    eletivas: dict[str, list[str]] = {}
    seen_fixed: set[str] = set()
    elective_index = 0

    for group in course.get("curriculo", []):
        h2 = group.get("secao_h2") or ""
        h3 = group.get("secao_h3") or ""
        variant_match = re.match(r"^([A-Z]{2})\s*-\s*", h2)
        group_variant = variant_match.group(1) if variant_match else None
        if group_variant and group_variant != variant_code:
            continue
        if group.get("tipo") == "eletiva":
            elective_index += 1
            component = elective_component(group, elective_index)
            if component:
                target_group, options = component
                groups.append(target_group)
                eletivas.update(options)
            continue

        disciplines = []
        for item in group.get("disciplinas", []):
            parsed = discipline(item)
            if parsed is None:
                continue
            key = parsed["codigo"] or parsed["nome"]
            if key in seen_fixed:
                continue
            seen_fixed.add(key)
            disciplines.append(parsed)
        if not disciplines:
            continue
        if h3.startswith("Núcleo Comum"):
            name = "Núcleo Comum"
        elif group_variant:
            name = f"Obrigatórias {group_variant}"
        else:
            name = h3 or "Obrigatórias"
        groups.append(
            {
                "ordem": 0,
                "nome": name,
                "horas": sum(item["horas"] for item in disciplines),
                "disciplinas": disciplines,
            }
        )

    for order, group in enumerate(groups, start=1):
        group["ordem"] = order

    turno = course.get("turno")
    if variant:
        habilitacao = f"{variant_code} — {variant['nome']}"
        if turno:
            habilitacao += f" ({turno})"
    else:
        habilitacao = f"{course['codigo']} — Currículo pleno"
        if turno:
            habilitacao += f" ({turno})"
    duration = proposal_duration(course, variant_code) or 60
    target = target_header(
        target_id=(
            f"unicamp-{slug(course['nome'])}-{course['codigo'].lower()}-2026"
            + (f"-{variant_code.lower()}" if variant_code else "")
        ),
        instituicao="UNICAMP",
        curso=course["nome"],
        habilitacao=habilitacao,
        duracao_meses=duration,
        carga_horaria_total=sum(group["horas"] for group in groups),
        fonte=course.get("fonte_curriculo") or course.get("fonte_index") or "",
        proposta_fonte=course.get("fonte_sugestao"),
        coletado_em=course.get("coletado_em"),
        observacoes=[
            "Alvo gerado automaticamente a partir do currículo público UNICAMP 2026.",
            "Grupos de eletivas são requisitos de crédito (1 crédito = 15h), não disciplinas únicas.",
            "A conversão automatiza o schema; a decisão de equivalência continua sendo da instituição.",
        ],
    )
    target["grupos"] = groups
    target["eletivas"] = eletivas
    return target


def build_usp_target(course: dict) -> dict | None:
    grade = course.get("grade") or []
    periods: dict[int, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for item in grade:
        period = int(item.get("periodo") or 0)
        code = str(item.get("codigo") or "")
        if period <= 0 or not code or code in seen:
            continue
        parsed = discipline(item)
        if parsed is None:
            continue
        seen.add(code)
        periods[period].append(parsed)
    if len(periods) < 6:
        return None

    groups = []
    for order, period in enumerate(sorted(periods), start=1):
        disciplines = sorted(periods[period], key=lambda item: item["nome"])
        groups.append(
            {
                "ordem": order,
                "nome": f"{period}º período",
                "horas": sum(item["horas"] for item in disciplines),
                "disciplinas": disciplines,
            }
        )

    label = re.sub(r"^Habilitação:\s*", "", course.get("curso") or "").strip()
    habilitacao = None
    if "ênfase em" in label.lower():
        label, habilitacao = re.split(
            r"\s*[-–]\s*ênfase em\s*", label, maxsplit=1, flags=re.I
        )
        label = label.strip()
        habilitacao = habilitacao.strip() if habilitacao else None

    ideal_semesters = int(course.get("duracao_ideal_semestres") or 0)
    # Engenharias da Poli são cursos de 10 semestres; quando a página não
    # publica a duração, não usar o último período da grade parcial como se
    # fosse o fim do curso.
    semesters = max(ideal_semesters or 10, max(periods))
    target = target_header(
        target_id=f"usp-poli-{course['codcur']}-{course['codhab']}",
        instituicao="USP",
        curso=label,
        habilitacao=habilitacao,
        duracao_meses=semesters * 6,
        carga_horaria_total=sum(group["horas"] for group in groups),
        fonte=course.get("fonte") or course.get("url") or "",
        proposta_fonte=None,
        coletado_em=course.get("coletado_em"),
        observacoes=[
            "Alvo gerado automaticamente a partir da grade pública do Jupiterweb.",
            "A grade pode estar em construção ou conter apenas o ciclo básico; confira a fonte.",
            "A decisão de equivalência continua sendo da instituição.",
        ],
    )
    target["grupos"] = groups
    target["eletivas"] = {}
    target["curriculo_versao"] = "Jupiterweb 2026"
    return target


def engineering_unicamp(course: dict) -> bool:
    return (
        "engenharia" in (course.get("nome") or "").lower()
        and course.get("codigo") not in UNICAMP_EXISTING
        and course.get("codigo") not in NON_ENGINEERING
        and bool(course.get("curriculo"))
    )


def engineering_usp(course: dict) -> bool:
    label = course.get("curso") or ""
    return (
        course.get("grade_disponivel")
        and course.get("codcur") not in USP_EXISTING
        and "engenharia" in label.lower()
        and "ciclo básico" not in label.lower()
        and "percurso formativo" not in label.lower()
    )


def write_target(target: dict, directory: Path) -> Path:
    path = directory / f"{target['id']}.json"
    path.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-unicamp", action="store_true")
    parser.add_argument("--only-usp", action="store_true")
    args = parser.parse_args()

    outputs: list[Path] = []
    if not args.only_usp:
        source = json.loads(UNICAMP_COURSES.read_text(encoding="utf-8"))
        for course in source.get("cursos", []):
            if not engineering_unicamp(course):
                continue
            variants = course.get("habilitacoes") or []
            codes = [item["codigo"] for item in variants if item["codigo"] != "AX"]
            if not codes:
                codes = [None]
            for variant_code in codes:
                target = build_unicamp_target(course, variant_code)
                target["coletado_em"] = source.get("coletado_em")
                if args.dry_run:
                    print(
                        f"dry-run: UNICAMP {target['id']} "
                        f"{target['carga_horaria_total']}h "
                        f"{len(target['grupos'])} grupos"
                    )
                else:
                    outputs.append(write_target(target, UNICAMP_TARGETS))

    if not args.only_unicamp:
        source = json.loads(USP_COURSES.read_text(encoding="utf-8"))
        for course in source.get("cursos", []):
            if not engineering_usp(course):
                continue
            target = build_usp_target(course)
            if target is not None:
                target["coletado_em"] = source.get("coletado_em")
            if target is None:
                print(
                    f"aviso: USP {course['codcur']}/{course['codhab']} sem grade completa",
                    file=sys.stderr,
                )
                continue
            if args.dry_run:
                print(
                    f"dry-run: USP {target['id']} {target['curso']} "
                    f"{target['carga_horaria_total']}h "
                    f"{len(target['grupos'])} períodos"
                )
            else:
                outputs.append(write_target(target, USP_TARGETS))

    if not args.dry_run:
        print(f"{len(outputs)} alvos gerados")
        for path in outputs:
            print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
