#!/usr/bin/env python3
"""Crawler persistente dos catálogos públicos de disciplinas da UNICAMP e USP.

O objetivo é coletar **uma vez** os dados publicados (código, nome, carga,
ementa e URL) e deixá-los em JSON versionável. O matching continua
determinístico e offline; este script não usa LLM, não lê históricos e não
infere equivalências.

Fontes:
  - UNICAMP: Catálogo dos Cursos de Graduação 2026 (DAC), páginas por letra.
  - USP: Jupiterweb, disciplinas por unidade e páginas obterDisciplina.

Uso:
    python3 -I tools/crawl_catalogos.py
    python3 -I tools/crawl_catalogos.py --refresh
    python3 -I tools/crawl_catalogos.py --offline
    python3 -I tools/crawl_catalogos.py --usp-scope all
    python3 -I tools/crawl_catalogos.py --usp-unit 3 --usp-unit 7

O cache HTTP fica fora do repositório, em ~/.cache/equivale/crawler por padrão.
As saídas ficam em data/catalog/ e são escritas de forma atômica.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "catalog"
DEFAULT_CACHE_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "equivale"
    / "crawler"
)
UNICAMP_INDEX = (
    "https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/disciplinas/"
)
USP_BASE = "https://uspdigital.usp.br/jupiterweb/"
USP_UNITS_URL = urllib.parse.urljoin(USP_BASE, "jupColegiadoLista?tipo=D")
USP_POLI_COD = "3"
USER_AGENT = "equivale-catalog-crawler/1.0 (+https://github.com/suzumi-nagata/equivale)"

CODE_RE = re.compile(r"^[A-Z0-9]{1,12}(?:\s[A-Z0-9]{1,6})?$")
USP_CODE_RE = re.compile(r"^[A-Z0-9]{3,12}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def atomic_write_json(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


def href_values(value: str) -> list[str]:
    """Aceita href com aspas ou sem aspas, como nas páginas antigas do Jupiterweb."""
    result = []
    pattern = re.compile(
        r'href\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s>]+))',
        flags=re.I,
    )
    for match in pattern.finditer(value):
        href = match.group(1) or match.group(2) or match.group(3)
        if href:
            result.append(html.unescape(href))
    return result


def clean_html(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.S | re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def safe_url(url: str) -> str:
    """Normaliza URLs descobertas sem quebrar query strings já codificadas."""
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%:@")
    query = urllib.parse.quote(parts.query, safe="=&%+;,:@/?")
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, path, query, parts.fragment)
    )


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" .;")
    if not value or value.lower() in {"nao ha", "não há", "nenhum", "-"}:
        return None
    return value


def section(start: str, text: str, ends: list[str]) -> str:
    """Extrai uma seção entre um marcador e o primeiro marcador final."""
    match = re.search(start, text, flags=re.I)
    if not match:
        return ""
    rest = text[match.end() :]
    positions = [
        end_match.start()
        for end in ends
        if (end_match := re.search(re.escape(end), rest, flags=re.I))
    ]
    end = min(positions) if positions else len(rest)
    return clean_html(rest[:end])


def first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.I)
    return int(match.group(1)) if match else None


@dataclass
class FetchOutcome:
    text: str | None
    from_cache: bool
    status: int | None = None


class DiskHttpCache:
    """Cache HTTP com manifest, validadores e fallback para resposta antiga."""

    def __init__(
        self,
        root: Path,
        *,
        max_age_days: float,
        timeout: float,
        delay: float,
        refresh: bool,
        offline: bool,
    ) -> None:
        self.root = root
        self.pages = root / "pages"
        self.manifest_path = root / "manifest.json"
        self.max_age_seconds = max(0.0, max_age_days * 86400)
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.refresh = refresh
        self.offline = offline
        self.manifest: dict[str, dict] = {}
        self.dirty = 0
        self.pages.mkdir(parents=True, exist_ok=True)
        if self.manifest_path.exists():
            try:
                loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.manifest = loaded
            except (OSError, json.JSONDecodeError):
                self.manifest = {}

    def _page_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.pages / digest[:2] / f"{digest}.html"

    def _entry(self, url: str) -> dict | None:
        entry = self.manifest.get(url)
        if not isinstance(entry, dict):
            return None
        return entry

    def _read(self, url: str, encoding: str) -> str | None:
        path = self._page_path(url)
        if not path.exists():
            return None
        try:
            return path.read_bytes().decode(encoding, errors="replace")
        except OSError:
            return None

    def _fresh(self, entry: dict, path: Path) -> bool:
        if not path.exists():
            return False
        fetched = entry.get("fetched_at")
        if not fetched:
            try:
                fetched_timestamp = path.stat().st_mtime
            except OSError:
                return False
        else:
            try:
                fetched_timestamp = datetime.fromisoformat(fetched).timestamp()
            except ValueError:
                fetched_timestamp = path.stat().st_mtime
        return (time.time() - fetched_timestamp) <= self.max_age_seconds

    def _remember(
        self,
        url: str,
        path: Path,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        status: int = 200,
    ) -> None:
        self.manifest[url] = {
            "path": str(path.relative_to(self.root)),
            "fetched_at": now_iso(),
            "etag": etag,
            "last_modified": last_modified,
            "status": status,
        }
        self.dirty += 1
        if self.dirty % 10 == 0:
            self.flush()

    def cache_path(self, url: str) -> Path:
        return self._page_path(url)

    def fetch(self, url: str, *, encoding: str = "utf-8") -> FetchOutcome:
        path = self._page_path(url)
        entry = self._entry(url)

        if entry and self._fresh(entry, path) and not self.refresh:
            cached = self._read(url, encoding)
            if cached is not None:
                return FetchOutcome(cached, True, entry.get("status"))

        # Recupera páginas gravadas antes de uma interrupção, mesmo que o
        # manifest não tenha sido atualizado.
        if entry is None and path.exists() and not self.refresh:
            age = time.time() - path.stat().st_mtime
            if age <= self.max_age_seconds:
                cached = self._read(url, encoding)
                if cached is not None:
                    return FetchOutcome(cached, True, None)

        if self.offline:
            cached = self._read(url, encoding)
            if cached is None:
                print(f"aviso: offline sem cache para {url}", file=sys.stderr)
                return FetchOutcome(None, False)
            return FetchOutcome(cached, True, entry.get("status") if entry else None)

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "identity",
        }
        if entry:
            if entry.get("etag"):
                headers["If-None-Match"] = str(entry["etag"])
            if entry.get("last_modified"):
                headers["If-Modified-Since"] = str(entry["last_modified"])

        last_error: Exception | None = None
        for attempt in range(3):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    charset = response.headers.get_content_charset() or encoding
                    content = raw.decode(charset, errors="replace")
                    atomic_write_bytes(path, raw)
                    self._remember(
                        url,
                        path,
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                        status=response.status,
                    )
                    if self.delay:
                        time.sleep(self.delay)
                    return FetchOutcome(content, False, response.status)
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code == 304:
                    cached = self._read(url, encoding)
                    if cached is not None:
                        self._remember(
                            url,
                            path,
                            etag=error.headers.get("ETag"),
                            last_modified=error.headers.get("Last-Modified"),
                            status=304,
                        )
                        return FetchOutcome(cached, True, 304)
                if error.code == 404:
                    self.manifest[url] = {
                        "path": str(path.relative_to(self.root)),
                        "fetched_at": now_iso(),
                        "status": 404,
                    }
                    self.dirty += 1
                    self.flush()
                    return FetchOutcome(None, False, 404)
                retry_after = error.headers.get("Retry-After")
                wait = 1.5 * (attempt + 1)
                if retry_after and retry_after.isdigit():
                    wait = max(wait, min(float(retry_after), 30.0))
                if attempt < 2:
                    time.sleep(wait)
                    continue
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(1.0 + attempt)
                    continue
            break

        cached = self._read(url, encoding)
        if cached is not None:
            print(
                f"aviso: usando cache antigo para {url} ({last_error})",
                file=sys.stderr,
            )
            return FetchOutcome(cached, True, entry.get("status") if entry else None)
        print(f"aviso: falha ao baixar {url}: {last_error}", file=sys.stderr)
        return FetchOutcome(None, False)

    def flush(self) -> None:
        atomic_write_json(self.manifest_path, self.manifest)
        self.dirty = 0


# ---------------------------------------------------------------------------
# UNICAMP


def unicamp_letter_urls(index_html: str) -> list[str]:
    links: set[str] = set()
    for href in href_values(index_html):
        if re.search(r"/disciplinas/[a-z0-9_]+\.html$", href, flags=re.I):
            if href.endswith("/index.html"):
                continue
            links.add(safe_url(urllib.parse.urljoin(UNICAMP_INDEX, href)))
    return sorted(links)


def parse_unicamp_page(page_html: str, page_url: str) -> list[dict]:
    disciplines: list[dict] = []
    for match in re.finditer(
        r'id="disc-([a-z0-9_]+)".*?(?=id="disc-|$)',
        page_html,
        flags=re.S,
    ):
        key = match.group(1)
        block = match.group(0)
        text = clean_html(block)
        code = key.upper().replace("_", " ")
        if not CODE_RE.fullmatch(code):
            continue
        code_pattern = r"\s*".join(re.escape(part) for part in code.split())
        name_match = re.search(
            r"\b"
            + code_pattern
            + r"\s*-\s*(.*?)\s+"
            r"(?:Coordenadoria|Carga Horária|Total de Horas|Período de Oferecimento)",
            text,
            flags=re.S | re.I,
        )
        if not name_match:
            continue
        name = clean_html(name_match.group(1))
        if not name or name == code:
            continue
        ementa = section("Ementa\\s+", text, ["Bibliografia", "Observação", "Observações"])
        horas = first_int(
            r"Total de Horas/Aula Realizadas em Sala de Aula:\s*(\d+)", text
        )
        if horas is None:
            horas = first_int(r"Total de Horas/Aula Semanais:\s*(\d+)", text)
        if horas is None:
            partes = [
                first_int(r"Total de Horas de Atividades Teóricas:\s*(\d+)", text),
                first_int(r"Total de Horas de Atividades Práticas:\s*(\d+)", text),
                first_int(r"Total de Horas de Laboratório:\s*(\d+)", text),
            ]
            if any(parte is not None for parte in partes):
                horas = sum(parte or 0 for parte in partes)
        prerequisites = section("Pré-requisitos\\s+", text, ["Ementa"])
        disciplines.append(
            {
                "codigo": code,
                "nome": name,
                "horas": horas,
                "horas_teoricas": first_int(
                    r"Total de Horas de Atividades Teóricas:\s*(\d+)", text
                ),
                "horas_praticas": first_int(
                    r"Total de Horas de Atividades Práticas:\s*(\d+)", text
                ),
                "horas_laboratorio": first_int(
                    r"Total de Horas de Laboratório:\s*(\d+)", text
                ),
                "creditos": first_int(r"Total de Créditos:\s*(\d+)", text),
                "periodo_oferta": clean_optional(
                    section("Período de Oferecimento\\s+", text, ["Avaliação"])
                ),
                "pre_requisitos": clean_optional(prerequisites),
                "ementa": ementa,
                "fonte": f"{page_url}#disc-{key}",
                "pagina": page_url,
            }
        )
    return disciplines


def crawl_unicamp(cache: DiskHttpCache) -> list[dict]:
    index = cache.fetch(UNICAMP_INDEX).text
    if index is None:
        raise SystemExit("Não foi possível obter o índice de disciplinas da UNICAMP.")
    letters = unicamp_letter_urls(index)
    if not letters:
        raise SystemExit("O índice da UNICAMP não contém páginas de letras reconhecíveis.")
    print(f"UNICAMP: {len(letters)} páginas de letras", file=sys.stderr)
    by_code: dict[str, dict] = {}
    for index, page_url in enumerate(letters, start=1):
        page = cache.fetch(page_url).text
        if page is None:
            continue
        for discipline in parse_unicamp_page(page, page_url):
            previous = by_code.get(discipline["codigo"])
            if previous is None or len(discipline.get("ementa") or "") > len(
                previous.get("ementa") or ""
            ):
                by_code[discipline["codigo"]] = discipline
        if index % 10 == 0 or index == len(letters):
            print(
                f"UNICAMP: {index}/{len(letters)} páginas, {len(by_code)} disciplinas",
                file=sys.stderr,
            )
    return sorted(by_code.values(), key=lambda item: item["codigo"])


# ---------------------------------------------------------------------------
# USP


def parse_usp_units(units_html: str) -> list[dict]:
    units: dict[str, dict] = {}
    pattern = re.compile(
        r"<a\b[^>]*?href\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))[^>]*>(.*?)</a>",
        flags=re.S | re.I,
    )
    for match in pattern.finditer(units_html):
        href = html.unescape(
            match.group(1) or match.group(2) or match.group(3) or ""
        )
        if "jupColegiadoMenu.jsp" not in href:
            continue
        query = urllib.parse.urlparse(href).query
        params = urllib.parse.parse_qs(query)
        codcg = (params.get("codcg") or [""])[0]
        if not codcg:
            continue
        units[codcg] = {
            "codcg": codcg,
            "nome": clean_html(match.group(4)),
            "url": safe_url(urllib.parse.urljoin(USP_BASE, href)),
        }
    return sorted(units.values(), key=lambda item: item["nome"])


def parse_usp_letter_urls(list_html: str) -> list[str]:
    links: set[str] = set()
    for href in href_values(list_html):
        if "jupDisciplinaLista" in href and "letra=" in href:
            links.add(safe_url(urllib.parse.urljoin(USP_BASE, href)))
    return sorted(links)


def parse_usp_codes(list_html: str) -> list[str]:
    codes = {
        code
        for code in re.findall(
            r"obterDisciplina\?sgldis=([A-Z0-9]+)", list_html, flags=re.I
        )
    }
    return sorted(code.upper() for code in codes if USP_CODE_RE.fullmatch(code.upper()))


def parse_usp_page(page_html: str, page_url: str) -> dict | None:
    text = clean_html(page_html)
    code_match = re.search(
        r"Disciplina:\s*([A-Z0-9]{3,12})\s*-\s*(.*?)\s+Cr.ditos Aula",
        text,
        flags=re.S | re.I,
    )
    if not code_match:
        return None
    code = code_match.group(1).upper()
    if not USP_CODE_RE.fullmatch(code):
        return None
    name = clean_html(code_match.group(2))
    if not name:
        return None
    ementa = section(
        r"\bEmenta\s+",
        text,
        [
            "Objetivos",
            "Conteúdo Programático",
            "Conteudo Programatico",
            "Bibliografia",
            "Observação",
            "Observacoes",
            "Instrumentos e Critérios",
        ],
    )
    objetivos = section(
        r"\bObjetivos\s+",
        text,
        [
            "Conteúdo Programático",
            "Conteudo Programatico",
            "Bibliografia",
            "Observação",
            "Observacoes",
            "Instrumentos e Critérios",
            "Norma de Recuperação",
        ],
    )
    conteudo = section(
        r"Conteúdo Programático\s+|Conteudo Programatico\s+",
        text,
        [
            "Bibliografia",
            "Observação",
            "Observacoes",
            "Instrumentos e Critérios",
            "Norma de Recuperação",
        ],
    )
    unidade_match = re.search(
        r"Sistema de Gestão Acadêmica da Pró-Reitoria de Graduação\s+(.*?)\s+Disciplina:",
        text,
        flags=re.S | re.I,
    )
    return {
        "codigo": code,
        "nome": name,
        "horas": first_int(r"Carga Hor.ria Total:\s*(\d+)\s*h", text),
        "creditos_aula": first_int(r"Cr.ditos Aula:\s*(\d+)", text),
        "creditos_trabalho": first_int(r"Cr.ditos Trabalho:\s*(\d+)", text),
        "tipo": clean_optional(section(r"\bTipo:\s*", text, ["Ativação", "Ativacao"])),
        "ativacao": clean_optional(
            section(r"\bAtivação:\s*|\bAtivacao:\s*", text, ["Desativação", "Desativacao", "Ementa"])
        ),
        "desativacao": clean_optional(
            section(r"\bDesativação:\s*|\bDesativacao:\s*", text, ["Ementa"])
        ),
        "unidade_contexto": clean_optional(unidade_match.group(1))
        if unidade_match
        else None,
        "ementa": ementa,
        "objetivos": objetivos or None,
        "conteudo": conteudo or None,
        "fonte": page_url,
    }


def usp_discipline_url(code: str) -> str:
    return safe_url(
        urllib.parse.urljoin(
            USP_BASE, f"obterDisciplina?sgldis={urllib.parse.quote(code)}"
        )
    )


def seed_usp_codes(target_dir: Path) -> list[str]:
    codes: set[str] = set()
    for path in sorted(target_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for group in payload.get("grupos", []):
            for discipline in group.get("disciplinas", []):
                code = str(discipline.get("codigo") or "").upper()
                if code and USP_CODE_RE.fullmatch(code):
                    codes.add(code)
    return sorted(codes)


def usp_codes_for_unit(cache: DiskHttpCache, unit: dict) -> list[str]:
    menu = cache.fetch(unit["url"]).text
    if menu is None:
        print(f"aviso: unidade USP sem menu: {unit['nome']}", file=sys.stderr)
        return []
    list_urls = set()
    for href in href_values(menu):
        if "jupDisciplinaLista" in href:
            list_urls.add(safe_url(urllib.parse.urljoin(USP_BASE, href)))
    base_url = safe_url(
        urllib.parse.urljoin(
            USP_BASE,
            f"jupDisciplinaLista?codcg={urllib.parse.quote(unit['codcg'])}&tipo=D",
        )
    )
    list_urls.add(base_url)

    codes: set[str] = set()
    letter_urls: set[str] = set()
    for list_url in sorted(list_urls):
        page = cache.fetch(list_url).text
        if page is None:
            continue
        codes.update(parse_usp_codes(page))
        letter_urls.update(parse_usp_letter_urls(page))
    for letter_url in sorted(letter_urls):
        page = cache.fetch(letter_url).text
        if page is None:
            continue
        codes.update(parse_usp_codes(page))
    return sorted(codes)


def crawl_usp(
    cache: DiskHttpCache,
    *,
    scope: str,
    extra_units: list[str],
    extra_codes: list[str],
    seed_targets: bool,
) -> list[dict]:
    units_html = cache.fetch(USP_UNITS_URL).text
    if units_html is None:
        raise SystemExit("Não foi possível obter a lista de unidades da USP.")
    all_units = parse_usp_units(units_html)
    by_codcg = {unit["codcg"]: unit for unit in all_units}

    selected: list[dict] = []
    if scope == "all":
        selected = all_units
    elif scope == "poli":
        selected = [by_codcg.get(USP_POLI_COD)] if USP_POLI_COD in by_codcg else []
    for codcg in extra_units:
        unit = by_codcg.get(str(codcg))
        if unit and unit not in selected:
            selected.append(unit)
        elif not unit:
            print(f"aviso: unidade USP codcg={codcg} não encontrada", file=sys.stderr)

    codes: set[str] = set()
    for unit in selected:
        unit_codes = usp_codes_for_unit(cache, unit)
        print(f"USP {unit['nome']}: {len(unit_codes)} disciplinas", file=sys.stderr)
        codes.update(unit_codes)
    if seed_targets:
        seeded = seed_usp_codes(ROOT / "data" / "targets" / "usp")
        print(f"USP: {len(seeded)} códigos citados nas grades-alvo", file=sys.stderr)
        codes.update(seeded)
    codes.update(code.strip().upper() for code in extra_codes if code.strip())
    print(f"USP: {len(codes)} páginas de disciplinas a coletar", file=sys.stderr)

    by_code: dict[str, dict] = {}
    for index, code in enumerate(sorted(codes), start=1):
        outcome = cache.fetch(usp_discipline_url(code), encoding="latin-1")
        if outcome.text is None:
            continue
        discipline = parse_usp_page(outcome.text, usp_discipline_url(code))
        if discipline:
            by_code[code] = discipline
        if index % 50 == 0 or index == len(codes):
            print(
                f"USP: {index}/{len(codes)} páginas, {len(by_code)} disciplinas",
                file=sys.stderr,
            )
    return sorted(by_code.values(), key=lambda item: item["codigo"])


# ---------------------------------------------------------------------------
# Saída


def catalog_payload(
    institution: str,
    catalog: str,
    source: str,
    scope: str,
    disciplines: list[dict],
) -> dict:
    with_ementa = [item for item in disciplines if item.get("ementa")]
    without = [item["codigo"] for item in disciplines if not item.get("ementa")]
    digest = hashlib.sha256(
        json.dumps(disciplines, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "instituicao": institution,
        "catalogo": catalog,
        "fonte": source,
        "escopo": scope,
        "coletado_em": now_iso(),
        "total": len(disciplines),
        "com_ementa": len(with_ementa),
        "sem_ementa": without,
        "hash_disciplinas": digest,
        "disciplinas": disciplines,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--cache-max-age-days",
        type=float,
        default=30.0,
        help="idade máxima do cache antes de revalidar (default: 30)",
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--delay", type=float, default=0.15, help="pausa entre requisições")
    parser.add_argument("--refresh", action="store_true", help="ignora a idade do cache")
    parser.add_argument("--offline", action="store_true", help="não faz requisições; usa só o cache")
    parser.add_argument(
        "--scope",
        choices=["all", "unicamp", "usp"],
        default="all",
        help="quais catálogos coletar (default: all)",
    )
    parser.add_argument(
        "--usp-scope",
        choices=["poli", "all", "none"],
        default="poli",
        help="unidades USP a varrer (default: poli; use all para todas)",
    )
    parser.add_argument(
        "--usp-unit",
        action="append",
        default=[],
        metavar="COD",
        help="codcg de unidade USP adicional (pode repetir)",
    )
    parser.add_argument(
        "--usp-code",
        action="append",
        default=[],
        metavar="CODE",
        help="código USP adicional para baixar diretamente (pode repetir)",
    )
    parser.add_argument(
        "--no-seed-usp-targets",
        action="store_true",
        help="não inclui códigos citados em data/targets/usp",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cache = DiskHttpCache(
        args.cache_dir,
        max_age_days=args.cache_max_age_days,
        timeout=args.timeout,
        delay=args.delay,
        refresh=args.refresh,
        offline=args.offline,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.scope in {"all", "unicamp"}:
            disciplines = crawl_unicamp(cache)
            payload = catalog_payload(
                "UNICAMP",
                "Catálogo dos Cursos de Graduação 2026",
                UNICAMP_INDEX,
                "todos os componentes das páginas de disciplinas do catálogo",
                disciplines,
            )
            output = args.out_dir / "unicamp_2026_disciplinas.json"
            atomic_write_json(output, payload)
            print(
                f"{output}: {payload['total']} disciplinas, "
                f"{payload['com_ementa']} com ementa"
            )

        if args.scope in {"all", "usp"} and args.usp_scope != "none":
            disciplines = crawl_usp(
                cache,
                scope=args.usp_scope,
                extra_units=args.usp_unit,
                extra_codes=args.usp_code,
                seed_targets=not args.no_seed_usp_targets,
            )
            scope_label = (
                "todas as unidades do Jupiterweb"
                if args.usp_scope == "all"
                else "Poli-USP + disciplinas citadas nas grades-alvo"
            )
            payload = catalog_payload(
                "USP",
                "Jupiterweb",
                USP_UNITS_URL,
                scope_label,
                disciplines,
            )
            output = args.out_dir / "usp_jupiterweb_disciplinas.json"
            atomic_write_json(output, payload)
            print(
                f"{output}: {payload['total']} disciplinas, "
                f"{payload['com_ementa']} com ementa"
            )
    finally:
        cache.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
