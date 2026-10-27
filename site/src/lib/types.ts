export type Grau = 'tecnologo' | 'bacharelado' | 'licenciatura' | string

export interface CurriculumDiscipline {
  nome: string
  horas: number
  tipo?: string
}

export interface CurriculumComponent {
  nome: string
  horas: number
  tipo?: string
  opcoes_ref?: string
}

export interface CurriculumGroup {
  ordem: number
  nome: string
  horas: number
  tipo?: string
  disciplinas?: CurriculumDiscipline[]
  componentes?: CurriculumComponent[]
}

export interface Curriculum {
  id: string
  instituicao: string
  curso: string
  grau: Grau
  modalidade: string
  duracao_meses: number
  carga_horaria_total: number
  fonte: string
  grupos: CurriculumGroup[]
  eletivas: Record<string, string[]>
}

export interface MecInfo {
  status?: string
  ato?: string | null
  verificado?: boolean
  observacao?: string | null
  fonte?: string | null
}

export interface DadosInfo {
  grade_disponivel?: boolean
  grade_com_carga_horaria?: boolean
  ppc_disponivel?: boolean
  ementa_disponivel?: boolean
  completude?: string
}

export interface IngressoInfo {
  formas?: string[]
  segunda_graduacao?: boolean | null
  segunda_graduacao_sem_vestibular?: boolean | null
  observacao?: string | null
}

export interface PrecoInfo {
  mensalidade_a_partir?: number | null
  observacao?: string | null
}

export interface CourseRecord {
  id: string
  instituicao: string
  curso: string
  grau: Grau
  modalidade: string
  duracao_meses: number | null
  carga_horaria_total: number | null
  mec?: MecInfo
  dados?: DadosInfo
  ingresso?: IngressoInfo
  preco?: PrecoInfo
  fontes?: string[]
  observacoes?: string[]
}

export interface CoursesFile {
  cursos: CourseRecord[]
}

export interface CurriculumIndexEntry {
  file: string
  id: string
  instituicao: string
  curso: string
  grau: Grau
  modalidade: string
  duracao_meses: number
  carga_horaria_total: number
  fonte: string
}

export interface CurriculumIndexFile {
  curriculos: CurriculumIndexEntry[]
}

export interface TranscriptDiscipline {
  codigo?: string
  codigo_normalizado?: string
  nome: string
  horas: number | null
  situacao: string
  periodo?: string | null
  media?: number | null
}

export interface Transcript {
  instituicao: string
  curso?: Record<string, string> | null
  disciplinas: TranscriptDiscipline[]
}

export interface SourceDiscipline {
  id: string
  codigo: string
  nome: string
  horas: number
  periodo: string | null
  situacao: string
}

export interface Slot {
  id: string
  grupoOrdem: number
  grupoNome: string
  nome: string
  horas: number
  opcoes: string[]
  tipo: string
  kind: 'fixa' | 'eletiva'
  abativel: boolean
}

export type Confidence = 'alta' | 'media' | 'baixa'

export interface Allocation {
  sourceId: string
  sourceCodigo: string
  sourceNome: string
  sourcePeriodo: string | null
  slotId: string
  slotNome: string
  grupoNome: string
  opcao: string
  score: number
  confianca: Confidence
  horas: number
  conceitos: string[]
  tokens: string[]
}

export interface SlotResult {
  slot: Slot
  alocado: number
  restante: number
  status: 'coberto' | 'parcial' | 'aberto'
  allocations: Allocation[]
}

export interface MatchSummary {
  horasTotal: number
  horasAbativeis: number
  horasNaoAbativeis: number
  horasAbatidas: number
  coberturaAbativel: number
  coberturaTotal: number
  slotsAbativeis: number
  slotsCobertos: number
  slotsParciais: number
  slotsAbertos: number
  horasRestantesAbativeis: number
  horasRestantesTotais: number
  semestresTotais: number
  horasPorSemestre: number
  semestresRestantes: number
  confiancaMedia: number
}

export interface MatchResult {
  summary: MatchSummary
  slots: SlotResult[]
  allocations: Allocation[]
  naoAbativeis: Slot[]
  fontes: SourceDiscipline[]
  avisos: string[]
}
