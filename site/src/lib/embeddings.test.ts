import assert from 'node:assert/strict'
import test from 'node:test'
import {
  cosineSimilarity,
  decodeEmbeddingFile,
  embeddingRecord,
  embeddingVector,
} from './embeddings'
import { matchCurriculum } from './match'
import type {
  CourseVectorRecord,
  Curriculum,
  EmbeddingsFile,
  Transcript,
} from './types'

function encode(values: number[], scale = 127): string {
  const bytes = Buffer.alloc(values.length)
  values.forEach((value, index) => {
    bytes[index] = Math.round(value * scale) & 0xff
  })
  return bytes.toString('base64')
}

function record(
  instituicao: string,
  codigo: string | null,
  nome: string,
  values: number[],
): CourseVectorRecord {
  return {
    chave: `${instituicao}|${codigo ?? nome}`,
    instituicao,
    codigo,
    nome,
    nome_chave: nome.toLowerCase().replace(/[^a-z0-9]+/g, ''),
    horas: 60,
    origem: 'teste',
    tipo_texto: 'ementa',
    fonte: 'https://example.test',
    termos: values.filter((value) => value !== 0).length,
    vetor: encode(values),
  }
}

function file(documentos: CourseVectorRecord[], dimensao = 4): EmbeddingsFile {
  return {
    schema_version: 1,
    metodo: 'teste',
    dimensao,
    escala: 127,
    encoding: 'int8-base64',
    gerado_em: '2026-10-27T00:00:00+00:00',
    documentos,
  }
}

function curriculum(nome: string, horas: number, codigo: string | null): Curriculum {
  return {
    id: 'teste',
    instituicao: 'UNICAMP',
    curso: 'Curso de teste',
    grau: 'bacharelado',
    modalidade: 'presencial',
    duracao_meses: 60,
    carga_horaria_total: horas,
    fonte: 'https://example.test/curriculo',
    grupos: [
      {
        ordem: 1,
        nome: 'Núcleo',
        horas,
        disciplinas: [{ nome, horas, codigo, tipo: 'obrigatoria' }],
      },
    ],
    eletivas: {},
  }
}

function transcript(
  nome: string,
  horas: number,
  codigo: string,
  instituicao = 'USP',
): Transcript {
  return {
    instituicao,
    disciplinas: [
      {
        codigo,
        codigo_normalizado: codigo,
        nome,
        horas,
        situacao: 'aprovado',
      },
    ],
  }
}

test('decodifica vetores int8 e calcula cosseno', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'BE310', 'Ciências do Ambiente', [1, 0, 0, 0]),
      record('USP', 'PEA3100', 'Energia e Ambiente', [0.5, 0.5, 0, 0]),
    ]),
  )
  assert.ok(index)
  const left = embeddingRecord(index, 'UNICAMP', 'BE310', 'Ciências do Ambiente')
  const right = embeddingRecord(index, 'USP', 'PEA3100', 'Energia e Ambiente')
  assert.ok(left && right)
  const leftVector = embeddingVector(index, left)
  const rightVector = embeddingVector(index, right)
  assert.ok(leftVector && rightVector)
  assert.ok(Math.abs(cosineSimilarity(leftVector, rightVector) - Math.SQRT1_2) < 1e-3)
})

test('encontra vetor por código e por nome, com fallback de código único', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'BE310', 'Ciências do Ambiente', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  assert.equal(embeddingRecord(index, 'UNICAMP', 'BE310', 'Outro nome')?.codigo, 'BE310')
  assert.equal(embeddingRecord(index, 'UNICAMP', null, 'Ciências do Ambiente')?.codigo, 'BE310')
  assert.equal(embeddingRecord(index, 'OUTRA', 'BE310', 'Outro nome')?.codigo, 'BE310')
})

test('adiciona aresta por vetor quando não há match por nome', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'BE310', 'Ciências do Ambiente', [1, 0, 0, 0]),
      record('USP', 'PEA3100', 'Energia e Ambiente', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Ciências do Ambiente', 30, 'BE310'),
    transcript('Energia e Ambiente', 60, 'PEA3100'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 1)
  assert.equal(result.allocations[0].metodo, 'vetor')
  assert.equal(result.allocations[0].horas, 30)
})

test('vetor não cruza sequências diferentes', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'F 428', 'Física Geral IV', [1, 0, 0, 0]),
      record('USP', 'F315', 'Física III', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Física Geral IV', 60, 'F 428'),
    transcript('Física III', 60, 'F315'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 0)
})

test('vetor não mistura teoria e laboratório', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'EA616', 'Análise Linear de Sistemas', [1, 0, 0, 0]),
      record('USP', 'PTC3312', 'Laboratório de Análise Linear', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Análise Linear de Sistemas', 60, 'EA616'),
    transcript('Laboratório de Análise Linear', 30, 'PTC3312'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 0)
})

test('vetor com cosseno baixo não cria aresta', () => {
  const index = decodeEmbeddingFile(
    file([
      record('UNICAMP', 'BE310', 'Ciências do Ambiente', [1, 0, 0, 0]),
      record('USP', 'PRO3200', 'Estatística', [0, 1, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Ciências do Ambiente', 30, 'BE310'),
    transcript('Estatística', 60, 'PRO3200'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 0)
})

test('vetor não confunde redes de computadores com redes neurais', () => {
  const index = decodeEmbeddingFile(
    file([
      record('USP', 'PCS2025', 'Redes de Computadores', [1, 0, 0, 0]),
      record('UNICAMP', 'EG453', 'Redes Neurais', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Redes de Computadores', 60, 'PCS2025'),
    transcript('Redes Neurais', 60, 'EG453'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 0)
})

test('vetor não confunde cálculo IV com cálculo numérico', () => {
  const index = decodeEmbeddingFile(
    file([
      record('USP', 'MAT2456', 'Cálculo Diferencial e Integral IV', [1, 0, 0, 0]),
      record('UNICAMP', 'MS211', 'Cálculo Numérico', [1, 0, 0, 0]),
    ]),
  )
  assert.ok(index)
  const result = matchCurriculum(
    curriculum('Cálculo Diferencial e Integral IV', 60, 'MAT2456'),
    transcript('Cálculo Numérico', 60, 'MS211'),
    [],
    { embeddings: index },
  )
  assert.equal(result.allocations.length, 0)
})

test('índice inválido é ignorado sem quebrar o matching', () => {
  const index = decodeEmbeddingFile(
    file([record('UNICAMP', 'BE310', 'Ciências do Ambiente', [1, 0, 0, 0])], 0),
  )
  assert.equal(index, null)
  const result = matchCurriculum(
    curriculum('Ciências do Ambiente', 30, 'BE310'),
    transcript('Ciências do Ambiente', 30, 'BE310'),
    [],
    { embeddings: index },
  )
  assert.equal(result.summary.horasAbatidas, 30)
})
