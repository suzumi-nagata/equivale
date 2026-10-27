import { normalize } from './normalize'
import type {
  CourseVectorRecord,
  EmbeddingIndex,
  EmbeddingsFile,
} from './types'

function compact(value: string): string {
  return normalize(value).replace(/\s+/g, '')
}

export function institutionKey(value: string): string {
  return compact(value)
}

export function codeKey(value: string | null | undefined): string {
  return compact(value ?? '').toUpperCase()
}

export function nameKey(value: string): string {
  return compact(value)
}

/**
 * Decodifica o índice estático gerado por tools/build_course_embeddings.py.
 * Os vetores são mantidos como base64 e só são decodificados sob demanda,
 * porque o corpus completo tem milhares de disciplinas.
 */
export function decodeEmbeddingFile(file: EmbeddingsFile): EmbeddingIndex | null {
  if (
    !file ||
    !Number.isFinite(file.dimensao) ||
    file.dimensao <= 0 ||
    !Number.isFinite(file.escala) ||
    file.escala <= 0 ||
    !Array.isArray(file.documentos)
  ) {
    return null
  }

  const byCode = new Map<string, CourseVectorRecord>()
  const byName = new Map<string, CourseVectorRecord>()
  const byAnyCode = new Map<string, CourseVectorRecord[]>()
  for (const record of file.documentos) {
    if (!record?.instituicao || !record?.nome || !record?.vetor) continue
    const institution = institutionKey(record.instituicao)
    if (record.codigo) {
      const code = codeKey(record.codigo)
      byCode.set(`${institution}|${code}`, record)
      const list = byAnyCode.get(code) ?? []
      list.push(record)
      byAnyCode.set(code, list)
    }
    const name = nameKey(record.nome)
    if (name) byName.set(`${institution}|${name}`, record)
  }

  return {
    dimensao: file.dimensao,
    escala: file.escala,
    byCode,
    byName,
    byAnyCode,
    vectors: new Map(),
  }
}

function decodeBase64(value: string): string | null {
  try {
    if (typeof atob === 'function') return atob(value)
  } catch {
    return null
  }
  return null
}

export function embeddingRecord(
  index: EmbeddingIndex | null | undefined,
  instituicao: string,
  codigo: string | null | undefined,
  nome: string,
): CourseVectorRecord | null {
  if (!index) return null
  const institution = institutionKey(instituicao)
  if (codigo) {
    const byCode = index.byCode.get(`${institution}|${codeKey(codigo)}`)
    if (byCode) return byCode
  }
  if (nome) {
    const byName = index.byName.get(`${institution}|${nameKey(nome)}`)
    if (byName) return byName
  }
  if (codigo) {
    const anywhere = index.byAnyCode.get(codeKey(codigo))
    if (anywhere && anywhere.length === 1) return anywhere[0]
  }
  return null
}

export function embeddingVector(
  index: EmbeddingIndex,
  record: CourseVectorRecord,
): Float32Array | null {
  const cached = index.vectors.get(record.chave)
  if (cached) return cached
  const binary = decodeBase64(record.vetor)
  if (binary === null) return null
  const vector = new Float32Array(binary.length)
  for (let offset = 0; offset < binary.length; offset += 1) {
    const byte = binary.charCodeAt(offset)
    const signed = byte > 127 ? byte - 256 : byte
    vector[offset] = signed / index.escala
  }
  if (vector.length !== index.dimensao) return null
  index.vectors.set(record.chave, vector)
  return vector
}

export function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) return 0
  let dot = 0
  let normA = 0
  let normB = 0
  for (let index = 0; index < a.length; index += 1) {
    const left = a[index]
    const right = b[index]
    dot += left * right
    normA += left * left
    normB += right * right
  }
  if (normA <= 0 || normB <= 0) return 0
  return dot / Math.sqrt(normA * normB)
}

export function similarityBetweenRecords(
  index: EmbeddingIndex,
  target: CourseVectorRecord,
  source: CourseVectorRecord,
): number {
  const targetVector = embeddingVector(index, target)
  const sourceVector = embeddingVector(index, source)
  if (!targetVector || !sourceVector) return 0
  return cosineSimilarity(targetVector, sourceVector)
}
