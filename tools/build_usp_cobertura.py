#!/usr/bin/env python3
"""Gera cobertura temática USP -> alvos UNICAMP a partir de ementas públicas.

Alvos: componentes com código em data/targets/unicamp/*.json.
Origens: disciplinas das grades públicas da Poli-USP em data/targets/usp/*.json.
Método: TF-IDF das ementas + similaridade de nomes, sem LLM em runtime.

Uso:
    python3 -I tools/build_usp_cobertura.py
    python3 -I tools/build_usp_cobertura.py --unicamp-html-dir /tmp/unicamp-ementas/cache --usp-html-dir /tmp/usp-ementas/cache
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_unicamp_cobertura as base  # noqa: E402

USP_BASE = "https://uspdigital.usp.br/jupiterweb/obterDisciplina?sgldis="
USP_CATALOG = ROOT / "data" / "catalog" / "usp_jupiterweb_disciplinas.json"
OUT = ROOT / "data" / "ontology" / "usp_2026_regras.json"


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def parse_usp_page(raw: str) -> dict | None:
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    code_match = re.search(r"Disciplina:\s*([A-Z0-9]+)\s*-\s*(.*?)\s+Cr.ditos Aula", text)
    ementa_match = re.search(r"Ementa\s+(.*?)\s+(?:Bibliografia|Observa)", text, re.S)
    if not code_match or not ementa_match:
        return None
    hours_match = re.search(r"Carga Hor.ria Total:\s*(\d+)\s*h", text)
    return {
        "codigo": code_match.group(1),
        "nome": code_match.group(2).strip(),
        "ementa": ementa_match.group(1).strip(),
        "horas": int(hours_match.group(1)) if hours_match else None,
    }


def fetch(url: str, cache: Path | None, key: str) -> str | None:
    if cache is not None:
        path = cache / f"{key}.html"
        if not path.exists():
            return None
        return path.read_text(encoding="latin-1", errors="replace")
    request = urllib.request.Request(url, headers={"User-Agent": "equivale-usp-ementa/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("latin-1", errors="replace")
        except Exception as error:  # noqa: BLE001
            if attempt == 2:
                print(f"aviso: falha ao baixar {url}: {error}")
            else:
                time.sleep(1 + attempt)
    return None


def load_usp_catalog(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents: dict[str, dict] = {}
    for item in payload.get("disciplinas", []):
        code = str(item.get("codigo") or "")
        name = str(item.get("nome") or "")
        if not code or not name:
            continue
        text = " ".join(
            str(item.get(key) or "")
            for key in ("ementa", "objetivos", "conteudo")
        ).strip()
        documents[code] = {
            "codigo": code,
            "nome": name,
            "ementa": text,
            "horas": item.get("horas"),
            "fonte": str(item.get("fonte") or ""),
        }
    return documents


def source_hours() -> dict[str, int]:
    hours: dict[str, int] = {}
    for path in (ROOT / "data" / "targets" / "usp").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for group in data["grupos"]:
            for discipline in group.get("disciplinas", []):
                hours[discipline["codigo"]] = int(discipline["horas"])
    return hours


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unicamp-html-dir", type=Path, default=None)
    parser.add_argument("--usp-html-dir", type=Path, default=None)
    parser.add_argument(
        "--unicamp-catalog",
        type=Path,
        default=None,
        help="catálogo UNICAMP do crawler (default: data/catalog se existir)",
    )
    parser.add_argument(
        "--usp-catalog",
        type=Path,
        default=None,
        help="catálogo USP do crawler (default: data/catalog se existir)",
    )
    parser.add_argument(
        "--all-usp-sources",
        action="store_true",
        help="usa todas as disciplinas do catálogo USP, não só as das grades-alvo",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    targets = base.load_documents(args.unicamp_html_dir, args.unicamp_catalog)
    if not targets:
        raise SystemExit("Sem ementas UNICAMP.")
    source_docs: dict[str, dict] = {}
    source_urls: dict[str, str] = {}
    catalog_path = args.usp_catalog
    if catalog_path is None and args.usp_html_dir is None and USP_CATALOG.exists():
        catalog_path = USP_CATALOG
    if catalog_path is not None:
        if not catalog_path.exists():
            raise SystemExit(f"Catálogo USP não encontrado: {catalog_path}")
        all_sources = load_usp_catalog(catalog_path)
        allowed = None if args.all_usp_sources else set(source_hours())
        source_docs = {
            code: doc
            for code, doc in all_sources.items()
            if allowed is None or code in allowed
        }
        source_urls = {code: doc["fonte"] for code, doc in source_docs.items()}
        print(
            f"{len(source_docs)} ementas USP carregadas de {catalog_path}"
            + (" (todas)" if allowed is None else " (grades-alvo)"),
            file=sys.stderr,
        )
    else:
        for code in sorted(source_hours()):
            raw = fetch(f"{USP_BASE}{code}", args.usp_html_dir, code)
            if raw is None:
                continue
            doc = parse_usp_page(raw)
            if not doc:
                continue
            doc["fonte"] = f"{USP_BASE}{code}"
            source_docs[code] = doc
            source_urls[code] = doc["fonte"]

    if not source_docs:
        raise SystemExit("Sem ementas USP.")

    combined = {
        **{f"T:{code}": doc for code, doc in targets.items()},
        **{f"S:{code}": doc for code, doc in source_docs.items()},
    }
    vectors = base.build_vectors(combined)
    target_rows = base.target_components()
    source_hours_map = source_hours()
    rules = []

    for target in target_rows:
        target_doc = targets.get(target["codigo"])
        target_vec = vectors.get(f"T:{target['codigo']}")
        if not target_doc or not target_vec:
            continue
        candidates = []
        for code, source in source_docs.items():
            if code == target["codigo"]:
                continue
            source_vec = vectors.get(f"S:{code}")
            if not source_vec:
                continue
            coverage, precision, cosine, shared = base.similarity(target_vec, source_vec)
            content_score = 0.55 * coverage + 0.25 * precision + 0.2 * cosine
            name_score = base.name_similarity(target["nome"], source["nome"])
            if name_score < 0.6 and content_score < 0.05:
                continue
            if name_score >= 0.6:
                max_hours = target["horas"]
                ignore = bool(source.get("horas") and source["horas"] < target["horas"])
                score = max(0.7, name_score)
                confidence = "alta" if name_score >= 0.85 else "media" if name_score >= 0.75 else "baixa"
                label = f"nome: {source['nome']}"
            else:
                strong_content = content_score >= 0.35
                source_hours_value = source_hours_map.get(code) or source.get("horas") or target["horas"]
                max_hours = target["horas"] if strong_content else min(target["horas"], source_hours_value)
                ignore = bool(strong_content and source_hours_value < target["horas"])
                score = min(0.9, 0.55 + 0.7 * content_score)
                confidence = "alta" if strong_content else "media" if content_score >= 0.18 else "baixa"
                terms = sorted(shared, key=lambda token: -target_vec.get(token, 0))[:8]
                label = "ementa: " + ", ".join(terms)
            candidates.append(
                {
                    "codigo": code,
                    "nome": source["nome"],
                    "horas_cobertura": max_hours,
                    "score": round(score, 4),
                    "confianca": confidence,
                    "ignorar_carga_horaria": ignore,
                    "rotulo": label,
                    "fonte": source_urls[code],
                    "_content": content_score,
                    "_name": name_score,
                }
            )
        candidates.sort(key=lambda item: (-item["score"], -item["_content"], -item["_name"], item["codigo"]))
        candidates = candidates[:30]
        if not candidates:
            continue
        for item in candidates:
            item.pop("_content")
            item.pop("_name")
        slug = re.sub(r"[^a-z0-9]+", "-", target["curso"].lower()).strip("-")
        code_slug = re.sub(r"[^a-z0-9]+", "-", target["codigo"].lower()).strip("-")
        rules.append(
            {
                "id": f"usp-auto-{slug}-{code_slug}",
                "tipo": "cobertura_tematica_automatica",
                "alvo": {
                    "instituicao": "UNICAMP",
                    "curso": target["curso"],
                    "codigo": target["codigo"],
                    "componente": target["nome"],
                },
                "origem_instituicao": "USP",
                "origens": candidates,
                "fonte": target_doc["fonte"],
                "observacao": (
                    "Gerado por TF-IDF de ementas públicas USP x UNICAMP e similaridade de nomes; "
                    "não é equivalência oficial. Limiares: nome >= 0.60; conteúdo >= 0.05; top 30."
                ),
            }
        )

    payload = {
        "versao": "2026-10-27",
        "gerado_por": "tools/build_usp_cobertura.py",
        "metodo": "TF-IDF de ementas USP/UNICAMP + similaridade de nomes; sem LLM",
        "escopo": "disciplinas das grades Poli-USP -> componentes UNICAMP",
        "coletado_em": "2026-10-27",
        "observacao": "Regras automáticas; a decisão final é da instituição.",
        "regras": rules,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"{args.out}: {len(rules)} regras, "
        f"{sum(len(rule['origens']) for rule in rules)} origens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
