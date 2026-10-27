import type { Transcript, TranscriptDiscipline } from './types'

const APPROVED = new Set(['aprovado', 'aprovado_proficiencia'])

export function isApproved(situacao: string): boolean {
  return APPROVED.has(situacao)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value !== 'string' || !value.trim()) return null
  const parsed = Number(value.replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeDiscipline(raw: unknown, index: number): TranscriptDiscipline {
  if (!isRecord(raw)) {
    throw new Error(`Disciplina ${index + 1}: esperado um objeto.`)
  }
  const nome = typeof raw.nome === 'string' ? raw.nome.trim() : ''
  if (!nome) {
    throw new Error(`Disciplina ${index + 1}: campo "nome" obrigatório.`)
  }

  return {
    nome,
    horas: toNumber(raw.horas),
    situacao: typeof raw.situacao === 'string' && raw.situacao.trim() ? raw.situacao.trim() : 'aprovado',
    codigo: typeof raw.codigo === 'string' ? raw.codigo : undefined,
    codigo_normalizado: typeof raw.codigo_normalizado === 'string' ? raw.codigo_normalizado : undefined,
    periodo: typeof raw.periodo === 'string' ? raw.periodo : null,
    media: toNumber(raw.media),
  }
}

export function parseTranscriptJson(text: string): Transcript {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('JSON inválido. Verifique o arquivo do parser.')
  }

  const rawDisciplines = Array.isArray(data)
    ? data
    : isRecord(data) && Array.isArray(data.disciplinas)
      ? data.disciplinas
      : null

  if (!rawDisciplines) {
    throw new Error('JSON sem o campo "disciplinas". Use a saída do parser local.')
  }
  if (rawDisciplines.length === 0) {
    throw new Error('O histórico não tem disciplinas.')
  }

  const course = isRecord(data) && isRecord(data.curso)
    ? Object.fromEntries(
        Object.entries(data.curso).filter((entry): entry is [string, string] => typeof entry[1] === 'string'),
      )
    : null

  return {
    instituicao: isRecord(data) && typeof data.instituicao === 'string' ? data.instituicao : 'Importado localmente',
    curso: course,
    disciplinas: rawDisciplines.map(normalizeDiscipline),
  }
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let field = ''
  let quoted = false

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          field += '"'
          index += 1
        } else {
          quoted = false
        }
      } else {
        field += char
      }
    } else if (char === '"') {
      quoted = true
    } else if (char === ',') {
      row.push(field)
      field = ''
    } else if (char === '\n') {
      row.push(field)
      rows.push(row)
      row = []
      field = ''
    } else if (char !== '\r') {
      field += char
    }
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field)
    rows.push(row)
  }

  return rows.filter((cells) => cells.some((cell) => cell.trim() !== ''))
}

function headerKey(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

export function parseTranscriptCsv(text: string): Transcript {
  const rows = parseCsvRows(text)
  if (rows.length < 2) {
    throw new Error('CSV vazio ou sem linhas de dados.')
  }

  const header = rows[0].map(headerKey)
  const column = (name: string): number => header.indexOf(name)
  const nameIndex = column('nome')
  const hoursIndex = column('horas')
  if (nameIndex < 0 || hoursIndex < 0) {
    throw new Error('CSV precisa de cabeçalho com as colunas "nome" e "horas".')
  }

  const codeIndex = column('codigo')
  const statusIndex = column('situacao')
  const periodIndex = column('periodo')
  const disciplines: TranscriptDiscipline[] = []

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const cells = rows[rowIndex]
    const nome = (cells[nameIndex] ?? '').trim()
    if (!nome) continue
    disciplines.push({
      nome,
      horas: toNumber(cells[hoursIndex]),
      situacao: statusIndex >= 0 && cells[statusIndex]?.trim() ? cells[statusIndex].trim() : 'aprovado',
      codigo: codeIndex >= 0 ? (cells[codeIndex] ?? '').trim() || undefined : undefined,
      periodo: periodIndex >= 0 ? (cells[periodIndex] ?? '').trim() || null : null,
    })
  }

  if (disciplines.length === 0) {
    throw new Error('Nenhuma disciplina válida encontrada no CSV.')
  }

  return {
    instituicao: 'Importado localmente',
    curso: null,
    disciplinas: disciplines,
  }
}

export async function parseTranscriptFile(file: File): Promise<Transcript> {
  const text = await file.text()
  const name = file.name.toLowerCase()
  if (name.endsWith('.json') || file.type.includes('json')) {
    return parseTranscriptJson(text)
  }
  if (name.endsWith('.csv') || file.type.includes('csv')) {
    return parseTranscriptCsv(text)
  }
  const trimmed = text.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    return parseTranscriptJson(text)
  }
  throw new Error('Formato não reconhecido. Importe um JSON do parser ou um CSV.')
}

export function approvedDisciplineCount(transcript: Transcript): number {
  return transcript.disciplinas.filter((discipline) => isApproved(discipline.situacao)).length
}

export function approvedHours(transcript: Transcript): number {
  return transcript.disciplinas
    .filter((discipline) => isApproved(discipline.situacao))
    .reduce((total, discipline) => total + (discipline.horas ?? 0), 0)
}
