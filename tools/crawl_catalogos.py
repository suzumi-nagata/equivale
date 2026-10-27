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

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from extract_unicamp_2026 import CurriculumParser, parse_rows  # noqa: E402
from extract_usp_poli import parse_page as parse_usp_grade_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = ROOT / "data" / "catalog"
DEFAULT_CACHE_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "equivale"
    / "crawler"
)
UNICAMP_ROOT = "https://www.dac.unicamp.br/sistemas/catalogos/grad/catalogo2026/"
UNICAMP_INDEX = f"{UNICAMP_ROOT}disciplinas/"
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
# Cursos da UNICAMP


def unicamp_course_links(index_html: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for href in href_values(index_html):
        match = re.search(r"(?:^|/)cursos/([a-z0-9]+)/index\.html$", href, flags=re.I)
        if not match:
            continue
        code = match.group(1).upper()
        links[code] = safe_url(urllib.parse.urljoin(UNICAMP_ROOT, href))
    return dict(sorted(links.items()))


def parse_unicamp_course_index(page_html: str, code: str, page_url: str) -> dict:
    headings = [
        clean_html(value)
        for value in re.findall(r"<h1[^>]*>(.*?)</h1>", page_html, flags=re.S | re.I)
    ]
    name = next(
        (value for value in headings if re.match(r"^Curso\s+\S+\s*-\s*", value)),
        code,
    )
    name = re.sub(r"^Curso\s+\S+\s*-\s*", "", name).strip() or code
    unit_match = re.search(
        r'<a\b[^>]*href=["\'][^"\']*membros\.html["\'][^>]*>(.*?)</a>',
        page_html,
        flags=re.S | re.I,
    )
    unit = clean_html(unit_match.group(1)) if unit_match else None
    if unit:
        unit = re.sub(r"\s*-\s*Membros da Comiss[aã]o.*$", "", unit, flags=re.I).strip()
    turno_match = re.search(r"<h2[^>]*>\s*Turno:\s*(.*?)</h2>", page_html, flags=re.S | re.I)
    turno = clean_html(turno_match.group(1)) if turno_match else None
    habilitacoes = []
    seen = set()
    for h3 in re.findall(r"<h3[^>]*>(.*?)</h3>", page_html, flags=re.S | re.I):
        text = clean_html(h3)
        match = re.match(r"^([A-Z]{2})\s*-\s*(.+)$", text)
        if not match:
            continue
        hab_code, hab_name = match.groups()
        if hab_code in seen:
            continue
        seen.add(hab_code)
        habilitacoes.append({"codigo": hab_code, "nome": hab_name.strip()})
    return {
        "codigo": code,
        "nome": name,
        "unidade": unit,
        "turno": turno,
        "habilitacoes": habilitacoes,
        "fonte_index": page_url,
    }


def parse_unicamp_curriculum(page_html: str) -> list[dict]:
    parser = CurriculumParser()
    parser.feed(page_html)
    groups = []
    for table in parser.tables:
        h3 = table.get("h3") or ""
        if "Núcleo Comum" in h3:
            tipo = "obrigatoria_comum"
        elif "Obrigat" in h3:
            tipo = "obrigatoria_habilitacao"
        elif "Eletiv" in h3:
            tipo = "eletiva"
        else:
            tipo = "outra"
        disciplines, notes = parse_rows(table.get("rows", []), tipo)
        if not disciplines and not notes:
            continue
        groups.append(
            {
                "secao_h2": table.get("h2"),
                "secao_h3": h3 or None,
                "grupo": table.get("group"),
                "creditos_exigidos": table.get("credits"),
                "tipo": tipo,
                "disciplinas": disciplines,
                "observacoes": notes,
            }
        )
    return groups


def parse_unicamp_proposal(page_html: str) -> list[dict]:
    headings = list(
        re.finditer(r"<h([123])\b[^>]*>(.*?)</h\1>", page_html, flags=re.S | re.I)
    )
    habilitacoes: list[dict] = []
    current: dict | None = None
    for index, heading in enumerate(headings):
        level = int(heading.group(1))
        title = clean_html(heading.group(2))
        content_end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(page_html)
        )
        content = clean_html(page_html[heading.end() : content_end])
        variant_match = re.match(r"^([A-Z]{2})\s*-\s*(.+)$", title)
        if level == 2 and variant_match:
            code, name = variant_match.groups()
            current = {"codigo": code, "nome": name.strip(), "semestres": []}
            habilitacoes.append(current)
            continue
        if level == 2:
            current = None
            continue
        if level != 3 or current is None:
            continue
        semester_match = re.match(
            r"^(\d+)\s*[º°o]\s*Semestre\s*-\s*(\d+)\s*cr[eé]ditos",
            title,
            flags=re.I,
        )
        if not semester_match:
            continue
        items = [
            {"codigo": code, "creditos": int(credits), "tipo": "disciplina"}
            for code, credits in re.findall(
                r"\b((?:[A-Z]{2,4}\d{3,4})|(?:EX|MX|IX)---)\s*\((\d+)\)",
                content,
            )
        ]
        elective_match = re.search(r"(\d+)\s*cr[eé]ditos?\s+eletivos?", content, re.I)
        if elective_match:
            items.append(
                {
                    "codigo": "ELETIVA",
                    "creditos": int(elective_match.group(1)),
                    "tipo": "eletiva",
                }
            )
        current["semestres"].append(
            {
                "numero": int(semester_match.group(1)),
                "creditos": int(semester_match.group(2)),
                "itens": items,
                "texto": content,
            }
        )
    return habilitacoes


def crawl_unicamp_courses(cache: DiskHttpCache) -> list[dict]:
    index = cache.fetch(UNICAMP_ROOT).text
    if index is None:
        raise SystemExit("Não foi possível obter o índice de cursos da UNICAMP.")
    links = unicamp_course_links(index)
    if not links:
        raise SystemExit("O índice da UNICAMP não contém cursos reconhecíveis.")
    print(f"UNICAMP: {len(links)} cursos", file=sys.stderr)
    courses = []
    for index_number, (code, index_url) in enumerate(links.items(), start=1):
        base_url = index_url.rsplit("/", 1)[0] + "/"
        curriculum_url = safe_url(urllib.parse.urljoin(base_url, "curriculo.html"))
        proposal_url = safe_url(urllib.parse.urljoin(base_url, "sugestao.html"))
        index_html = cache.fetch(index_url).text
        curriculum_html = cache.fetch(curriculum_url).text
        proposal_html = cache.fetch(proposal_url).text
        metadata = (
            parse_unicamp_course_index(index_html, code, index_url)
            if index_html
            else {"codigo": code, "nome": code}
        )
        metadata["fonte_curriculo"] = curriculum_url
        metadata["fonte_sugestao"] = proposal_url
        metadata["curriculo"] = parse_unicamp_curriculum(curriculum_html) if curriculum_html else []
        metadata["proposta"] = parse_unicamp_proposal(proposal_html) if proposal_html else []
        metadata["grade_disponivel"] = bool(metadata["curriculo"])
        courses.append(metadata)
        if index_number % 10 == 0 or index_number == len(links):
            print(
                f"UNICAMP cursos: {index_number}/{len(links)}",
                file=sys.stderr,
            )
    return courses


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
# Cursos da USP


def parse_usp_course_rows(list_html: str, codcg: str, unit_name: str) -> list[dict]:
    rows: list[dict] = []
    for row_html in re.findall(r"<tr\b.*?</tr>", list_html, flags=re.S | re.I):
        hrefs = [
            href
            for href in href_values(row_html)
            if "listarGradeCurricular" in href
        ]
        if not hrefs:
            continue
        href = hrefs[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        codcur = (query.get("codcur") or [""])[0]
        codhab = (query.get("codhab") or [""])[0]
        tipo = (query.get("tipo") or ["N"])[0]
        if not codcur:
            continue
        cells = [
            clean_html(cell)
            for cell in re.findall(r"<t[dh]\b.*?</t[dh]>", row_html, flags=re.S | re.I)
        ]
        name = cells[1] if len(cells) > 1 else ""
        period = cells[2] if len(cells) > 2 else None
        if not name or re.fullmatch(r"[\d\s]+", name):
            continue
        rows.append(
            {
                "codcg": codcg,
                "codcur": codcur,
                "codhab": codhab,
                "tipo": tipo,
                "curso": name.strip(),
                "periodo": clean_optional(period),
                "unidade": unit_name,
                "url": safe_url(urllib.parse.urljoin(USP_BASE, href)),
            }
        )
    # Uma linha por combinação curso/habilitação.
    unique: dict[tuple[str, str], dict] = {}
    for row in rows:
        unique[(row["codcur"], row["codhab"])] = row
    return sorted(unique.values(), key=lambda row: (row["codcur"], row["codhab"]))


def parse_usp_course_metadata(page_html: str, row: dict) -> dict:
    text = clean_html(page_html)
    course_names = re.findall(
        r"Curso:\s*(.*?)\s+(?=Curso:|Informa(?:ç|c)[oõ]es B[aá]sicas|Data de In[íi]cio)",
        text,
        flags=re.I,
    )
    duration_ideal = re.search(r"Dura(?:ç|c)[aã]o Ideal\s*(\d+)\s*semestres", text, re.I)
    duration_min = re.search(r"M[íi]nima\s*(\d+)\s*semestres", text, re.I)
    duration_max = re.search(r"M[aá]xima\s*(\d+)\s*semestres", text, re.I)
    start = re.search(r"Data de In[íi]cio:\s*([0-9/]+)", text, re.I)
    unit = re.search(r"Grade Curricular.*?Preparar para impressão\s+(.*?)\s+Curso:", text, re.I)
    grade = parse_usp_grade_rows(page_html)
    return {
        **row,
        "unidade": clean_optional(unit.group(1)) if unit else row.get("unidade"),
        "curso_pagina": course_names,
        "data_inicio": start.group(1) if start else None,
        "duracao_ideal_semestres": int(duration_ideal.group(1)) if duration_ideal else None,
        "duracao_minima_semestres": int(duration_min.group(1)) if duration_min else None,
        "duracao_maxima_semestres": int(duration_max.group(1)) if duration_max else None,
        "fonte": row["url"],
        "grade_disponivel": bool(grade),
        "carga_horaria_total": sum(int(item["horas"] or 0) for item in grade),
        "grade": grade,
    }


def crawl_usp_courses(
    cache: DiskHttpCache,
    *,
    scope: str,
    extra_units: list[str],
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

    courses: dict[tuple[str, str], dict] = {}
    for unit in selected:
        list_url = safe_url(
            urllib.parse.urljoin(
                USP_BASE,
                f"jupCursoLista?codcg={urllib.parse.quote(unit['codcg'])}&tipo=N",
            )
        )
        list_html = cache.fetch(list_url, encoding="latin-1").text
        if list_html is None:
            print(f"aviso: unidade USP sem lista de cursos: {unit['nome']}", file=sys.stderr)
            continue
        rows = parse_usp_course_rows(list_html, unit["codcg"], unit["nome"])
        print(f"USP {unit['nome']}: {len(rows)} cursos/habilitações", file=sys.stderr)
        for row in rows:
            page = cache.fetch(row["url"], encoding="latin-1").text
            if page is None:
                continue
            courses[(row["codcur"], row["codhab"])] = parse_usp_course_metadata(page, row)
    return sorted(
        courses.values(),
        key=lambda row: (row.get("codcur", ""), row.get("codhab", "")),
    )


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


def course_payload(
    institution: str,
    catalog: str,
    source: str,
    scope: str,
    courses: list[dict],
) -> dict:
    with_grade = [course for course in courses if course.get("grade_disponivel")]
    digest = hashlib.sha256(
        json.dumps(courses, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "instituicao": institution,
        "catalogo": catalog,
        "fonte": source,
        "escopo": scope,
        "coletado_em": now_iso(),
        "total": len(courses),
        "com_grade": len(with_grade),
        "hash_cursos": digest,
        "cursos": courses,
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
    parser.add_argument(
        "--no-cursos",
        action="store_true",
        help="não coleta cursos/currículos",
    )
    parser.add_argument(
        "--no-disciplinas",
        action="store_true",
        help="não coleta o catálogo de disciplinas",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.no_cursos and args.no_disciplinas:
        raise SystemExit("Nada a coletar: --no-cursos e --no-disciplinas juntos.")
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
            if not args.no_cursos:
                courses = crawl_unicamp_courses(cache)
                payload = course_payload(
                    "UNICAMP",
                    "Catálogo dos Cursos de Graduação 2026",
                    UNICAMP_ROOT,
                    "todos os cursos, currículos plenos e propostas do catálogo",
                    courses,
                )
                output = args.out_dir / "unicamp_2026_cursos.json"
                atomic_write_json(output, payload)
                print(
                    f"{output}: {payload['total']} cursos, "
                    f"{payload['com_grade']} com currículo"
                )

            if not args.no_disciplinas:
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
            scope_label = (
                "todas as unidades do Jupiterweb"
                if args.usp_scope == "all"
                else "Poli-USP + disciplinas citadas nas grades-alvo"
            )
            if not args.no_cursos:
                courses = crawl_usp_courses(
                    cache,
                    scope=args.usp_scope,
                    extra_units=args.usp_unit,
                )
                payload = course_payload(
                    "USP",
                    "Jupiterweb",
                    USP_UNITS_URL,
                    scope_label,
                    courses,
                )
                output = args.out_dir / "usp_jupiterweb_cursos.json"
                atomic_write_json(output, payload)
                print(
                    f"{output}: {payload['total']} cursos/habilitações, "
                    f"{payload['com_grade']} com grade"
                )

            if not args.no_disciplinas:
                disciplines = crawl_usp(
                    cache,
                    scope=args.usp_scope,
                    extra_units=args.usp_unit,
                    extra_codes=args.usp_code,
                    seed_targets=not args.no_seed_usp_targets,
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
