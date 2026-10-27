#!/usr/bin/env python3
"""Proof-of-concept matcher: transcript normalizado x currículo normalizado.

Sem ementa, a estimativa usa nome + carga horária. O pareamento é uma
atribuição ótima um-para-um (algoritmo húngaro): cada disciplina de origem
ocupa no máximo um slot do currículo alvo.

Uso:
    python3 -I match_curricula.py \
        --transcript /tmp/transcript-parser/SEU_HISTORICO.json \
        --curriculum data/spike/curriculos/uninter_ads.json \
        --out /tmp/spike-matching/unicamp_ads.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APPROVED = {"aprovado", "aprovado_proficiencia"}
NON_WAIVABLE_TYPES = {"extensao", "projeto", "complementar", "estagio", "tcc"}
NON_WAIVABLE_NAME_PATTERNS = [
    r"\batividades? complementares?\b",
    r"\batividades? extensionistas?\b",
    r"\bextensao\b",
    r"\bestagio\b",
    r"\btrabalho de (fim|conclusao) de curso\b",
    r"\btcc\b",
    r"\bprojeto interdisciplinar\b",
]
SOURCE_EXCLUDE_NAME_PATTERNS = [
    r"\bestagio\b",
    r"\btrabalho de (fim|conclusao) de curso\b",
    r"\btcc\b",
    r"\batividades? complementares?\b",
    r"\bextensao\b",
]

STOPWORDS = {
    "a", "as", "o", "os", "de", "da", "das", "do", "dos", "e", "em", "para",
    "por", "com", "sem", "um", "uma", "uns", "umas", "na", "nas", "no", "nos",
    "ao", "aos", "à", "às", "the", "and", "of", "for", "in", "on", "to",
}

# Conceitos genéricos: um match específico (ex.: estrutura_dados) deve
# desempatar contra um match genérico (ex.: programacao).
BROAD_CONCEPTS = {
    "programacao", "calculo", "seguranca", "ia", "redes", "direito",
    "etica", "meio_ambiente", "governanca",
}

# Conceitos canônicos aproximados para o domínio de computação/engenharia.
# A ordem importa apenas para leitura; todos os padrões são testados.
CONCEPT_PATTERNS: list[tuple[str, list[str]]] = [
    ("calculo", [r"(?<!pre )\bcalculo\b(?!\s+numerico)"]),
    ("calculo_numerico", [r"\bcalculo numerico\b", r"\bmetodos? numericos?\b", r"\bmetodo numerico\b"]),
    ("algebra_linear", [r"\balgebra linear\b"]),
    ("geometria_analitica", [r"\bgeometria analitica\b"]),
    ("probabilidade", [r"\bprobabilidade\b", r"\bprocessos estocasticos\b"]),
    ("estatistica", [r"\bestatistica\b"]),
    ("pre_calculo", [r"\bpre calculo\b", r"\bmatematica elementar\b"]),
    ("programacao", [
        r"\bprogramacao\b(?!\s+matematica)",
        r"\balgoritmos?\b",
        r"\blaboratorio de programacao\b",
        r"\bintroducao a computacao\b",
        r"\bintroducao a ciencia da computacao\b",
    ]),
    ("estrutura_dados", [r"\bestruturas? de dados\b"]),
    ("poo", [r"\bprogramacao orientada a objetos\b", r"\borientada a objetos\b", r"\bpoo\b"]),
    ("banco_dados", [r"\bbanco de dados\b", r"\bbanco dados\b", r"\bsgbd\b"]),
    ("engenharia_software", [r"\bengenharia de software\b"]),
    ("sistemas_operacionais", [r"\bsistemas? operacionais?\b"]),
    ("redes", [
        r"\bredes de computadores\b",
        r"\bredes e comunicacoes\b",
        r"\bcomunicacao de dados\b",
        r"\bprotocolos de redes\b",
    ]),
    ("ia", [
        r"\binteligencia artificial\b",
        r"\binteligencia computacional\b",
    ]),
    ("machine_learning", [
        r"\bmachine learning\b",
        r"\baprendizado de maquina\b",
        r"\bdeep learning\b",
        r"\bredes neurais\b",
    ]),
    ("organizacao_computadores", [
        r"\barquitetura de computadores\b",
        r"\borganizacao de computadores\b",
        r"\bsistemas de computacao digital\b",
        r"\barquitetura e organizacao de computadores\b",
    ]),
    ("circuitos_digitais", [
        r"\bsistemas digitais\b",
        r"\bcircuitos digitais\b",
        r"\bcircuitos logicos\b",
        r"\blaboratorio digital\b",
    ]),
    ("cloud", [r"\bcomputacao em nuvem\b", r"\bcloud\b"]),
    ("big_data", [r"\bbig data\b"]),
    ("seguranca", [
        r"\bseguranca da informacao\b",
        r"\bseguranca em sistemas de informacao\b",
        r"\bseguranca em comunicacao de dados\b",
        r"\bciberseguranca\b",
        r"\bseguranca de sistemas\b",
        r"\bseguranca em banco de dados\b",
        r"\bseguranca de redes\b",
        r"\bseguranca em ambiente web\b",
        r"\bseguranca cibernetica\b",
    ]),
    ("devops", [r"\bdevops\b", r"\bintegracao continua\b"]),
    ("gestao_projetos", [r"\bgestao de projetos\b", r"\bmetodos ageis\b", r"\bgerencia de projetos\b"]),
    ("ihc", [r"\bdesign de interacao\b", r"\binterface homem\b", r"\bihc\b", r"\busabilidade\b"]),
    ("modelagem_sistemas", [r"\banalise e modelagem de sistemas\b", r"\bmodelagem de sistemas\b"]),
    ("web", [
        r"\bdesenvolvimento web\b",
        r"\bferramentas de desenvolvimento web\b",
        r"\bfront end\b",
        r"\bback end\b",
        r"\barquitetura e desenvolvimento de apis\b",
    ]),
    ("mobile", [r"\bdesenvolvimento mobile\b", r"\bcomputacao movel\b", r"\bmobile\b"]),
    ("teste", [r"\btestes? de software\b", r"\bqualidade de software\b"]),
    ("governanca", [r"\bgovernanca de ti\b", r"\bgovernanca\b", r"\bgestao da tecnologia da informacao\b"]),
    ("direito_cibernetico", [r"\bdireito cibernetico\b"]),
    ("direito", [r"\bdireito\b(?! cibernetico)", r"\blegislacao\b"]),
    ("empreendedorismo", [r"\bempreendedorismo\b", r"\binovacao\b"]),
    ("metodologia", [r"\bmetodologia cientifica\b", r"\bmetodologia de pesquisa\b"]),
    ("portugues", [r"\bproducao textual\b", r"\blingua portuguesa\b", r"\bcomunicacao e expressao\b", r"\bportugues\b"]),
    ("etnico_racial", [
        r"\brelacoes etnico\b",
        r"\bafricana\b",
        r"\bafro brasileira\b",
        r"\bindigena\b",
    ]),
    ("meio_ambiente", [r"\bciencias do ambiente\b", r"\bsustentabilidade\b"]),
    ("formacao_cidada", [r"\bformacao cidada\b"]),
    ("etica", [r"\betica\b"]),
    ("sociologia", [r"\bsociologia\b"]),
    ("ciencia_tecnologia_sociedade", [
        r"\bciencia, tecnologia e sociedade\b",
        r"\bciencia tecnologia e sociedade\b",
    ]),
    ("logica", [r"\braciocinio logico\b", r"\blogica matematica\b"]),
    ("processos_negocios", [r"\bmodelagem de processos\b", r"\bprocessos e negocios\b"]),
    ("pesquisa_operacional", [r"\bpesquisa operacional\b"]),
    ("sistemas_informacao", [r"\bsistemas? de informacao\b", r"\bfundamentos de sistema de informacao\b"]),
    ("requisitos", [r"\bengenharia de requisitos\b", r"\brequisitos\b"]),
    ("metricas", [r"\bmetricas\b", r"\bestimativa de software\b"]),
    ("configuracao", [r"\bgerencia de configuracao\b"]),
    ("visualizacao", [r"\bvisualizacao de dados\b", r"\bstorytelling\b"]),
    ("distribuidos", [r"\bsistemas distribuidos\b"]),
    ("compiladores", [r"\bcompiladores\b", r"\blinguagens formais\b"]),
    ("teoria_computacao", [r"\bteoria da computacao\b", r"\bteoria dos grafos\b"]),
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> set[str]:
    return {token for token in normalize(text).split() if len(token) > 2 and token not in STOPWORDS}


def concepts(text: str) -> set[str]:
    normalized = normalize(text)
    found: set[str] = set()
    for concept, patterns in CONCEPT_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            found.add(concept)
    return found


def name_score(target_name: str, source_name: str) -> dict[str, Any]:
    target_concepts = concepts(target_name)
    source_concepts = concepts(source_name)
    target_tokens = tokenize(target_name)
    source_tokens = tokenize(source_name)
    shared_tokens = sorted(target_tokens & source_tokens)
    jaccard = (
        len(target_tokens & source_tokens) / len(target_tokens | source_tokens)
        if target_tokens | source_tokens
        else 0.0
    )

    if target_concepts:
        overlap = len(target_concepts & source_concepts) / len(target_concepts)
        if overlap == 0:
            return {
                "score": 0.0,
                "parcial": True,
                "conceitos_alvo": sorted(target_concepts),
                "conceitos_origem": sorted(source_concepts),
                "conceitos_comuns": [],
                "tokens_comuns": shared_tokens,
                "motivo": "sem conceito em comum",
            }
        score = min(1.0, overlap + 0.1 * jaccard)
        if overlap == 1.0:
            score = max(score, 0.9)
        return {
            "score": score,
            "parcial": overlap < 1.0,
            "conceitos_alvo": sorted(target_concepts),
            "conceitos_origem": sorted(source_concepts),
            "conceitos_comuns": sorted(target_concepts & source_concepts),
            "tokens_comuns": shared_tokens,
            "motivo": "conceito",
        }

    if not target_tokens:
        return {
            "score": 0.0,
            "parcial": True,
            "conceitos_alvo": [],
            "conceitos_origem": sorted(source_concepts),
            "conceitos_comuns": [],
            "tokens_comuns": shared_tokens,
            "motivo": "nome sem tokens",
        }
    containment = len(target_tokens & source_tokens) / len(target_tokens)
    if containment >= 0.6 and jaccard >= 0.4:
        score = 0.6 * containment + 0.4 * jaccard
        return {
            "score": score,
            "parcial": True,
            "conceitos_alvo": [],
            "conceitos_origem": sorted(source_concepts),
            "conceitos_comuns": [],
            "tokens_comuns": shared_tokens,
            "motivo": "tokens",
        }
    return {
        "score": 0.0,
        "parcial": True,
        "conceitos_alvo": [],
        "conceitos_origem": sorted(source_concepts),
        "conceitos_comuns": [],
        "tokens_comuns": shared_tokens,
        "motivo": "tokens insuficientes",
    }


def workload_fit(target_hours: int, source_hours: int) -> float:
    if target_hours <= 0:
        return 0.0
    if source_hours >= target_hours:
        return 1.0
    ratio = source_hours / target_hours
    if ratio >= 0.75:
        return 0.8
    if ratio >= 0.5:
        return 0.5
    return 0.2


def pair_score(target_name: str, target_hours: int, source_name: str, source_hours: int) -> dict[str, Any]:
    details = name_score(target_name, source_name)
    fit = workload_fit(target_hours, source_hours)
    score = 0.8 * details["score"] + 0.2 * fit
    if details["score"] < 0.5 or score < 0.55:
        score = 0.0
    confidence = "baixa"
    if score >= 0.85 and not details["parcial"] and details["tokens_comuns"]:
        confidence = "alta"
    elif score >= 0.7:
        confidence = "media"
    return {
        "score": round(score, 4),
        "confianca": confidence,
        "parcial": details["parcial"],
        "conceitos_alvo": details["conceitos_alvo"],
        "conceitos_origem": details["conceitos_origem"],
        "conceitos_comuns": details["conceitos_comuns"],
        "tokens_comuns": details["tokens_comuns"],
        "motivo": details["motivo"],
        "workload_fit": fit,
    }


@dataclass
class Slot:
    group_order: int
    group_name: str
    name: str
    hours: int
    options: list[str]
    kind: str
    waivable: bool = True
    tipo: str = "obrigatoria"


@dataclass
class Source:
    code: str
    name: str
    hours: int
    period: str | None
    situacao: str


def build_slots(curriculum: dict[str, Any]) -> tuple[list[Slot], list[Slot], int]:
    waivable: list[Slot] = []
    non_waivable: list[Slot] = []
    total = 0

    for group in curriculum["grupos"]:
        order = group.get("ordem", 0)
        group_name = group.get("nome", "")
        for discipline in group.get("disciplinas", []):
            hours = int(discipline.get("horas") or 0)
            total += hours
            name = discipline["nome"]
            tipo = discipline.get("tipo", "obrigatoria")
            normalized = normalize(name)
            blocked = tipo in NON_WAIVABLE_TYPES or any(
                re.search(pattern, normalized) for pattern in NON_WAIVABLE_NAME_PATTERNS
            )
            slot = Slot(
                group_order=order,
                group_name=group_name,
                name=name,
                hours=hours,
                options=[name],
                kind="fixa",
                waivable=not blocked,
                tipo=tipo,
            )
            (waivable if slot.waivable else non_waivable).append(slot)

        for component in group.get("componentes", []):
            hours = int(component.get("horas") or 0)
            total += hours
            ref = component.get("opcoes_ref")
            options = curriculum.get("eletivas", {}).get(ref, []) if ref else []
            if not options:
                options = [component["nome"]]
            waivable.append(
                Slot(
                    group_order=order,
                    group_name=group_name,
                    name=component["nome"],
                    hours=hours,
                    options=list(options),
                    kind="eletiva",
                    waivable=True,
                    tipo="eletiva",
                )
            )

    return waivable, non_waivable, total


def load_sources(transcript: dict[str, Any]) -> list[Source]:
    by_code: dict[str, Source] = {}
    for discipline in transcript.get("disciplinas", []):
        if discipline.get("situacao") not in APPROVED:
            continue
        hours = discipline.get("horas")
        if not hours or int(hours) <= 0:
            continue
        name = discipline.get("nome") or ""
        normalized = normalize(name)
        if any(re.search(pattern, normalized) for pattern in SOURCE_EXCLUDE_NAME_PATTERNS):
            continue
        code = discipline.get("codigo_normalizado") or discipline.get("codigo") or ""
        source = Source(
            code=code,
            name=name,
            hours=int(hours),
            period=discipline.get("periodo"),
            situacao=discipline.get("situacao", ""),
        )
        previous = by_code.get(code)
        if previous is None or (source.period or "") >= (previous.period or ""):
            by_code[code] = source
    return list(by_code.values())


def hungarian(cost: list[list[float]]) -> list[int]:
    """Minimum-cost assignment for a square matrix. Returns row -> column."""
    n = len(cost)
    if n == 0:
        return []
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                current = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if current < minv[j]:
                    minv[j] = current
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j] != 0:
            assignment[p[j] - 1] = j - 1
    return assignment


def run_match(sources: list[Source], slots: list[Slot]) -> list[tuple[int, int, dict[str, Any]]]:
    if not sources or not slots:
        return []

    ns, nt = len(sources), len(slots)
    details: list[list[dict[str, Any] | None]] = [[None] * nt for _ in range(ns)]
    values = [[0.0] * nt for _ in range(ns)]

    for i, source in enumerate(sources):
        for j, slot in enumerate(slots):
            best: dict[str, Any] | None = None
            for option in slot.options:
                info = pair_score(option, slot.hours, source.name, source.hours)
                if best is None or info["score"] > best["score"]:
                    best = {**info, "opcao_alvo": option}
            if best and best["score"] > 0:
                details[i][j] = best
                # Pequeno bônus para slots obrigatórios: desempata contra
                # eletivas com o mesmo conteúdo (ex.: Cálculo obrigatório vs.
                # Cálculo como opção de eletiva).
                priority = 1.02 if slot.kind == "fixa" else 1.0
                token_bonus = 1.0 + min(0.02, 0.005 * len(best.get("tokens_comuns", [])))
                option_concepts = concepts(best["opcao_alvo"])
                specificity = 1.02 if (option_concepts - BROAD_CONCEPTS) else 1.0
                values[i][j] = (
                    best["score"] * slot.hours * priority
                    * specificity * token_bonus
                )

    n = max(ns, nt)
    max_value = max((max(row) for row in values), default=0.0)
    cost = [
        [
            max_value - (values[i][j] if i < ns and j < nt else 0.0)
            for j in range(n)
        ]
        for i in range(n)
    ]
    assignment = hungarian(cost)

    matches: list[tuple[int, int, dict[str, Any]]] = []
    for i in range(ns):
        j = assignment[i]
        if j is not None and 0 <= j < nt and values[i][j] > 0 and details[i][j] is not None:
            matches.append((i, j, details[i][j]))
    return matches


def confidence_summary(matches: list[tuple[int, int, dict[str, Any]]]) -> dict[str, int]:
    result = {"alta": 0, "media": 0, "baixa": 0}
    for _, _, info in matches:
        result[info["confianca"]] = result.get(info["confianca"], 0) + 1
    return result


def build_report(transcript: dict[str, Any], curriculum: dict[str, Any], sources: list[Source], slots: list[Slot], non_waivable: list[Slot], total_hours: int) -> dict[str, Any]:
    matches = run_match(sources, slots)
    matched_slots = {j for _, j, _ in matches}
    matched_hours = sum(slots[j].hours for _, j, _ in matches)
    waivable_hours = sum(slot.hours for slot in slots)
    non_waivable_hours = sum(slot.hours for slot in non_waivable)
    total_target_hours = waivable_hours + non_waivable_hours

    semesters_total = max(1, round(curriculum.get("duracao_meses", 6) / 6))
    hours_per_semester = total_target_hours / semesters_total
    remaining_hours = total_target_hours - matched_hours
    semesters_remaining = math.ceil(remaining_hours / hours_per_semester) if remaining_hours > 0 else 0
    confidence = sum(info["score"] * slots[j].hours for _, j, info in matches)
    confidence_avg = confidence / matched_hours if matched_hours else 0.0

    match_rows = []
    for i, j, info in matches:
        source = sources[i]
        slot = slots[j]
        match_rows.append(
            {
                "grupo": slot.group_name,
                "componente": slot.name,
                "opcao_alvo": info.get("opcao_alvo"),
                "horas_alvo": slot.hours,
                "origem_codigo": source.code,
                "origem_nome": source.name,
                "origem_periodo": source.period,
                "horas_origem": source.hours,
                "score": info["score"],
                "confianca": info["confianca"],
                "parcial": info["parcial"],
                "conceitos_alvo": info["conceitos_alvo"],
                "conceitos_origem": info["conceitos_origem"],
                "conceitos_comuns": info["conceitos_comuns"],
                "tokens_comuns": info["tokens_comuns"],
                "workload_fit": info["workload_fit"],
            }
        )
    match_rows.sort(key=lambda row: (row["grupo"], row["componente"], -row["score"]))

    remaining_rows = []
    for j, slot in enumerate(slots):
        if j in matched_slots:
            continue
        best_candidate = None
        for source in sources:
            for option in slot.options:
                info = pair_score(option, slot.hours, source.name, source.hours)
                if best_candidate is None or info["score"] > best_candidate["score"]:
                    best_candidate = {
                        "origem_codigo": source.code,
                        "origem_nome": source.name,
                        "opcao_alvo": option,
                        "score": info["score"],
                        "confianca": info["confianca"],
                    }
        remaining_rows.append(
            {
                "grupo": slot.group_name,
                "componente": slot.name,
                "horas": slot.hours,
                "tipo": slot.tipo,
                "melhor_candidato": best_candidate if best_candidate and best_candidate["score"] > 0 else None,
            }
        )

    non_waivable_rows = [
        {
            "grupo": slot.group_name,
            "componente": slot.name,
            "horas": slot.hours,
            "tipo": slot.tipo,
        }
        for slot in non_waivable
    ]

    warnings = [
        "Estimativa por nome + carga horária; não há ementa neste PoC.",
        "Pareamento um-para-um: uma disciplina de origem não preenche dois slots.",
        "Estágio, TCC, extensão, atividades complementares e projetos foram tratados como não abatíveis.",
        "A estimativa de semestres ignora pré-requisitos, oferta de disciplinas, limite de aproveitamento e regras da IES.",
        "Este resultado não é uma decisão oficial de equivalência.",
    ]
    if total_hours != total_target_hours:
        warnings.append(
            f"Soma dos grupos ({total_target_hours}h) difere da carga declarada ({total_hours}h)."
        )

    return {
        "metadata": {
            "transcricao_instituicao": transcript.get("instituicao"),
            "transcricao_curso": transcript.get("curso"),
            "curriculo_id": curriculum.get("id"),
            "curriculo_curso": curriculum.get("curso"),
            "curriculo_grau": curriculum.get("grau"),
            "curriculo_fonte": curriculum.get("fonte"),
            "gerado_em": "2026-10-26",
        },
        "resumo": {
            "horas_alvo_total": total_target_hours,
            "horas_abativeis": waivable_hours,
            "horas_nao_abativeis": non_waivable_hours,
            "horas_abatidas": matched_hours,
            "cobertura_abatível_pct": round(100 * matched_hours / waivable_hours, 1) if waivable_hours else 0,
            "cobertura_total_pct": round(100 * matched_hours / total_target_hours, 1) if total_target_hours else 0,
            "slots_abativeis": len(slots),
            "slots_cobertos": len(matches),
            "slots_restantes": len(slots) - len(matches),
            "disciplinas_origem_elegiveis": len(sources),
            "horas_restantes_abativeis": waivable_hours - matched_hours,
            "horas_restantes_totais": remaining_hours,
            "semestres_totais": semesters_total,
            "horas_por_semestre": round(hours_per_semester, 1),
            "semestres_restantes_bruto": semesters_remaining,
            "confianca_media": round(confidence_avg, 4),
            "matches_por_confianca": confidence_summary(matches),
        },
        "matches": match_rows,
        "restantes": remaining_rows,
        "nao_abativeis": non_waivable_rows,
        "avisos": warnings,
    }


def print_summary(report: dict[str, Any], top: int) -> None:
    meta = report["metadata"]
    summary = report["resumo"]
    print(f"\n{meta['transcricao_instituicao']} -> {meta['curriculo_id']}")
    print(
        f"  horas alvo: {summary['horas_alvo_total']} | "
        f"abatíveis: {summary['horas_abativeis']} | "
        f"não abatíveis: {summary['horas_nao_abativeis']}"
    )
    print(
        f"  abatidas: {summary['horas_abatidas']}h "
        f"({summary['cobertura_abatível_pct']}% do abatível; "
        f"{summary['cobertura_total_pct']}% do total)"
    )
    print(
        f"  slots: {summary['slots_cobertos']}/{summary['slots_abativeis']} cobertos | "
        f"restantes: {summary['slots_restantes']}"
    )
    print(
        f"  semestres restantes (bruto): {summary['semestres_restantes_bruto']} "
        f"de {summary['semestres_totais']} | "
        f"confiança média: {summary['confianca_media']}"
    )
    print(f"  confiança: {summary['matches_por_confianca']}")
    if top:
        print("  amostra de matches:")
        for row in report["matches"][:top]:
            option = f" [{row['opcao_alvo']}]" if row["opcao_alvo"] != row["componente"] else ""
            print(
                f"    {row['origem_codigo']} {row['origem_nome']} -> "
                f"{row['componente']}{option} | {row['score']} ({row['confianca']})"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args(argv)

    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    curriculum = json.loads(args.curriculum.read_text(encoding="utf-8"))
    sources = load_sources(transcript)
    slots, non_waivable, total_hours = build_slots(curriculum)
    report = build_report(transcript, curriculum, sources, slots, non_waivable, total_hours)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(report, args.top)
    print(f"  JSON: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
