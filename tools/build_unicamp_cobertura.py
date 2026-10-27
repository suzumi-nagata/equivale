#!/usr/bin/env python3
"""Gera automaticamente regras de cobertura temática a partir de ementas.

Fonte: Catálogo dos Cursos de Graduação 2026 da UNICAMP (DAC).
Entrada:
  - data/targets/unicamp/*.json  (componentes-alvo com código)
  - páginas públicas de disciplinas do catálogo (ementas)
Saída:
  - data/ontology/unicamp_2026_regras.json

Método (sem LLM):
  - TF-IDF de tokens das ementas (português, stopwords, normalização simples);
  - similaridade de conteúdo (cobertura/precisão/cosseno) e similaridade de nome;
  - candidatos acima de limiares, com termos compartilhados e URL da ementa.

Uso:
    python3 -I tools/build_unicamp_cobertura.py
    python3 -I tools/build_unicamp_cobertura.py --html-dir /tmp/unicamp-ementas/cache
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas"
ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = ROOT / "data" / "targets" / "unicamp"
CATALOG = ROOT / "data" / "catalog" / "unicamp_2026_disciplinas.json"
OUTPUT = ROOT / "data" / "ontology" / "unicamp_2026_regras.json"

# Páginas que cobrem os currículos EC/EE e as áreas de Física, Eng. Elétrica,
# Eng. de Computação e Matemática usadas no teste. São dados públicos do catálogo.
PAGES = [
    "be.html", "ce.html", "ea.html", "ee.html", "eg.html", "em.html",
    "et.html", "f_.html", "gt.html", "hg.html", "hz.html", "la.html",
    "ma.html", "mc.html", "me.html", "ms.html", "mx.html", "qg.html",
]

STOPWORDS = set("""
a as o os de da das do dos e em para por com sem um uma uns umas na nas no nos ao aos
the and of for in on to seu sua seus suas este esta estes estas esse essa esses essas
como entre sobre sob apos antes durante mais menos muito pouco tambem nao sim ou
ser sao foi foram seja sejam sendo ter tem tinham havia havera pode podem podera
partir atraves uso utilizacao utilizando utilizado utilizados analise
introducao conceitos conceito fundamentos fundamento basicos estudo estudos
teoria teorica aplicacao aplicacoes desenvolvimento projeto projetos sistemas sistema
metodos tecnicas processo processos modelo modelos principais
""".split())

SUFFIXES = sorted(
    ["mente", "coes", "cao", "ais", "eis", "is", "os", "as", "es", "s", "a", "o"],
    key=len,
    reverse=True,
)


def normalize_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if token]


def stem(token: str) -> str:
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def content_tokens(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in normalize_words(text):
        if len(token) < 4 or token.isdigit() or token in STOPWORDS:
            continue
        counts[stem(token)] += 1
    return counts


def name_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_words(text)
        if len(token) >= 3 and token not in STOPWORDS
    }


GENERIC_NAME_TOKENS = {
    "laboratorio", "laboratorios", "projeto", "projetos", "sistema", "sistemas",
    "introducao", "fundamento", "fundamentos", "basico", "basica", "aplicado",
    "aplicada", "teoria", "pratica", "geral", "experimental",
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
}


def is_lab(name: str) -> bool:
    tokens = name_tokens(name)
    return bool(tokens & {"laboratorio", "laboratorios", "experimental"})


ROMAN_SEQUENCE = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
    "a": "1", "b": "2", "c": "3",
}


def sequence(text: str) -> str | None:
    """Extrai o numeral de sequência final (Cálculo I, Física IV, ...)."""
    tokens = normalize_words(text)
    if not tokens:
        return None
    token = tokens[-1]
    if token in ROMAN_SEQUENCE:
        return ROMAN_SEQUENCE[token]
    if token.isdigit() and 1 <= int(token) <= 10:
        return str(int(token))
    return None


def name_similarity(target_name: str, source_name: str) -> float:
    target_sequence = sequence(target_name)
    source_sequence = sequence(source_name)
    if target_sequence and source_sequence and target_sequence != source_sequence:
        return 0
    if is_lab(target_name) != is_lab(source_name):
        return 0
    target = name_tokens(target_name)
    source = name_tokens(source_name)
    if not target or not source:
        return 0
    shared = target & source
    if not any(token not in GENERIC_NAME_TOKENS for token in shared):
        return 0
    containment = len(shared) / len(target)
    union = target | source
    jaccard = len(shared) / len(union)
    if containment >= 0.6 and jaccard >= 0.4:
        return 0.6 * containment + 0.4 * jaccard
    return 0


def parse_page(page_html: str) -> dict[str, dict]:
    courses: dict[str, dict] = {}
    for match in re.finditer(r'id="disc-([a-z0-9_]+)".*?(?=id="disc-|$)', page_html, re.S):
        key = match.group(1)
        code = key.upper().replace("_", " ")
        block = match.group(0)
        text = re.sub(r"<[^>]+>", " ", block)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        ementa_match = re.search(r"Ementa\s+(.*?)\s+Bibliografia", text)
        if not ementa_match:
            continue
        code_pattern = r"\s*".join(re.escape(part) for part in code.split())
        name_match = re.search(
            r"\b" + code_pattern + r"\s*-\s*(.*?)\s+"
            r"(?:Coordenadoria|Carga Horária|Total de Horas)",
            text,
            re.S,
        )
        name = re.sub(r"\s+", " ", name_match.group(1)).strip() if name_match else ""
        hours_match = re.search(r"Total de Horas/Aula Realizadas em Sala de Aula:\s*(\d+)", text)
        hours = int(hours_match.group(1)) if hours_match else None
        courses[code] = {
            "codigo": code,
            "nome": name or code,
            "ementa": ementa_match.group(1).strip(),
            "horas": hours,
        }
    return courses


def fetch_page(page: str, html_dir: Path | None) -> str | None:
    if html_dir is not None:
        path = html_dir / page
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
    request = urllib.request.Request(
        f"{BASE}/{page}",
        headers={"User-Agent": "equivale-ementa-collector/1.0"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:  # noqa: BLE001 - relatório de coleta
            if attempt == 2:
                print(f"aviso: falha ao baixar {page}: {error}")
            else:
                time.sleep(1 + attempt)
    return None


def load_catalog(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    documents: dict[str, dict] = {}
    for item in payload.get("disciplinas", []):
        code = str(item.get("codigo") or "")
        name = str(item.get("nome") or "")
        if not code or not name:
            continue
        documents[code] = {
            "codigo": code,
            "nome": name,
            "ementa": str(item.get("ementa") or ""),
            "horas": item.get("horas"),
            "fonte": str(item.get("fonte") or ""),
        }
    return documents


def load_documents(
    html_dir: Path | None,
    catalog_path: Path | None = None,
) -> dict[str, dict]:
    """Usa o catálogo coletado pelo crawler; as páginas antigas são fallback."""
    if catalog_path is None and html_dir is None and CATALOG.exists():
        catalog_path = CATALOG
    if catalog_path is not None:
        if not catalog_path.exists():
            raise SystemExit(f"Catálogo não encontrado: {catalog_path}")
        documents = load_catalog(catalog_path)
        if documents:
            print(f"{len(documents)} ementas carregadas de {catalog_path}", file=sys.stderr)
            return documents

    documents: dict[str, dict] = {}
    for page in PAGES:
        page_html = fetch_page(page, html_dir)
        if page_html is None:
            continue
        for code, course in parse_page(page_html).items():
            course["fonte"] = (
                f"{BASE}/{page}#disc-{code.lower().replace(' ', '_')}"
            )
            documents[code] = course
    return documents


def build_vectors(documents: dict[str, dict]) -> dict[str, dict[str, float]]:
    doc_tokens = {code: content_tokens(item["ementa"]) for code, item in documents.items()}
    df: Counter[str] = Counter()
    for tokens in doc_tokens.values():
        for token in tokens:
            df[token] += 1
    count = len(doc_tokens)
    idf = {
        token: math.log((count + 1) / (frequency + 1)) + 1
        for token, frequency in df.items()
    }
    vectors: dict[str, dict[str, float]] = {}
    for code, tokens in doc_tokens.items():
        vector = {
            token: (1 + math.log(frequency)) * idf[token]
            for token, frequency in tokens.items()
            if df[token] < count * 0.7
        }
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm > 0:
            vectors[code] = {token: value / norm for token, value in vector.items()}
    return vectors


def similarity(target: dict[str, float], source: dict[str, float]) -> tuple[float, float, float, set[str]]:
    shared = set(target) & set(source)
    target_weight = sum(target.values())
    source_weight = sum(source.values())
    shared_weight = sum(target[token] for token in shared)
    coverage = shared_weight / target_weight if target_weight else 0
    precision = shared_weight / source_weight if source_weight else 0
    cosine = sum(target[token] * source[token] for token in shared)
    return coverage, precision, cosine, shared


def round_hours(hours: float) -> int:
    return max(15, int(round(hours / 15) * 15))


def target_components() -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    components: list[dict] = []
    for path in sorted(TARGET_DIR.glob("*.json")):
        curriculum = json.loads(path.read_text(encoding="utf-8"))
        for group in curriculum["grupos"]:
            for discipline in group.get("disciplinas", []):
                code = discipline.get("codigo")
                if not code or not re.fullmatch(r"[A-Z]{1,2}\s?\d{3}", code):
                    continue
                key = (curriculum["curso"], code, discipline["nome"])
                if key in seen:
                    continue
                seen.add(key)
                components.append(
                    {
                        "curso": curriculum["curso"],
                        "codigo": code,
                        "nome": discipline["nome"],
                        "horas": int(discipline["horas"]),
                    }
                )
    return components


def pick_candidates(
    target: dict,
    documents: dict[str, dict],
    vectors: dict[str, dict[str, float]],
) -> list[dict]:
    target_vector = vectors.get(target["codigo"])
    if not target_vector:
        return []
    candidates = []
    for code, source in documents.items():
        if code == target["codigo"]:
            continue
        source_vector = vectors.get(code)
        if not source_vector:
            continue
        # Uma disciplina de laboratório não deve ser coberta por uma teórica
        # (e vice-versa); a ementa de laboratório é genérica e gera ruído.
        if is_lab(target["nome"]) != is_lab(source["nome"]):
            continue
        coverage, precision, cosine, shared = similarity(target_vector, source_vector)
        content_score = 0.55 * coverage + 0.25 * precision + 0.2 * cosine
        name_score = name_similarity(target["nome"], source["nome"])
        if name_score < 0.6 and content_score < 0.05:
            continue
        if name_score >= 0.6:
            max_hours = target["horas"]
            ignore = bool(source.get("horas") and source["horas"] < target["horas"])
            score = max(0.7, name_score)
            basis = "nome"
            confidence = "alta" if name_score >= 0.85 else "media" if name_score >= 0.75 else "baixa"
            label = source["nome"]
        else:
            # A cobertura é limitada pela carga da origem; se a origem tem
            # menos horas, o fluxo combina mais de uma origem (m-para-n).
            max_hours = min(target["horas"], source.get("horas") or target["horas"])
            ignore = False
            score = min(0.9, 0.62 + 0.7 * content_score)
            basis = "ementa"
            confidence = "alta" if content_score >= 0.35 else "media" if content_score >= 0.18 else "baixa"
            label = ", ".join(
                sorted(shared, key=lambda token: -target_vector.get(token, 0))[:8]
            )
        candidates.append(
            {
                "codigo": code,
                "nome": source["nome"],
                "horas_cobertura": max_hours,
                "score": round(score, 4),
                "confianca": confidence,
                "ignorar_carga_horaria": ignore,
                "rotulo": label,
                "fonte": source["fonte"],
                "_basis": basis,
                "_content": content_score,
                "_name": name_score,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], -item["_content"], -item["_name"], item["codigo"]))
    return candidates[:20]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html-dir", type=Path, default=None)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="catálogo JSON do crawler (default: data/catalog se existir)",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()

    documents = load_documents(args.html_dir, args.catalog)
    if not documents:
        raise SystemExit("Nenhuma ementa carregada.")
    vectors = build_vectors(documents)
    components = target_components()
    rules = []
    for target in components:
        target_doc = documents.get(target["codigo"])
        if not target_doc:
            continue
        candidates = pick_candidates(target, documents, vectors)
        if not candidates:
            continue
        origins = []
        for candidate in candidates:
            basis = candidate.pop("_basis")
            candidate.pop("_content")
            candidate.pop("_name")
            candidate["rotulo"] = f"{basis}: {candidate['rotulo']}"
            origins.append(candidate)
        slug = re.sub(r"[^a-z0-9]+", "-", target["curso"].lower()).strip("-")
        code_slug = re.sub(r"[^a-z0-9]+", "-", target["codigo"].lower()).strip("-")
        rules.append(
            {
                "id": f"auto-{slug}-{code_slug}",
                "tipo": "cobertura_tematica_automatica",
                "alvo": {
                    "instituicao": "UNICAMP",
                    "curso": target["curso"],
                    "codigo": target["codigo"],
                    "componente": target["nome"],
                },
                "origem_instituicao": "UNICAMP",
                "origens": origins,
                "fonte": target_doc["fonte"],
                "observacao": (
                    "Gerado por TF-IDF de ementas e similaridade de nomes; "
                    "não é equivalência oficial. Limiares: nome >= 0.6; "
                    "conteúdo >= 0.05."
                ),
            }
        )

    payload = {
        "versao": "2026-10-26",
        "gerado_por": "tools/build_unicamp_cobertura.py",
        "metodo": "TF-IDF de ementas + similaridade de nomes; sem LLM",
        "escopo": "UNICAMP 2026: componentes da EC/EE contra disciplinas do catálogo",
        "coletado_em": "2026-10-26",
        "observacao": (
            "Regras geradas automaticamente a partir de ementas públicas. "
            "As horas de cobertura e os scores são heurísticos e não substituem "
            "a decisão da instituição."
        ),
        "regras": rules,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(rules)} regras, {sum(len(rule['origens']) for rule in rules)} origens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
