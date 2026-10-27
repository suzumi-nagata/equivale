#!/usr/bin/env python3
"""Extrai os currículos plenos 2026 da UNICAMP (Eng. Computação e Eng. Elétrica).

Fonte: Catálogo dos Cursos de Graduação da UNICAMP (DAC), 2026.
Saída: data/sources/unicamp/*.json

Uso:
    python3 -I tools/extract_unicamp_2026.py
    python3 -I tools/extract_unicamp_2026.py --html-dir /tmp/unicamp-curriculos
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026"

SOURCES = {
    "eng_computacao_2026": {
        "curso": "Engenharia de Computação",
        "codigo_curso": "34G",
        "url": f"{BASE}/cursos/34g/curriculo.html",
        "proposta_url": f"{BASE}/cursos/34g/sugestao.html",
        "html_file": "catalogo2026_cursos_34g_curriculo.html",
    },
    "eng_eletrica_2026": {
        "curso": "Engenharia Elétrica",
        "codigo_curso": "41G",
        "url": f"{BASE}/cursos/41g/curriculo.html",
        "proposta_url": f"{BASE}/cursos/41g/sugestao.html",
        "html_file": "catalogo2026_cursos_41g_curriculo.html",
    },
}

CERTIFICADOS_FEEC = [
    ("Fundamentos da Engenharia de Computação", "cursos 11 e 41"),
    ("Fundamentos da Engenharia Elétrica", "curso 34, habilitação AB"),
    ("Engenharia de Som", "cursos 11, 41 e 34"),
    ("Telecomunicações e Telemática", "cursos 11, 41 e 34"),
    ("Sistemas de Energia Elétrica", "cursos 11 e 41"),
    ("Engenharia Biomédica", "cursos 11, 41 e 34"),
    ("Sistemas de Controle", "cursos 11, 41 e 34, conforme modalidade"),
    ("Sistemas Distribuídos e Redes de Computadores", "cursos 11, 41 e 34"),
    ("Automação e Sistemas Inteligentes", "cursos 11, 41 e 34"),
    ("Otimização de Sistemas", "cursos 11, 41 e 34"),
    ("Técnicas de Projeto de Sistemas Embarcados", "cursos 11, 41 e 34"),
    ("Eletrônica, Microeletrônica e Optoeletrônica", "cursos 11, 41 e 34"),
    ("Aplicações de Energia Elétrica", "cursos 11 e 41"),
]

CERTIFICADOS_IC = [
    "Engenharia de Algoritmos",
    "Tecnologias para Internet",
    "Computação Visual",
    "Engenharia de Software",
    "Sistemas de Informação",
    "Inteligência Artificial, Aprendizado de Máquina e Ciência de Dados",
]

CERTIFICADOS_FEEC_PDF = (
    "http://www.dac.unicamp.br/portal/storage/app/media/Certificado%20de%20Estudo/"
    "Certificado_de_Estudos_FEEC-Catalogo_2025.pdf"
)


class CurriculumParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h2: str | None = None
        self.h3: str | None = None
        self.capture: str | None = None
        self.buffer: list[str] = []
        self.group: str | None = None
        self.credits: int | None = None
        self.table: dict | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.tables: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"h2", "h3", "p"}:
            self.capture = tag
            self.buffer = []
        elif tag == "table":
            self.table = {
                "h2": self.h2,
                "h3": self.h3,
                "group": self.group,
                "credits": self.credits,
                "rows": [],
            }
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"h2", "h3", "p"} and self.capture == tag:
            text = " ".join("".join(self.buffer).split())
            if tag == "h2":
                self.h2 = text
                self.h3 = None
                self.group = None
                self.credits = None
            elif tag == "h3":
                self.h3 = text
                self.group = None
                self.credits = None
            else:
                match = re.search(
                    r"Disciplinas eletivas\s+([IVX]+)\s*:.*?(\d+)\s*cr[eé]ditos",
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    self.group = f"Eletivas {match.group(1)}"
                    self.credits = int(match.group(2))
            self.capture = None
            self.buffer = []
        elif tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if re.fullmatch(r"\d+", value) else None


def parse_rows(rows: list[list[str]], tipo: str) -> tuple[list[dict], list[str]]:
    disciplines: list[dict] = []
    notes: list[str] = []
    for row in rows:
        if len(row) < 4:
            text = " ".join(row).strip()
            if text:
                notes.append(text)
            continue
        code, hours, credits, name = row[:4]
        code = code.strip()
        name = name.strip()
        if not code and not name:
            continue
        free = bool(re.fullmatch(r"(?:EX|MX|IX)---", code)) or "qualquer disciplina" in name.lower()
        disciplines.append(
            {
                "codigo": code,
                "codigo_normalizado": re.sub(r"\s+", "", code),
                "nome": name,
                "horas": parse_int(hours),
                "creditos": parse_int(credits),
                "tipo": "eletiva_livre" if free else tipo,
            }
        )
    return disciplines, notes


def build(source_key: str, meta: dict, html: str) -> dict:
    parser = CurriculumParser()
    parser.feed(html)

    common: list[dict] = []
    variants: dict[str, dict] = {}

    for table in parser.tables:
        h2 = table["h2"] or ""
        h3 = table["h3"] or ""
        rows = table["rows"]

        if h3.startswith("Núcleo Comum"):
            parsed, notes = parse_rows(rows, "obrigatoria_comum")
            common.extend(parsed)
            continue

        variant_match = re.match(r"^(AA|AB|AX)\s*-\s*(.+)$", h2)
        if variant_match:
            variant_code, variant_name = variant_match.groups()
            variant = variants.setdefault(
                variant_code,
                {
                    "codigo": variant_code,
                    "nome": variant_name.strip(),
                    "tipo": "pre_opcao" if variant_code == "AX" else "habilitacao",
                    "obrigatorias": [],
                    "eletivas": [],
                },
            )
            if h3.startswith("Disciplinas Obrigatórias"):
                parsed, notes = parse_rows(rows, "obrigatoria_habilitacao")
                variant["obrigatorias"].extend(parsed)
                if notes:
                    variant["observacoes"] = notes
            elif h3.startswith("Disciplinas Eletivas"):
                parsed, notes = parse_rows(rows, "eletiva")
                group = {
                    "grupo": table["group"] or "Eletivas",
                    "creditos_exigidos": table["credits"],
                    "disciplinas": parsed,
                }
                if notes:
                    group["observacao"] = " ".join(notes)
                variant["eletivas"].append(group)
            continue

        if h3.startswith("Disciplinas Eletivas"):
            variant = variants.setdefault(
                meta["codigo_curso"],
                {
                    "codigo": meta["codigo_curso"],
                    "nome": meta["curso"],
                    "tipo": "curriculo_pleno",
                    "obrigatorias": [],
                    "eletivas": [],
                },
            )
            parsed, notes = parse_rows(rows, "eletiva")
            group = {
                "grupo": table["group"] or "Eletivas",
                "creditos_exigidos": table["credits"],
                "disciplinas": parsed,
            }
            if notes:
                group["observacao"] = " ".join(notes)
            variant["eletivas"].append(group)

    data = {
        "instituicao": "UNICAMP",
        "curso": meta["curso"],
        "codigo_curso": meta["codigo_curso"],
        "curriculo_versao": "2026",
        "fonte": meta["url"],
        "proposta_fonte": meta["proposta_url"],
        "coletado_em": "2026-10-26",
        "nucleo_comum": common,
        "variantes": list(variants.values()),
        "observacoes": [
            "Currículo pleno do Catálogo 2026; os créditos de eletivas são requisitos de grupo, não disciplinas únicas.",
            "AA e AB são habilitações distintas; não somar as listas sem escolher a habilitação.",
        ],
    }

    if source_key == "eng_computacao_2026":
        data["certificados"] = [
            {
                "nome": name,
                "tipo": "certificado_ic",
                "fonte": meta["proposta_url"],
                "observacao": "Certificado de estudos do IC; não é habilitação.",
            }
            for name in CERTIFICADOS_IC
        ] + [
            {
                "nome": name,
                "publico_alvo": audience,
                "tipo": "certificado_feec",
                "fonte": CERTIFICADOS_FEEC_PDF,
                "observacao": "Certificado de estudos da FEEC; não é habilitação.",
            }
            for name, audience in CERTIFICADOS_FEEC
        ]
        data["observacoes"].append(
            "A variante AX é a grade provisória para matrícula antes da opção por AA/AB."
        )
    else:
        data["certificados"] = [
            {
                "nome": name,
                "publico_alvo": audience,
                "tipo": "certificado_feec",
                "fonte": CERTIFICADOS_FEEC_PDF,
                "observacao": "Certificado de estudos da FEEC; não é habilitação.",
            }
            for name, audience in CERTIFICADOS_FEEC
        ]
        data["observacoes"].append(
            "O currículo pleno 41G não define habilitações; as ênfases/tracks aparecem como certificados de estudos da FEEC."
        )
        data["observacoes"].append(
            "Para o perfil de Automação e Controle, os certificados mais próximos são 'Sistemas de Controle' e 'Automação e Sistemas Inteligentes'."
        )

    return data


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "equivale-curriculum-collector/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/sources/unicamp"))
    parser.add_argument("--html-dir", type=Path, default=None, help="Usar HTMLs locais em vez de baixar")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for source_key, meta in SOURCES.items():
        if args.html_dir:
            html = (args.html_dir / meta["html_file"]).read_text(encoding="utf-8", errors="replace")
        else:
            html = fetch(meta["url"])
        data = build(source_key, meta, html)
        output = args.out_dir / f"{source_key}.json"
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"{output}: {len(data['nucleo_comum'])} comuns, "
            f"{len(data['variantes'])} variante(s), "
            f"{len(data.get('certificados', []))} certificado(s)"
        )
        for variant in data["variantes"]:
            print(
                f"  {variant['codigo']} {variant['nome']} ({variant['tipo']}): "
                f"{len(variant['obrigatorias'])} obrigatórias, {len(variant['eletivas'])} grupos de eletivas"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
