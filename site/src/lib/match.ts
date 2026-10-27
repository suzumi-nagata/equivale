import {
  BROAD_CONCEPTS,
  concepts,
  isLab,
  normalize,
  pairScore,
  sequence,
  sharedSpecificNameToken,
} from './normalize'
import type {
  Allocation,
  Confidence,
  Curriculum,
  EquivalenceRule,
  MatchOptions,
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
  /\bprojeto final de (graduacao|curso)\b/,
  /\btcc\b/,
  /\bprojeto interdisciplinar\b/,
]
const SOURCE_EXCLUDE_NAME_PATTERNS = [
  /\bestagio\b/,
  /\btrabalho de (fim|conclusao) de curso\b/,
  /\bprojeto final de (graduacao|curso)\b/,
  /\btcc\b/,
  /\batividades? complementares?\b/,
  /\bextensao\b/,
]

const MIN_PARTIAL_HOURS = 20
const FREE_ELECTIVE_SCORE = 0.6

interface Edge {
  source: SourceDiscipline
  slot: Slot
  option: string
  score: number
  confianca: Confidence
  conceitos: string[]
  tokens: string[]
  rank: number
  maxHours?: number
  ignoreSourceHours?: boolean
  priority?: number
  ruleId?: string
}

interface MatchedEdge {
  edge: Edge
  hours: number
}

interface FlowEdge {
  to: number
  rev: number
  cap: number
  originalCap: number
  cost: number
  meta?: Edge
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
        codigo: discipline.codigo ?? null,
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
        livre: Boolean(component.livre),
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

function bestEdgeForSlot(
  source: SourceDiscipline,
  slot: Slot,
  ignoreWorkload = false,
): Edge | null {
  if (slot.livre) {
    return {
      source,
      slot,
      option: 'Eletiva livre',
      score: FREE_ELECTIVE_SCORE,
      confianca: 'baixa',
      conceitos: [],
      tokens: [],
      rank: FREE_ELECTIVE_SCORE,
    }
  }

  let best: Edge | null = null

  for (const option of slot.opcoes) {
    const scoreHours = ignoreWorkload ? source.horas : slot.horas
    const pair = pairScore(option, scoreHours, source.nome, source.horas)
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

function codeKey(value: string | null | undefined): string {
  return normalize(value ?? '').replace(/\s+/g, '')
}

function ruleMatchesTarget(rule: EquivalenceRule, curriculum: Curriculum, slot: Slot): boolean {
  const target = rule.alvo
  if (target.instituicao && normalize(target.instituicao) !== normalize(curriculum.instituicao)) {
    return false
  }
  if (target.curso && normalize(target.curso) !== normalize(curriculum.curso)) {
    return false
  }
  if (target.habilitacao) {
    const habilitacao = normalize(curriculum.habilitacao ?? '')
    if (!habilitacao.includes(normalize(target.habilitacao))) return false
  }
  if (target.codigo) {
    if (!slot.codigo || codeKey(slot.codigo) !== codeKey(target.codigo)) return false
  }
  if (target.componente && normalize(slot.nome) !== normalize(target.componente)) {
    return false
  }
  return Boolean(target.codigo || target.componente)
}

function findSourceForOrigin(
  sources: SourceDiscipline[],
  origin: EquivalenceRule['origens'][number],
): SourceDiscipline | undefined {
  if (origin.codigo) {
    const key = codeKey(origin.codigo)
    const byCode = sources.find(
      (source) => codeKey(source.codigo) === key || codeKey(source.id) === key,
    )
    if (byCode) return byCode
  }
  if (origin.nome) {
    const key = normalize(origin.nome)
    return sources.find((source) => normalize(source.nome) === key)
  }
  return undefined
}

/**
 * Adiciona arestas de cobertura temática geradas a partir de ementas. Elas não
 * substituem o match por nome quando este é melhor, e cada origem declara
 * quantas horas pode cobrir do componente-alvo (cobertura parcial).
 */
function applyRules(
  edges: Edge[],
  curriculum: Curriculum,
  slots: Slot[],
  sources: SourceDiscipline[],
  rules: EquivalenceRule[],
  transcriptInstitution: string,
): Edge[] {
  if (rules.length === 0) return edges

  const byPair = new Map(edges.map((edge) => [`${edge.source.id}|${edge.slot.id}`, edge]))

  for (const rule of rules) {
    if (
      rule.origem_instituicao &&
      normalize(rule.origem_instituicao) !== normalize(transcriptInstitution)
    ) {
      continue
    }
    for (const slot of slots) {
      if (!ruleMatchesTarget(rule, curriculum, slot)) continue
      for (const origin of rule.origens) {
        const source = findSourceForOrigin(sources, origin)
        if (!source) continue
        const targetSequence = sequence(slot.nome)
        const sourceSequence = sequence(source.nome)
        if (
          targetSequence &&
          sourceSequence &&
          targetSequence !== sourceSequence
        ) {
          continue
        }
        const targetConcepts = concepts(slot.nome)
        const sourceConcepts = concepts(source.nome)
        const specificTargetConcepts = [...targetConcepts].filter(
          (concept) => !BROAD_CONCEPTS.has(concept),
        )
        const sharedSpecificConcept = specificTargetConcepts.some((concept) =>
          sourceConcepts.has(concept),
        )
        const sharedConcept = [...targetConcepts].some((concept) =>
          sourceConcepts.has(concept),
        )
        const sharedSpecificToken = sharedSpecificNameToken(slot.nome, source.nome)
        const score = Math.min(1, Math.max(0, Number(origin.score) || 0))

        if (isLab(slot.nome) !== isLab(source.nome) && !sharedSpecificConcept) {
          continue
        }
        if (
          specificTargetConcepts.length > 0 &&
          !sharedSpecificConcept
        ) {
          continue
        }
        if (
          isLab(slot.nome) === isLab(source.nome) &&
          !sharedConcept &&
          !sharedSpecificToken &&
          score < 0.755
        ) {
          continue
        }
        const maxHours = Math.max(0, Number(origin.horas_cobertura) || 0)
        if (score <= 0 || maxHours <= 0) continue
        const confianca: Confidence =
          origin.confianca ?? (score >= 0.85 ? 'alta' : score >= 0.7 ? 'media' : 'baixa')
        const edge: Edge = {
          source,
          slot,
          option: origin.rotulo ?? 'Cobertura temática por ementa',
          score,
          confianca,
          conceitos: ['cobertura_tematica'],
          tokens: [],
          rank: score,
          maxHours,
          ignoreSourceHours: Boolean(origin.ignorar_carga_horaria),
          priority: Math.max(0, Number(origin.prioridade) || 0),
          ruleId: rule.id,
        }
        const key = `${source.id}|${slot.id}`
        const current = byPair.get(key)
        // Uma regra de cobertura integral (carga da origem não limita) vence
        // um match por nome que só cobriria parte da carga do alvo.
        const fullCoverageRule = edge.ignoreSourceHours && !current?.ignoreSourceHours
        if (!current || edge.score > current.score || fullCoverageRule) {
          byPair.set(key, edge)
        }
      }
    }
  }

  return [...byPair.values()]
}

function addFlowEdge(
  graph: FlowEdge[][],
  from: number,
  to: number,
  cap: number,
  cost: number,
  meta?: Edge,
): FlowEdge {
  const forward: FlowEdge = {
    to,
    rev: graph[to].length,
    cap,
    originalCap: cap,
    cost,
    meta,
  }
  const backward: FlowEdge = {
    to: from,
    rev: graph[from].length,
    cap: 0,
    originalCap: 0,
    cost: -cost,
  }
  graph[from].push(forward)
  graph[to].push(backward)
  return forward
}

/**
 * Fluxo de custo mínimo / máximo valor.
 *
 * Cada origem tem capacidade de horas; cada slot-alvo tem demanda de horas.
 * A aresta origem -> slot recebe valor `score + 0.01` por hora, de modo que
 * o fluxo maximize primeiro a qualidade do pareamento e, em empate, as horas
 * aproveitadas. O algoritmo augmenta enquanto houver caminho de custo
 * negativo (valor positivo) no grafo residual; portanto pode deixar
 * capacidade sem uso em vez de forçar um pareamento ruim.
 */
function maxCostFlow(
  edges: Edge[],
  sources: SourceDiscipline[],
  slots: Slot[],
  ignoreWorkload = false,
): MatchedEdge[] {
  const sourceIndex = new Map(sources.map((source, index) => [source.id, index]))
  const slotIndex = new Map(slots.map((slot, index) => [slot.id, index]))
  const sourceOffset = 1
  const slotOffset = sourceOffset + sources.length
  const sink = slotOffset + slots.length
  const nodeCount = sink + 1
  const sourceNode = 0
  const graph: FlowEdge[][] = Array.from({ length: nodeCount }, () => [])
  const pairEdges: FlowEdge[] = []
  const sourceCapacity = new Map(sources.map((source) => [source.id, source.horas]))

  for (const edge of edges) {
    let capacity = sourceCapacity.get(edge.source.id) ?? 0
    if (edge.ignoreSourceHours && edge.maxHours) {
      capacity = Math.max(capacity, edge.maxHours)
    }
    if (ignoreWorkload && edge.slot.kind === 'fixa') {
      capacity = Math.max(capacity, edge.slot.horas)
    }
    sourceCapacity.set(edge.source.id, capacity)
  }

  for (let index = 0; index < sources.length; index += 1) {
    addFlowEdge(
      graph,
      sourceNode,
      sourceOffset + index,
      sourceCapacity.get(sources[index].id) ?? sources[index].horas,
      0,
    )
  }
  for (let index = 0; index < slots.length; index += 1) {
    addFlowEdge(graph, slotOffset + index, sink, slots[index].horas, 0)
  }

  for (const edge of edges) {
    const from = sourceIndex.get(edge.source.id)
    const to = slotIndex.get(edge.slot.id)
    if (from === undefined || to === undefined || edge.score <= 0) continue
    const ignoreHoursForEdge =
      edge.ignoreSourceHours ||
      (ignoreWorkload && edge.slot.kind === 'fixa')
    const cap = ignoreHoursForEdge
      ? Math.min(edge.slot.horas, edge.maxHours ?? Number.POSITIVE_INFINITY)
      : Math.min(
        edge.source.horas,
        edge.slot.horas,
        edge.maxHours ?? Number.POSITIVE_INFINITY,
      )
    if (cap <= 0) continue
    pairEdges.push(
      addFlowEdge(
        graph,
        sourceOffset + from,
        slotOffset + to,
        cap,
        -(edge.score + 0.01 + (edge.priority ?? 0)),
        edge,
      ),
    )
  }

  const maxAugmentations = Math.max(100, pairEdges.length * 2 + 10)

  for (let iteration = 0; iteration < maxAugmentations; iteration += 1) {
    const dist = Array<number>(nodeCount).fill(Number.POSITIVE_INFINITY)
    const inQueue = Array<boolean>(nodeCount).fill(false)
    const prevNode = Array<number>(nodeCount).fill(-1)
    const prevEdge = Array<number>(nodeCount).fill(-1)
    const queue = [sourceNode]
    dist[sourceNode] = 0
    inQueue[sourceNode] = true

    for (let head = 0; head < queue.length; head += 1) {
      const node = queue[head]
      inQueue[node] = false
      const base = dist[node]
      const adjacency = graph[node]
      for (let index = 0; index < adjacency.length; index += 1) {
        const edge = adjacency[index]
        if (edge.cap <= 1e-9) continue
        const candidate = base + edge.cost
        if (candidate >= dist[edge.to] - 1e-9) continue
        dist[edge.to] = candidate
        prevNode[edge.to] = node
        prevEdge[edge.to] = index
        if (!inQueue[edge.to]) {
          queue.push(edge.to)
          inQueue[edge.to] = true
        }
      }
    }

    // Só vale a pena augmentar se o caminho tem valor positivo.
    if (!Number.isFinite(dist[sink]) || dist[sink] >= -1e-9) break

    let amount = Number.POSITIVE_INFINITY
    for (let node = sink; node !== sourceNode; node = prevNode[node]) {
      if (prevNode[node] < 0) {
        amount = 0
        break
      }
      amount = Math.min(amount, graph[prevNode[node]][prevEdge[node]].cap)
    }
    if (amount <= 1e-9 || !Number.isFinite(amount)) break

    for (let node = sink; node !== sourceNode; node = prevNode[node]) {
      const from = prevNode[node]
      const edge = graph[from][prevEdge[node]]
      edge.cap -= amount
      graph[node][edge.rev].cap += amount
    }
  }

  const matched: MatchedEdge[] = []
  for (const edge of pairEdges) {
    const hours = edge.originalCap - edge.cap
    if (hours <= 1e-9 || !edge.meta) continue
    matched.push({ edge: edge.meta, hours })
  }
  return matched
}

export function matchCurriculum(
  curriculum: Curriculum,
  transcript: Transcript,
  rules: EquivalenceRule[] = [],
  options: MatchOptions = {},
): MatchResult {
  const { slots, naoAbativeis } = buildSlots(curriculum)
  const sources = loadSources(transcript)
  const ignoreWorkload = Boolean(options.ignoreWorkload)
  const nameEdges: Edge[] = []

  for (const source of sources) {
    for (const slot of slots) {
      const edge = bestEdgeForSlot(source, slot, ignoreWorkload)
      if (edge) nameEdges.push(edge)
    }
  }

  const edges = applyRules(
    nameEdges,
    curriculum,
    slots,
    sources,
    rules,
    transcript.instituicao,
  )

  edges.sort((a, b) => {
    if (b.rank !== a.rank) return b.rank - a.rank
    if (b.score !== a.score) return b.score - a.score
    return Math.min(b.source.horas, b.slot.horas) - Math.min(a.source.horas, a.slot.horas)
  })

  const matched = maxCostFlow(edges, sources, slots, ignoreWorkload)
  const allocations: Allocation[] = matched
    .filter(({ edge, hours }) => {
      // Em slots fixos, evita frações pequenas que não fecham o componente.
      // Em grupos de eletivas, qualquer fração ajuda a somar os créditos.
      const minimum = edge.slot.kind === 'fixa'
        ? Math.min(MIN_PARTIAL_HOURS, edge.slot.horas)
        : 0
      return hours >= minimum
    })
    .map(({ edge, hours }) => ({
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
      horas: hours,
      conceitos: edge.conceitos,
      tokens: edge.tokens,
      ruleId: edge.ruleId,
    }))

  allocations.sort(
    (a, b) =>
      a.grupoNome.localeCompare(b.grupoNome, 'pt-BR') ||
      a.slotNome.localeCompare(b.slotNome, 'pt-BR') ||
      b.score - a.score,
  )

  const allocatedBySlot = new Map<string, number>()
  for (const allocation of allocations) {
    allocatedBySlot.set(
      allocation.slotId,
      (allocatedBySlot.get(allocation.slotId) ?? 0) + allocation.horas,
    )
  }

  const slotResults: SlotResult[] = slots
    .map((slot) => {
      const alocado = allocatedBySlot.get(slot.id) ?? 0
      const restante = Math.max(0, slot.horas - alocado)
      const allocationsForSlot = allocations
        .filter((allocation) => allocation.slotId === slot.id)
        .sort((a, b) => b.score - a.score)
      const status: SlotResult['status'] =
        restante <= 1e-9 ? 'coberto' : alocado > 0 ? 'parcial' : 'aberto'
      return {
        slot,
        alocado,
        restante,
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
    'Estimativa por nome + carga horária, complementada por cobertura temática gerada de ementas quando disponível.',
    'Fluxo de custo mínimo m-para-n: uma origem pode cobrir vários alvos e um alvo pode combinar várias origens.',
    'Estágio, TCC, extensão, atividades complementares e projetos foram separados como não abatíveis.',
    'A estimativa de semestres ignora pré-requisitos, oferta, limite de aproveitamento e regras específicas de optativa livre.',
    'Não é uma decisão oficial de equivalência; a IES de destino decide.',
  ]

  if (slots.some((slot) => slot.livre)) {
    avisos.push(
      'Grupos de eletivas livres aceitam qualquer disciplina elegível da origem; a confiança é baixa e a regra da IES pode ser mais restrita.',
    )
  }

  if (ignoreWorkload) {
    avisos.push(
      'Modo de teste ativo: a carga horária da origem não limita o componente-alvo. Uma disciplina de 30h pode cobrir um componente de 90h; use com cautela.',
    )
  }

  const usedRules = new Set(
    allocations.map((allocation) => allocation.ruleId).filter((ruleId): ruleId is string => Boolean(ruleId)),
  )
  if (usedRules.size > 0) {
    avisos.push(
      'Inclui cobertura temática gerada por ementa (TF-IDF + nome); é uma heurística, não equivalência oficial. A fonte de cada regra está no arquivo de regras.',
    )
  }

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
