import { BROAD_CONCEPTS, concepts, normalize, pairScore } from './normalize'
import type {
  Allocation,
  Confidence,
  Curriculum,
  MatchResult,
  MatchSummary,
  Slot,
  SlotResult,
  SourceDiscipline,
  Transcript,
} from './types'

const APPROVED = new Set(['aprovado', 'aprovado_proficiencia'])
const NON_WAIVABLE_TYPES = new Set(['extensao', 'projeto', 'complementar', 'estagio', 'tcc'])
const NON_WAIVABLE_NAME_PATTERNS = [
  /\batividades? complementares?\b/,
  /\batividades? extensionistas?\b/,
  /\bextensao\b/,
  /\bestagio\b/,
  /\btrabalho de (fim|conclusao) de curso\b/,
  /\btcc\b/,
  /\bprojeto interdisciplinar\b/,
]
const SOURCE_EXCLUDE_NAME_PATTERNS = [
  /\bestagio\b/,
  /\btrabalho de (fim|conclusao) de curso\b/,
  /\btcc\b/,
  /\batividades? complementares?\b/,
  /\bextensao\b/,
]

const MIN_PARTIAL_HOURS = 20

interface Edge {
  source: SourceDiscipline
  slot: Slot
  option: string
  score: number
  confianca: Confidence
  conceitos: string[]
  tokens: string[]
  rank: number
}

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0)
}

function matchesAny(value: string, patterns: RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(value))
}

export function buildSlots(curriculum: Curriculum): { slots: Slot[]; naoAbativeis: Slot[] } {
  const slots: Slot[] = []
  const naoAbativeis: Slot[] = []
  let index = 0

  for (const group of curriculum.grupos) {
    for (const discipline of group.disciplinas ?? []) {
      const horas = Number(discipline.horas) || 0
      if (horas <= 0) continue
      const tipo = discipline.tipo ?? 'obrigatoria'
      const normalized = normalize(discipline.nome)
      const blocked = NON_WAIVABLE_TYPES.has(tipo) || matchesAny(normalized, NON_WAIVABLE_NAME_PATTERNS)
      const slot: Slot = {
        id: `slot-${index++}`,
        grupoOrdem: group.ordem,
        grupoNome: group.nome,
        nome: discipline.nome,
        horas,
        opcoes: [discipline.nome],
        tipo,
        kind: 'fixa',
        abativel: !blocked,
      }
      ;(slot.abativel ? slots : naoAbativeis).push(slot)
    }

    for (const component of group.componentes ?? []) {
      const horas = Number(component.horas) || 0
      if (horas <= 0) continue
      const ref = component.opcoes_ref
      const options = ref && curriculum.eletivas?.[ref]?.length
        ? curriculum.eletivas[ref]
        : [component.nome]
      slots.push({
        id: `slot-${index++}`,
        grupoOrdem: group.ordem,
        grupoNome: group.nome,
        nome: component.nome,
        horas,
        opcoes: options,
        tipo: component.tipo ?? 'eletiva',
        kind: 'eletiva',
        abativel: true,
      })
    }
  }

  return { slots, naoAbativeis }
}

export function loadSources(transcript: Transcript): SourceDiscipline[] {
  const byCode = new Map<string, SourceDiscipline>()

  for (const discipline of transcript.disciplinas) {
    if (!APPROVED.has(discipline.situacao)) continue
    const horas = Number(discipline.horas) || 0
    if (horas <= 0) continue
    const normalized = normalize(discipline.nome)
    if (matchesAny(normalized, SOURCE_EXCLUDE_NAME_PATTERNS)) continue

    const code = discipline.codigo_normalizado || discipline.codigo || discipline.nome
    const source: SourceDiscipline = {
      id: code,
      codigo: discipline.codigo || code,
      nome: discipline.nome,
      horas,
      periodo: discipline.periodo ?? null,
      situacao: discipline.situacao,
    }
    const previous = byCode.get(code)
    if (!previous || (source.periodo ?? '') >= (previous.periodo ?? '')) {
      byCode.set(code, source)
    }
  }

  return [...byCode.values()]
}

function bestEdgeForSlot(source: SourceDiscipline, slot: Slot): Edge | null {
  let best: Edge | null = null

  for (const option of slot.opcoes) {
    const pair = pairScore(option, slot.horas, source.nome, source.horas)
    if (pair.score <= 0) continue
    const optionConcepts = concepts(option)
    const specific = [...optionConcepts].some((concept) => !BROAD_CONCEPTS.has(concept))
    const rank =
      pair.score *
      (slot.kind === 'fixa' ? 1.02 : 1) *
      (specific ? 1.02 : 1) *
      (1 + Math.min(0.02, pair.tokens.length * 0.005))
    if (!best || rank > best.rank) {
      best = {
        source,
        slot,
        option,
        score: pair.score,
        confianca: pair.confianca,
        conceitos: pair.conceitos,
        tokens: pair.tokens,
        rank,
      }
    }
  }

  return best
}

export function matchCurriculum(curriculum: Curriculum, transcript: Transcript): MatchResult {
  const { slots, naoAbativeis } = buildSlots(curriculum)
  const sources = loadSources(transcript)
  const edges: Edge[] = []

  for (const source of sources) {
    for (const slot of slots) {
      const edge = bestEdgeForSlot(source, slot)
      if (edge) edges.push(edge)
    }
  }

  edges.sort((a, b) => {
    if (b.rank !== a.rank) return b.rank - a.rank
    if (b.score !== a.score) return b.score - a.score
    return Math.min(b.source.horas, b.slot.horas) - Math.min(a.source.horas, a.slot.horas)
  })

  const sourceRemaining = new Map(sources.map((source) => [source.id, source.horas]))
  const slotRemaining = new Map(slots.map((slot) => [slot.id, slot.horas]))
  const allocations: Allocation[] = []

  for (const edge of edges) {
    const sourceLeft = sourceRemaining.get(edge.source.id) ?? 0
    const slotLeft = slotRemaining.get(edge.slot.id) ?? 0
    const amount = Math.min(sourceLeft, slotLeft)
    // Slots de 15h podem ser cobertos integralmente; para slots maiores,
    // evita frações pequenas que não ajudam a fechar o componente.
    const minimum = Math.min(MIN_PARTIAL_HOURS, edge.slot.horas)
    if (amount < minimum) continue

    sourceRemaining.set(edge.source.id, sourceLeft - amount)
    slotRemaining.set(edge.slot.id, slotLeft - amount)
    allocations.push({
      sourceId: edge.source.id,
      sourceCodigo: edge.source.codigo,
      sourceNome: edge.source.nome,
      sourcePeriodo: edge.source.periodo,
      slotId: edge.slot.id,
      slotNome: edge.slot.nome,
      grupoNome: edge.slot.grupoNome,
      opcao: edge.option,
      score: edge.score,
      confianca: edge.confianca,
      horas: amount,
      conceitos: edge.conceitos,
      tokens: edge.tokens,
    })
  }

  allocations.sort(
    (a, b) =>
      a.grupoNome.localeCompare(b.grupoNome, 'pt-BR') ||
      a.slotNome.localeCompare(b.slotNome, 'pt-BR') ||
      b.score - a.score,
  )

  const slotResults: SlotResult[] = slots
    .map((slot) => {
      const remaining = slotRemaining.get(slot.id) ?? slot.horas
      const alocado = slot.horas - remaining
      const allocationsForSlot = allocations
        .filter((allocation) => allocation.slotId === slot.id)
        .sort((a, b) => b.score - a.score)
      const status: SlotResult['status'] =
        remaining === 0 ? 'coberto' : alocado > 0 ? 'parcial' : 'aberto'
      return {
        slot,
        alocado,
        restante: remaining,
        status,
        allocations: allocationsForSlot,
      }
    })
    .sort(
      (a, b) =>
        a.slot.grupoOrdem - b.slot.grupoOrdem ||
        a.slot.nome.localeCompare(b.slot.nome, 'pt-BR'),
    )

  const naoAbativeisOrdenados = [...naoAbativeis].sort(
    (a, b) => a.grupoOrdem - b.grupoOrdem || a.nome.localeCompare(b.nome, 'pt-BR'),
  )

  const horasAbativeis = sum(slots.map((slot) => slot.horas))
  const horasNaoAbativeis = sum(naoAbativeis.map((slot) => slot.horas))
  const horasTotal = horasAbativeis + horasNaoAbativeis
  const horasAbatidas = sum(allocations.map((allocation) => allocation.horas))
  const semestresTotais = Math.max(1, Math.round(curriculum.duracao_meses / 6))
  const horasPorSemestre = horasTotal / semestresTotais
  const horasRestantesTotais = horasTotal - horasAbatidas
  const confiancaMedia = horasAbatidas
    ? sum(allocations.map((allocation) => allocation.score * allocation.horas)) / horasAbatidas
    : 0

  const summary: MatchSummary = {
    horasTotal,
    horasAbativeis,
    horasNaoAbativeis,
    horasAbatidas,
    coberturaAbativel: horasAbativeis ? horasAbatidas / horasAbativeis : 0,
    coberturaTotal: horasTotal ? horasAbatidas / horasTotal : 0,
    slotsAbativeis: slots.length,
    slotsCobertos: slotResults.filter((slot) => slot.status === 'coberto').length,
    slotsParciais: slotResults.filter((slot) => slot.status === 'parcial').length,
    slotsAbertos: slotResults.filter((slot) => slot.status === 'aberto').length,
    horasRestantesAbativeis: horasAbativeis - horasAbatidas,
    horasRestantesTotais,
    semestresTotais,
    horasPorSemestre,
    semestresRestantes: horasRestantesTotais > 0 ? Math.ceil(horasRestantesTotais / horasPorSemestre) : 0,
    confiancaMedia,
  }

  const avisos = [
    'Estimativa por nome + carga horária; não há ementa neste protótipo.',
    'Heurística m-para-n gulosa: uma origem pode cobrir vários alvos e um alvo pode combinar várias origens. O modelo final é fluxo de custo mínimo.',
    'Estágio, TCC, extensão, atividades complementares e projetos foram separados como não abatíveis.',
    'A estimativa de semestres ignora pré-requisitos, oferta, limite de aproveitamento e optativa livre.',
    'Não é uma decisão oficial de equivalência; a IES de destino decide.',
  ]

  if (Math.abs(horasTotal - curriculum.carga_horaria_total) > 0) {
    avisos.push(
      `A soma dos grupos (${horasTotal}h) difere da carga declarada (${curriculum.carga_horaria_total}h).`,
    )
  }

  return {
    summary,
    slots: slotResults,
    allocations,
    naoAbativeis: naoAbativeisOrdenados,
    fontes: sources,
    avisos,
  }
}
