#!/usr/bin/env python3
"""Pré-computa vetores densos de disciplinas para o matching local.

Não usa LLM. O método recomendado é LSA: TF-IDF das ementas/títulos seguido de
SVD truncado por um randomized SVD implementado neste script (com NumPy apenas
para álgebra linear). O resultado é quantizado em int8 e serializado em base64
para o site baixar um JSON compacto.

Há também um modo ``--metodo hash`` sem NumPy, que usa feature hashing; ele é
útil em ambientes mínimos, mas produz vetores lexicais menos estáveis.

Entrada:
  - data/catalog/unicamp_2026_disciplinas.json
  - data/catalog/usp_jupiterweb_disciplinas.json
  - grades-alvo (para incluir disciplinas sem ementa e cursos sem código)

Saída:
  - data/embeddings/cursos.json

Uso:
    python3 -I tools/build_course_embeddings.py
    python3 -I tools/build_course_embeddings.py --dimensao 192 --iteracoes 2
    python3 -I tools/build_course_embeddings.py --metodo hash

O script é determinístico para o mesmo corpus, dimensão, seed e método. O hash
do modo alternativo usa BLAKE2b, não a implementação aleatória de ``hash()`` do
Python.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "embeddings" / "cursos.json"
DEFAULT_CATALOG_DIR = ROOT / "data" / "catalog"
DEFAULT_TARGET_DIRS = [
    ROOT / "data" / "spike" / "curriculos",
    ROOT / "data" / "targets" / "unicamp",
    ROOT / "data" / "targets" / "usp",
]

STOPWORDS = set(
    """
    a as o os de da das do dos e em para por com sem um uma uns umas na nas no
    nos ao aos the and of for in on to seu sua seus suas este esta estes estas
    esse essa esses essas como entre sobre sob apos antes durante mais menos
    muito pouco tambem nao sim ou ser sao foi foram seja sejam sendo ter tem
    tinham havia havera pode podem podera partir atraves uso utilizacao
    utilizando utilizado utilizados disciplina disciplinas curso cursos aluno
    alunos professor professores
    """.split()
)
SUFFIXES = sorted(
    [
        "abilidade", "ibilidade", "amento", "imento", "idade", "idades",
        "mente", "encia", "ancia", "ismo", "ista", "coes", "cao", "ais",
        "eis", "is", "os", "as", "es", "s", "a", "o",
    ],
    key=len,
    reverse=True,
)


@dataclass
class Document:
    key: str
    instituicao: str
    codigo: str | None
    nome: str
    nome_chave: str
    horas: int | None
    ementa: str
    objetivos: str
    conteudo: str
    fonte: str
    origem: str

    @property
    def text_kind(self) -> str:
        return "ementa" if (self.ementa or self.objetivos or self.conteudo) else "titulo"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if token]


def stem(token: str) -> str:
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokens(text: str, *, keep_stopwords: bool = False) -> list[str]:
    result = []
    for token in normalize_words(text):
        if len(token) < 2 or token.isdigit():
            continue
        if not keep_stopwords and token in STOPWORDS:
            continue
        result.append(stem(token))
    return result


def code_key(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (value or "").upper())


def name_key(value: str) -> str:
    return "".join(normalize_words(value))


def make_key(instituicao: str, codigo: str | None, nome: str) -> str:
    institution = re.sub(r"\s+", "_", (instituicao or "").strip().upper())
    if codigo:
        return f"{institution}|{code_key(codigo)}"
    return f"{institution}|NOME|{name_key(nome) or 'SEM_NOME'}"


def load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_catalog_documents(catalog_dir: Path) -> list[Document]:
    documents: list[Document] = []
    for filename, institution in [
        ("unicamp_2026_disciplinas.json", "UNICAMP"),
        ("usp_jupiterweb_disciplinas.json", "USP"),
    ]:
        payload = load_json(catalog_dir / filename)
        if not payload:
            print(f"aviso: catálogo ausente: {catalog_dir / filename}", file=sys.stderr)
            continue
        for item in payload.get("disciplinas", []):
            code = str(item.get("codigo") or "")
            name = str(item.get("nome") or "")
            if not name:
                continue
            documents.append(
                Document(
                    key=make_key(institution, code, name),
                    instituicao=institution,
                    codigo=code or None,
                    nome=name,
                    nome_chave=name_key(name),
                    horas=int(item["horas"]) if item.get("horas") is not None else None,
                    ementa=str(item.get("ementa") or ""),
                    objetivos=str(item.get("objetivos") or ""),
                    conteudo=str(item.get("conteudo") or ""),
                    fonte=str(item.get("fonte") or ""),
                    origem="catalogo",
                )
            )
    return documents


def load_target_documents(target_dirs: list[Path], existing: set[str]) -> list[Document]:
    documents: list[Document] = []
    for target_dir in target_dirs:
        if not target_dir.exists():
            continue
        for path in sorted(target_dir.glob("*.json")):
            payload = load_json(path)
            if not payload or not isinstance(payload.get("grupos"), list):
                continue
            institution = str(payload.get("instituicao") or "")
            for group in payload.get("grupos", []):
                for item in group.get("disciplinas", []):
                    name = str(item.get("nome") or "")
                    code = str(item.get("codigo") or "") or None
                    if not name:
                        continue
                    key = make_key(institution, code, name)
                    if key in existing:
                        continue
                    existing.add(key)
                    documents.append(
                        Document(
                            key=key,
                            instituicao=institution,
                            codigo=code,
                            nome=name,
                            nome_chave=name_key(name),
                            horas=(
                                int(item["horas"])
                                if item.get("horas") is not None
                                else None
                            ),
                            ementa="",
                            objetivos="",
                            conteudo="",
                            fonte=str(payload.get("fonte") or ""),
                            origem="grade_alvo",
                        )
                    )
    return documents


def document_counts(document: Document) -> Counter[str]:
    counts: Counter[str] = Counter()
    content = " ".join(
        part
        for part in (document.ementa, document.objetivos, document.conteudo)
        if part
    )
    counts.update(tokens(content))
    title = tokens(document.nome)
    for token in title:
        counts[token] += 3.0
    for left, right in zip(title, title[1:]):
        counts[f"{left}_{right}"] += 2.0
    return counts


def build_idf(
    counts_list: list[Counter[str]],
) -> tuple[dict[str, float], Counter[str]]:
    df: Counter[str] = Counter()
    for counts in counts_list:
        df.update(counts.keys())
    total = len(counts_list)
    idf = {
        token: math.log((total + 1) / (frequency + 1)) + 1.0
        for token, frequency in df.items()
    }
    return idf, df


def weighted_counts(counts: Counter[str], idf: dict[str, float]) -> list[tuple[str, float]]:
    result = []
    for token, count in counts.items():
        weight = (1.0 + math.log(count)) * idf.get(token, 0.0)
        if weight > 0:
            result.append((token, weight))
    return result


def hash_term(term: str, dimension: int) -> tuple[int, float]:
    digest = hashlib.blake2b(term.encode("utf-8"), digest_size=16).digest()
    index = int.from_bytes(digest[:8], "little") % dimension
    sign = 1.0 if digest[8] & 1 else -1.0
    return index, sign


def hashing_vectors(
    counts_list: list[Counter[str]],
    idf: dict[str, float],
    dimension: int,
) -> list[list[float]]:
    vectors = []
    for counts in counts_list:
        vector = [0.0] * dimension
        for token, weight in weighted_counts(counts, idf):
            index, sign = hash_term(token, dimension)
            vector[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        vectors.append(vector)
    return vectors


def lsa_vectors(
    counts_list: list[Counter[str]],
    idf: dict[str, float],
    dimension: int,
    *,
    iterations: int,
    seed: int,
) -> list[list[float]]:
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - depende do ambiente
        raise SystemExit(
            "O método LSA requer NumPy. Instale com "
            "`python3 -m pip install numpy` ou rode com `--metodo hash`."
        ) from error

    vocabulary = {token: index for index, token in enumerate(sorted(idf))}
    vocabulary_size = len(vocabulary)
    document_count = len(counts_list)
    if vocabulary_size == 0 or document_count == 0:
        return []

    indptr = [0]
    indices: list[int] = []
    data: list[float] = []
    for counts in counts_list:
        entries = []
        for token, weight in weighted_counts(counts, idf):
            entries.append((vocabulary[token], weight))
        norm = math.sqrt(sum(weight * weight for _, weight in entries))
        if norm > 0:
            for index, weight in entries:
                indices.append(index)
                data.append(weight / norm)
        indptr.append(len(indices))

    indices_array = np.asarray(indices, dtype=np.int32)
    data_array = np.asarray(data, dtype=np.float32)
    indptr_array = np.asarray(indptr, dtype=np.int64)
    target_dimension = min(dimension, document_count, vocabulary_size)
    projection_dimension = min(
        vocabulary_size,
        document_count,
        max(target_dimension * 2, target_dimension + 32),
    )
    if projection_dimension <= 0:
        return []

    rng = np.random.default_rng(seed)
    projection = rng.standard_normal(
        (vocabulary_size, projection_dimension), dtype=np.float32
    )

    def multiply_x(matrix: np.ndarray) -> np.ndarray:
        output = np.empty((document_count, projection_dimension), dtype=np.float32)
        for row in range(document_count):
            start, end = indptr[row], indptr[row + 1]
            output[row] = data_array[start:end] @ matrix[indices_array[start:end]]
        return output

    def multiply_xt(matrix: np.ndarray) -> np.ndarray:
        output = np.zeros((vocabulary_size, projection_dimension), dtype=np.float32)
        for row in range(document_count):
            start, end = indptr[row], indptr[row + 1]
            output[indices_array[start:end]] += (
                data_array[start:end, None] * matrix[row]
            )
        return output

    sample = multiply_x(projection)
    for _ in range(max(0, iterations)):
        sample = multiply_x(multiply_xt(sample))

    basis, _ = np.linalg.qr(sample, mode="reduced")
    compressed = np.zeros((basis.shape[1], vocabulary_size), dtype=np.float32)
    for row in range(document_count):
        start, end = indptr[row], indptr[row + 1]
        compressed[:, indices_array[start:end]] += (
            basis[row][:, None] * data_array[start:end][None, :]
        )

    gram = compressed @ compressed.T
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1][:target_dimension]
    singular_values = np.sqrt(np.maximum(eigenvalues[order], 0.0))
    embedding = basis @ (eigenvectors[:, order] * singular_values[None, :])
    norms = np.linalg.norm(embedding, axis=1)
    norms[norms == 0] = 1.0
    embedding = embedding / norms[:, None]
    return embedding.tolist()


def quantize(vector: list[float], scale: int = 127) -> str:
    raw = bytes(max(-scale, min(scale, int(round(value * scale)))) & 0xFF for value in vector)
    return base64.b64encode(raw).decode("ascii")


def default_target_dirs() -> list[Path]:
    return [path for path in DEFAULT_TARGET_DIRS if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-dir", type=Path, default=DEFAULT_CATALOG_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dimensao", type=int, default=128)
    parser.add_argument(
        "--metodo",
        choices=["lsa", "hash"],
        default="lsa",
        help="LSA com SVD truncado (recomendado) ou feature hashing",
    )
    parser.add_argument("--iteracoes", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--target-dir",
        type=Path,
        action="append",
        default=None,
        help="diretório de grades-alvo (pode repetir; default: os três do repo)",
    )
    args = parser.parse_args()
    if args.dimensao < 32:
        raise SystemExit("A dimensão deve ser pelo menos 32.")

    catalog_documents = load_catalog_documents(args.catalog_dir)
    existing = {document.key for document in catalog_documents}
    target_dirs = args.target_dir or default_target_dirs()
    target_documents = load_target_documents(target_dirs, existing)
    documents = catalog_documents + target_documents
    if not documents:
        raise SystemExit("Nenhum documento encontrado para gerar embeddings.")

    # Chaves duplicadas de catálogos diferentes: mantém o documento com mais texto.
    by_key: dict[str, Document] = {}
    for document in documents:
        previous = by_key.get(document.key)
        if previous is None:
            by_key[document.key] = document
            continue
        previous_text = len(previous.ementa) + len(previous.objetivos) + len(previous.conteudo)
        current_text = len(document.ementa) + len(document.objetivos) + len(document.conteudo)
        if current_text > previous_text:
            by_key[document.key] = document
    documents = sorted(by_key.values(), key=lambda item: item.key)

    counts_list = [document_counts(document) for document in documents]
    idf, _ = build_idf(counts_list)
    if args.metodo == "lsa":
        vectors = lsa_vectors(
            counts_list,
            idf,
            args.dimensao,
            iterations=args.iteracoes,
            seed=args.seed,
        )
        actual_dimension = len(vectors[0]) if vectors else 0
        method_label = (
            "TF-IDF de ementas/títulos + SVD truncado "
            f"(randomized SVD, {args.iteracoes} iteração(ões), seed {args.seed})"
        )
    else:
        vectors = hashing_vectors(counts_list, idf, args.dimensao)
        actual_dimension = args.dimensao
        method_label = (
            "TF-IDF de ementas/títulos + feature hashing determinístico "
            "(BLAKE2b)"
        )

    output_documents = []
    for index, (document, vector, counts) in enumerate(
        zip(documents, vectors, counts_list), start=1
    ):
        output_documents.append(
            {
                "chave": document.key,
                "instituicao": document.instituicao,
                "codigo": document.codigo,
                "nome": document.nome,
                "nome_chave": document.nome_chave,
                "horas": document.horas,
                "origem": document.origem,
                "tipo_texto": document.text_kind,
                "fonte": document.fonte,
                "termos": len(counts),
                "vetor": quantize(vector),
            }
        )
        if index % 1000 == 0 or index == len(documents):
            print(
                f"{index}/{len(documents)} documentos vetorizados",
                file=sys.stderr,
            )

    payload = {
        "schema_version": 2,
        "metodo": method_label,
        "dimensao": actual_dimension,
        "escala": 127,
        "encoding": "int8-base64",
        "gerado_em": now_iso(),
        "corpus": {
            "documentos": len(documents),
            "com_ementa": sum(1 for document in documents if document.text_kind == "ementa"),
            "somente_titulo": sum(
                1 for document in documents if document.text_kind == "titulo"
            ),
            "vocabulario": len(idf),
            "catalogo": len(catalog_documents),
            "grades_alvo": len(target_documents),
        },
        "documentos": output_documents,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_name(f".{args.out.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.out)
    print(
        f"{args.out}: {len(documents)} documentos, dimensão {actual_dimension}, "
        f"{len(idf)} termos, método {args.metodo}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
