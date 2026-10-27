#!/usr/bin/env python3
"""Prototype transcript parser for UNICAMP and USP (Júpiter) PDFs.

Uses poppler's `pdftotext -bbox-layout` for word coordinates and only the
Python standard library. No third-party Python packages are required.

Privacy: this parser deliberately extracts only academic rows. Identity
fields (name, RA/RG, birth date, etc.) are never parsed or emitted.

Usage:
    python3 -I parse_transcripts.py HISTORICO.pdf [HISTORICO2.pdf ...] \
        --out-dir /tmp/transcript-parser --sample 5

The output JSON contains academic data; store it somewhere private and do
not commit it. The PDFs themselves are read in place and never copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PARSER_VERSION = "0.1.0-prototype"

APPROVED_UNICAMP = {"aprovado", "aprovado_proficiencia", "suficiente"}
APPROVED_USP = {"aprovado"}

USP_SITUACOES = {
    "A": "aprovado",
    "AE": "aproveitamento_estudo",
    "DS": "dispensado",
    "RN": "reprovado_nota",
    "RF": "reprovado_frequencia",
    "RA": "reprovado_nota_frequencia",
    "T": "trancado",
    "MA": "matriculado",
    "P": "pendente",
    "I": "inscrito",
    "IR": "inscricao_reservada",
    "IT": "inscricao_turma_lotada",
    "IP": "inscricao_optativa_preterida",
    "IL": "inscricao_lista_espera",
}


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    y0: float
    y1: float


@dataclass
class Row:
    y: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class UnicampLayout:
    name_x0: float
    num_x0: float
    situacao_x0: float


@dataclass
class UspLayout:
    anchors: dict[str, float]
    name_x0: float
    num_x0: float


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def run_pdftotext(pdf: Path, *, bbox: bool = False, layout: bool = False) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        raise SystemExit("pdftotext não encontrado; instale poppler-utils")
    args = [exe]
    if bbox:
        args.append("-bbox-layout")
    if layout:
        args.append("-layout")
    args.extend([str(pdf), "-"])
    proc = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise SystemExit(f"pdftotext falhou: {proc.stderr.strip()}")
    return proc.stdout


def strip_doctype(xml: str) -> str:
    return re.sub(r"<!DOCTYPE[^>]*>", "", xml, count=1)


def parse_pages(xml: str) -> list[list[Row]]:
    root = ET.fromstring(strip_doctype(xml))
    pages: list[list[Row]] = []
    for page in (el for el in root.iter() if local_name(el.tag) == "page"):
        line_items: list[tuple[float, list[Word]]] = []
        for line in (el for el in page.iter() if local_name(el.tag) == "line"):
            y = float(line.attrib["yMin"])
            words: list[Word] = []
            for word in line:
                if local_name(word.tag) != "word":
                    continue
                text = (word.text or "").strip()
                if not text:
                    continue
                words.append(
                    Word(
                        text=text,
                        x0=float(word.attrib["xMin"]),
                        x1=float(word.attrib["xMax"]),
                        y0=float(word.attrib["yMin"]),
                        y1=float(word.attrib["yMax"]),
                    )
                )
            if words:
                line_items.append((y, words))

        rows: list[Row] = []
        for y, words in sorted(line_items, key=lambda item: item[0]):
            target: Row | None = None
            for row in rows:
                if abs(row.y - y) <= 2.0:
                    target = row
                    break
            if target is None:
                target = Row(y=y)
                rows.append(target)
            target.words.extend(words)

        rows.sort(key=lambda row: row.y)
        for row in rows:
            row.words.sort(key=lambda word: word.x0)
            seen: set[tuple[str, int, int]] = set()
            unique: list[Word] = []
            for word in row.words:
                key = (word.text, round(word.x0, 1), round(word.y0, 1))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(word)
            row.words = unique
        pages.append(rows)
    return pages


def detect_institution(plain_text: str) -> str:
    upper = plain_text.upper()
    if "UNIVERSIDADE ESTADUAL DE CAMPINAS" in upper:
        return "unicamp"
    if "JÚPITER" in upper or "JUPITER" in upper or "HISTÓRICO ESCOLAR FINAL" in upper:
        return "usp"
    raise SystemExit("Não reconheci a instituição do PDF (esperado UNICAMP ou USP/Júpiter).")


UNICAMP_CODE_RE = re.compile(r"^[A-Z]{1,3}\s?\d{3}$")
USP_CODE_RE = re.compile(r"^(?:\d{7}|[A-Z]{2,4}\d{4})$")


def extract_code(row: Row, institution: str) -> tuple[str | None, set[int]]:
    """Return normalized code and the indexes of the words that form it."""
    if institution == "unicamp":
        for index, word in enumerate(row.words):
            if word.x0 >= 100:
                break
            if index + 1 < len(row.words):
                candidate = f"{word.text} {row.words[index + 1].text}"
                if UNICAMP_CODE_RE.fullmatch(candidate):
                    return candidate.replace(" ", ""), {index, index + 1}
            if UNICAMP_CODE_RE.fullmatch(word.text):
                return word.text, {index}
        return None, set()

    for index, word in enumerate(row.words):
        if word.x0 >= 100:
            break
        if USP_CODE_RE.fullmatch(word.text):
            return word.text, {index}
    return None, set()


def code_text(row: Row, indexes: set[int]) -> str:
    return " ".join(row.words[index].text for index in sorted(indexes))


def unicamp_layout(rows: list[Row]) -> UnicampLayout | None:
    for row in rows:
        texts = {word.text for word in row.words}
        if {"Código", "Crd", "Situação"}.issubset(texts):
            x_nome = min((word.x0 for word in row.words if word.text == "Nome"), default=75.0)
            x_media = min((word.x0 for word in row.words if word.text == "Média"), default=285.0)
            return UnicampLayout(
                name_x0=x_nome - 10.0,
                num_x0=x_media - 5.0,
                situacao_x0=395.0,
            )
    return None


def usp_layout(rows: list[Row]) -> UspLayout | None:
    for row in rows:
        texts = {word.text for word in row.words}
        if {"Sigla", "AU", "FREQ", "NOTA"}.issubset(texts):
            anchors: dict[str, float] = {}
            for word in row.words:
                if word.text in {"AU", "TR", "CH", "CE", "CP", "EXT", "ATPA", "FREQ", "NOTA"}:
                    anchors[word.text] = (word.x0 + word.x1) / 2.0
            x_nome = min((word.x0 for word in row.words if word.text == "Nome"), default=135.7)
            x_au = min((word.x0 for word in row.words if word.text == "AU"), default=323.45)
            return UspLayout(anchors=anchors, name_x0=max(95.0, x_nome - 40.0), num_x0=x_au - 20.0)
    return None


def semester_unicamp(row: Row) -> str | None:
    match = re.search(r"(\d)º\s*Semestre\s+de\s+(\d{4})", row.text, re.IGNORECASE)
    if match:
        return f"{match.group(2)}.{match.group(1)}"
    return None


def semester_usp(row: Row) -> str | None:
    match = re.search(r"(\d{4})\s+(\d)º\.\s*Semestre", row.text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return None


def unicamp_name(rows: list[Row], index: int, code_indexes: set[int], layout: UnicampLayout) -> str:
    row = rows[index]
    parts = [
        word.text
        for word_index, word in enumerate(row.words)
        if word_index not in code_indexes and layout.name_x0 <= word.x0 < layout.num_x0
    ]

    for following in rows[index + 1 :]:
        if extract_code(following, "unicamp")[0]:
            break
        normalized = normalize(following.text)
        if normalized.startswith(("prof", "profa")):
            break
        upper = following.text.upper()
        if "CÓDIGO DE AUTENTICIDADE" in upper or "EMISSÃO:" in upper or "PAG.:" in upper:
            break
        if semester_unicamp(following):
            break
        name_words = [
            word.text for word in following.words if layout.name_x0 <= word.x0 < layout.num_x0
        ]
        if name_words:
            parts.extend(name_words)

    return " ".join(parts).strip()


def usp_name(rows: list[Row], index: int, code_indexes: set[int], layout: UspLayout) -> str:
    y = rows[index].y
    parts: list[tuple[float, float, str]] = []

    for row in rows:
        if abs(row.y - y) > 10.0:
            continue
        if row is not rows[index] and extract_code(row, "usp")[0]:
            continue
        if semester_usp(row):
            continue
        normalized = normalize(row.text)
        if normalized.startswith("emitido em") or normalized.startswith("código de controle"):
            continue
        for word_index, word in enumerate(row.words):
            if row is rows[index] and word_index in code_indexes:
                continue
            if layout.name_x0 <= word.x0 < layout.num_x0:
                parts.append((row.y, word.x0, word.text))

    parts.sort(key=lambda item: (item[0], item[1]))
    return " ".join(item[2] for item in parts).strip()


def parse_number(text: str) -> float | None:
    if not text:
        return None
    text = text.strip()
    if text in {"----", "-", "—", "–"}:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def parse_int(text: str) -> int | None:
    value = parse_number(text)
    return int(value) if value is not None else None


def map_situacao_unicamp(original: str) -> str:
    text = normalize(original)
    if not text:
        return "desconhecida"
    if "aprovado" in text and "profic" in text:
        return "aprovado_proficiencia"
    if "aprovado" in text:
        return "aprovado"
    if "desist" in text:
        return "desistencia"
    if "suficiente" in text:
        return "suficiente"
    if "reprovado" in text:
        return "reprovado"
    if "tranc" in text:
        return "trancado"
    return "outro"


def map_situacao_usp(original: str | None) -> str:
    if not original:
        return "desconhecida"
    return USP_SITUACOES.get(original.upper(), "outro")


def unicamp_fields(row: Row) -> dict[str, Any]:
    media = " ".join(word.text for word in row.words if 280.0 <= word.x0 < 325.0)
    ch = " ".join(word.text for word in row.words if 325.0 <= word.x0 < 360.0)
    crd = " ".join(word.text for word in row.words if 360.0 <= word.x0 < 395.0)
    situacao = " ".join(word.text for word in row.words if word.x0 >= 395.0)
    return {
        "media": parse_number(media),
        "horas": parse_int(ch),
        "creditos": parse_int(crd),
        "situacao_original": situacao.strip(),
        "situacao": map_situacao_unicamp(situacao),
    }


def usp_fields(row: Row, layout: UspLayout) -> dict[str, Any]:
    words = [word for word in row.words if word.x0 >= layout.num_x0]
    situacao_original: str | None = None
    if words and re.fullmatch(r"[A-Z]{1,2}", words[-1].text):
        situacao_original = words[-1].text
        words = words[:-1]

    values: dict[str, str] = {}
    for word in words:
        if not re.fullmatch(r"\d+(?:[.,]\d+)?", word.text):
            continue
        center = (word.x0 + word.x1) / 2.0
        label = min(layout.anchors, key=lambda key: abs(layout.anchors[key] - center))
        values[label] = word.text

    au = parse_int(values.get("AU", ""))
    tr = parse_int(values.get("TR", ""))
    ch = parse_int(values.get("CH", ""))
    if ch is None and (au is not None or tr is not None):
        ch = (au or 0) * 15 + (tr or 0) * 30

    return {
        "media": parse_number(values.get("NOTA", "")),
        "horas": ch,
        "creditos_aula": au,
        "creditos_trabalho": tr,
        "creditos_total": (au or 0) + (tr or 0) if (au is not None or tr is not None) else None,
        "horas_estagio": parse_int(values.get("CE", "")),
        "horas_praticas": parse_int(values.get("CP", "")),
        "horas_extensao": parse_int(values.get("EXT", "")),
        "atpa": parse_int(values.get("ATPA", "")),
        "frequencia": parse_int(values.get("FREQ", "")),
        "situacao_original": situacao_original,
        "situacao": map_situacao_usp(situacao_original),
    }


def parse_usp_course(plain_text: str) -> dict[str, str]:
    course: dict[str, str] = {}
    for label, key in (
        ("Unidade", "unidade"),
        ("Curso", "curso"),
        ("Habilitação", "habilitacao"),
        ("Módulo", "modulo"),
    ):
        match = re.search(rf"^[ \t]*{re.escape(label)}:[ \t]*(.+)$", plain_text, re.MULTILINE)
        if not match:
            continue
        value = re.split(r"\s{2,}", match.group(1).strip())[0].strip()
        if value:
            course[key] = value
    return course


def declared_totals(plain_text: str, institution: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", plain_text)
    if institution == "unicamp":
        match = re.search(
            r"Total da Carga Horária Total da Carga Horária Supervisionada Total de Créditos "
            r"(\d+) (\d+) (\d+)",
            normalized,
        )
        if match:
            return {
                "horas": int(match.group(1)),
                "horas_supervisionadas": int(match.group(2)),
                "creditos": int(match.group(3)),
            }
        return {}

    totals: dict[str, Any] = {}
    credits = re.search(
        r"Créditos obtidos:\s*aula\s*:?\s*(\d+)\s*trabalho\s*:?\s*(\d+)\s*total\s*:?\s*(\d+)",
        normalized,
    )
    if credits:
        totals.update(
            {
                "creditos_aula": int(credits.group(1)),
                "creditos_trabalho": int(credits.group(2)),
                "creditos_total": int(credits.group(3)),
            }
        )
    hours = re.search(r"Carga Horária Total:\s*(\d+)\s*h", normalized)
    if hours:
        totals["horas"] = int(hours.group(1))
    geral = re.search(r"Total geral.*?:\s*(\d+)", normalized)
    if geral:
        totals["total_geral"] = int(geral.group(1))
    return totals


def validate_codes(layout_text: str, institution: str, disciplines: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare parsed codes with the codes visible in the layout-preserving text."""
    if institution == "unicamp":
        pattern = re.compile(r"^[ \t]*([A-Z]{1,3}[ \t]?\d{3})[ \t]+", re.MULTILINE)
    else:
        pattern = re.compile(r"^[ \t]*(\d{7}|[A-Z]{2,4}\d{4})[ \t]+", re.MULTILINE)
    text_codes = [re.sub(r"\s+", "", match.group(1)) for match in pattern.finditer(layout_text)]
    parsed_codes = [item["codigo_normalizado"] for item in disciplines]
    text_counter = Counter(text_codes)
    parsed_counter = Counter(parsed_codes)
    return {
        "texto": len(text_codes),
        "parseado": len(parsed_codes),
        "confere": text_counter == parsed_counter,
        "faltando": dict(text_counter - parsed_counter),
        "extra": dict(parsed_counter - text_counter),
    }


def summarize(disciplines: list[dict[str, Any]], declared: dict[str, Any], institution: str) -> dict[str, Any]:
    if institution == "unicamp":
        approved = [item for item in disciplines if item["situacao"] in APPROVED_UNICAMP]
        horas = sum((item["horas"] or 0) for item in approved)
        creditos = sum((item["creditos"] or 0) for item in approved)
        conferem = None
        if declared:
            conferem = declared.get("horas") == horas and declared.get("creditos") == creditos
        return {
            "disciplinas": len(disciplines),
            "aprovadas": len(approved),
            "horas_aprovadas": horas,
            "creditos_aprovados": creditos,
            "totais_declarados": declared,
            "totais_conferem": conferem,
        }

    approved = [item for item in disciplines if item["situacao"] in APPROVED_USP]
    horas = sum((item["horas"] or 0) for item in approved)
    au = sum((item["creditos_aula"] or 0) for item in approved)
    tr = sum((item["creditos_trabalho"] or 0) for item in approved)
    conferem = None
    if declared:
        conferem = (
            declared.get("horas") == horas
            and declared.get("creditos_aula") == au
            and declared.get("creditos_trabalho") == tr
        )
    return {
        "disciplinas": len(disciplines),
        "aprovadas": len(approved),
        "horas_aprovadas": horas,
        "creditos_aula": au,
        "creditos_trabalho": tr,
        "creditos_total": au + tr,
        "totais_declarados": declared,
        "totais_conferem": conferem,
    }


def parse_transcript(pdf: Path) -> dict[str, Any]:
    plain_text = run_pdftotext(pdf, bbox=False)
    institution = detect_institution(plain_text)
    pages = parse_pages(run_pdftotext(pdf, bbox=True))

    disciplines: list[dict[str, Any]] = []
    warnings: list[str] = []
    current_period: str | None = None
    layout: UnicampLayout | UspLayout | None = None

    for page_number, rows in enumerate(pages, start=1):
        if institution == "unicamp":
            layout = unicamp_layout(rows) or layout
        else:
            layout = usp_layout(rows) or layout
        if layout is None:
            continue

        for index, row in enumerate(rows):
            if institution == "unicamp":
                period = semester_unicamp(row)
                if period:
                    current_period = period
                    continue
                code, code_indexes = extract_code(row, "unicamp")
                if not code:
                    continue
                original_code = code_text(row, code_indexes)
                name = unicamp_name(rows, index, code_indexes, layout)
                fields = unicamp_fields(row)
                if not fields["situacao_original"] and fields["horas"] is None:
                    continue
                disciplines.append(
                    {
                        "periodo": current_period,
                        "codigo": original_code,
                        "codigo_normalizado": code,
                        "nome": name,
                        "horas": fields["horas"],
                        "creditos": fields["creditos"],
                        "creditos_aula": None,
                        "creditos_trabalho": None,
                        "horas_estagio": None,
                        "horas_praticas": None,
                        "horas_extensao": None,
                        "atpa": None,
                        "frequencia": None,
                        "media": fields["media"],
                        "situacao": fields["situacao"],
                        "situacao_original": fields["situacao_original"],
                        "pagina": page_number,
                    }
                )
                if not name:
                    warnings.append(f"UNICAMP {code} ({current_period}) sem nome")
                if fields["situacao"] in APPROVED_UNICAMP and fields["horas"] is None:
                    warnings.append(f"UNICAMP {code} ({current_period}) aprovada sem carga horária")
            else:
                period = semester_usp(row)
                if period:
                    current_period = period
                    continue
                code, code_indexes = extract_code(row, "usp")
                if not code:
                    continue
                original_code = code_text(row, code_indexes)
                name = usp_name(rows, index, code_indexes, layout)
                fields = usp_fields(row, layout)
                if (
                    fields["horas"] is None
                    and fields["creditos_aula"] is None
                    and fields["situacao_original"] is None
                ):
                    continue
                disciplines.append(
                    {
                        "periodo": current_period,
                        "codigo": original_code,
                        "codigo_normalizado": code,
                        "nome": name,
                        "horas": fields["horas"],
                        "creditos": None,
                        "creditos_aula": fields["creditos_aula"],
                        "creditos_trabalho": fields["creditos_trabalho"],
                        "horas_estagio": fields["horas_estagio"],
                        "horas_praticas": fields["horas_praticas"],
                        "horas_extensao": fields["horas_extensao"],
                        "atpa": fields["atpa"],
                        "frequencia": fields["frequencia"],
                        "media": fields["media"],
                        "situacao": fields["situacao"],
                        "situacao_original": fields["situacao_original"],
                        "pagina": page_number,
                    }
                )
                if not name:
                    warnings.append(f"USP {code} ({current_period}) sem nome")
                if fields["situacao"] == "aprovado" and fields["horas"] is None:
                    warnings.append(f"USP {code} ({current_period}) aprovada sem carga horária")

    layout_text = run_pdftotext(pdf, layout=True)
    course = parse_usp_course(layout_text) if institution == "usp" else None
    code_check = validate_codes(layout_text, institution, disciplines)
    if institution == "unicamp":
        warnings.append("UNICAMP: curso/catálogo não vêm no PDF; selecionar manualmente")

    declared = declared_totals(plain_text, institution)
    summary = summarize(disciplines, declared, institution)
    if summary["totais_conferem"] is False:
        warnings.append(
            "Totais divergentes: "
            f"calculado={summary} declarado={declared}"
        )
    if not code_check["confere"]:
        warnings.append(f"Códigos divergentes: {code_check}")

    return {
        "parser_version": PARSER_VERSION,
        "instituicao": institution.upper(),
        "arquivo_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "curso": course,
        "disciplinas": disciplines,
        "validacao_codigos": code_check,
        "resumo": summary,
        "avisos": warnings,
    }


def print_summary(result: dict[str, Any], out_path: Path, sample: int) -> None:
    summary = result["resumo"]
    print(f"\n{result['instituicao']} — sha256:{result['arquivo_sha256'][:12]}")
    print(f"  disciplinas: {summary['disciplinas']} | aprovadas: {summary['aprovadas']}")
    print(f"  horas aprovadas: {summary['horas_aprovadas']} (declarado {summary['totais_declarados'].get('horas')})")
    if result["instituicao"] == "UNICAMP":
        print(
            f"  créditos aprovados: {summary['creditos_aprovados']} "
            f"(declarado {summary['totais_declarados'].get('creditos')})"
        )
    else:
        print(
            f"  créditos: {summary['creditos_aula']} AU + {summary['creditos_trabalho']} TR "
            f"= {summary['creditos_total']} "
            f"(declarado {summary['totais_declarados'].get('creditos_total')})"
        )
    print(f"  totais conferem: {summary['totais_conferem']}")
    check = result.get("validacao_codigos", {})
    if check:
        print(
            f"  códigos: {check['texto']} no texto / {check['parseado']} no parse "
            f"(confere: {check['confere']})"
        )
    if result.get("curso"):
        print(f"  curso: {result['curso']}")
    print(f"  JSON: {out_path}")
    if result["avisos"]:
        print(f"  avisos: {len(result['avisos'])}")
        for warning in result["avisos"][:5]:
            print(f"    - {warning}")
    if sample:
        print(f"  amostra ({min(sample, len(result['disciplinas']))}):")
        for item in result["disciplinas"][:sample]:
            print(
                f"    {item['periodo']} {item['codigo']} | {item['nome']} | "
                f"{item['horas']}h | {item['situacao']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path, help="Histórico(s) em PDF")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/tmp/transcript-parser"),
        help="Diretório para o JSON normalizado (padrão: /tmp/transcript-parser)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=3,
        help="Quantidade de disciplinas para imprimir na amostra (0 desliga)",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        if not pdf.is_file():
            print(f"arquivo não encontrado: {pdf}", file=sys.stderr)
            return 2
        result = parse_transcript(pdf)
        digest = result["arquivo_sha256"][:12]
        out_path = args.out_dir / f"{result['instituicao'].lower()}_{digest}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print_summary(result, out_path, args.sample)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
