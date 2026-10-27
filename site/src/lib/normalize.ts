import type { Confidence } from './types'

const STOPWORDS = new Set([
  'a', 'as', 'o', 'os', 'de', 'da', 'das', 'do', 'dos', 'e', 'em', 'para',
  'por', 'com', 'sem', 'um', 'uma', 'uns', 'umas', 'na', 'nas', 'no', 'nos',
  'ao', 'aos', 'the', 'and', 'of', 'for', 'in', 'on', 'to',
])

const GENERIC_NAME_TOKENS = new Set([
  'laboratorio', 'laboratorios', 'experimental', 'projeto', 'projetos',
  'sistema', 'sistemas', 'introducao', 'fundamento', 'fundamentos',
  'basico', 'basica', 'aplicado', 'aplicada', 'teoria', 'pratica', 'geral',
  'digital', 'linear', 'processamento', 'computacao', 'engenharia', 'eletrica',
  'programacao', 'ambiente', 'meio',
  'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
  '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
])

export const BROAD_CONCEPTS = new Set([
  'programacao', 'calculo', 'seguranca', 'ia', 'redes', 'direito',
  'etica', 'meio_ambiente', 'governanca',
])

interface ConceptPattern {
  concept: string
  patterns: RegExp[]
}

const CONCEPT_PATTERNS: ConceptPattern[] = [
  { concept: 'calculo', patterns: [/(?<!pre )\bcalculo\b(?!\s+numerico)/] },
  { concept: 'calculo_numerico', patterns: [/\bcalculo numerico\b/, /\bmetodos? numericos?\b/, /\bmetodo numerico\b/] },
  { concept: 'algebra_linear', patterns: [/\balgebra linear\b/] },
  { concept: 'geometria_analitica', patterns: [/\bgeometria analitica\b/] },
  { concept: 'probabilidade', patterns: [/\bprobabilidade\b/, /\bprocessos estocasticos\b/, /\bprobabilisticos?\b/] },
  { concept: 'controle', patterns: [/\bcontrole\b/, /\bservomecanismo\b/] },
  { concept: 'resistencia_materiais', patterns: [/\bresistencia dos materiais\b/, /\bengenharia dos materiais\b/, /\bciencia e engenharia dos materiais\b/] },
  { concept: 'sinais', patterns: [/\bsinais\b/] },
  { concept: 'estatistica', patterns: [/\bestatistica\b/] },
  { concept: 'pre_calculo', patterns: [/\bpre calculo\b/, /\bmatematica elementar\b/] },
  { concept: 'programacao', patterns: [/\bprogramacao\b(?!\s+matematica)/, /\balgoritmos?\b/, /\blaboratorio de programacao\b/, /\bintroducao a computacao\b/, /\bintroducao a ciencia da computacao\b/] },
  { concept: 'projeto_algoritmos', patterns: [/\bprojeto e analise de algoritmos\b/, /\bprojeto de algoritmos\b/, /\banalise de algoritmos\b/] },
  { concept: 'estrutura_dados', patterns: [/\bestruturas? de dados\b/] },
  { concept: 'poo', patterns: [/\bprogramacao orientada a objetos\b/, /\borientada a objetos\b/, /\bpoo\b/] },
  { concept: 'banco_dados', patterns: [/\bbanco de dados\b/, /\bbanco dados\b/, /\bsgbd\b/] },
  { concept: 'engenharia_software', patterns: [/\bengenharia de software\b/] },
  { concept: 'sistemas_operacionais', patterns: [/\bsistemas? operacionais?\b/] },
  { concept: 'redes', patterns: [/\bredes de computadores\b/, /\bredes e comunicacoes\b/, /\bcomunicacao de dados\b/, /\bprotocolos de redes\b/] },
  { concept: 'ia', patterns: [/\binteligencia artificial\b/, /\binteligencia computacional\b/] },
  { concept: 'machine_learning', patterns: [/\bmachine learning\b/, /\baprendizado de maquina\b/, /\bdeep learning\b/, /\bredes neurais\b/] },
  { concept: 'organizacao_computadores', patterns: [/\barquitetura de computadores\b/, /\borganizacao de computadores\b/, /\borganizacao basica de computadores\b/, /\blinguagem de montagem\b/, /\bsistemas de computacao digital\b/, /\barquitetura e organizacao de computadores\b/] },
  { concept: 'circuitos_digitais', patterns: [/\bsistemas digitais\b/, /\bcircuitos digitais\b/, /\bcircuitos logicos\b/, /\blaboratorio digital\b/] },
  { concept: 'cloud', patterns: [/\bcomputacao em nuvem\b/, /\bcloud\b/] },
  { concept: 'big_data', patterns: [/\bbig data\b/] },
  { concept: 'seguranca', patterns: [/\bseguranca da informacao\b/, /\bseguranca em sistemas de informacao\b/, /\bseguranca em comunicacao de dados\b/, /\bciberseguranca\b/, /\bseguranca de sistemas\b/, /\bseguranca em banco de dados\b/, /\bseguranca de redes\b/, /\bseguranca em ambiente web\b/, /\bseguranca cibernetica\b/] },
  { concept: 'devops', patterns: [/\bdevops\b/, /\bintegracao continua\b/] },
  { concept: 'gestao_projetos', patterns: [/\bgestao de projetos\b/, /\bmetodos ageis\b/, /\bgerencia de projetos\b/] },
  { concept: 'ihc', patterns: [/\bdesign de interacao\b/, /\binterface homem\b/, /\bihc\b/, /\busabilidade\b/] },
  { concept: 'modelagem_sistemas', patterns: [/\banalise e modelagem de sistemas\b/, /\bmodelagem de sistemas\b/] },
  { concept: 'web', patterns: [/\bdesenvolvimento web\b/, /\bferramentas de desenvolvimento web\b/, /\bfront end\b/, /\bback end\b/, /\barquitetura e desenvolvimento de apis\b/] },
  { concept: 'mobile', patterns: [/\bdesenvolvimento mobile\b/, /\bcomputacao movel\b/, /\bmobile\b/] },
  { concept: 'teste', patterns: [/\btestes? de software\b/, /\bqualidade de software\b/] },
  { concept: 'governanca', patterns: [/\bgovernanca de ti\b/, /\bgovernanca\b/, /\bgestao da tecnologia da informacao\b/] },
  { concept: 'direito_cibernetico', patterns: [/\bdireito cibernetico\b/] },
  { concept: 'direito', patterns: [/\bdireito\b(?! cibernetico)/, /\blegislacao\b/] },
  { concept: 'empreendedorismo', patterns: [/\bempreendedorismo\b/, /\binovacao\b/] },
  { concept: 'metodologia', patterns: [/\bmetodologia cientifica\b/, /\bmetodologia de pesquisa\b/] },
  { concept: 'portugues', patterns: [/\bproducao textual\b/, /\blingua portuguesa\b/, /\bcomunicacao e expressao\b/, /\bportugues\b/] },
  { concept: 'etnico_racial', patterns: [/\brelacoes etnico\b/, /\bafricana\b/, /\bafro brasileira\b/, /\bindigena\b/] },
  { concept: 'meio_ambiente', patterns: [/\bciencias do ambiente\b/, /\bsustentabilidade\b/] },
  { concept: 'formacao_cidada', patterns: [/\bformacao cidada\b/] },
  { concept: 'etica', patterns: [/\betica\b/] },
  { concept: 'sociologia', patterns: [/\bsociologia\b/] },
  { concept: 'ciencia_tecnologia_sociedade', patterns: [/\bciencia, tecnologia e sociedade\b/, /\bciencia tecnologia e sociedade\b/] },
  { concept: 'logica', patterns: [/\braciocinio logico\b/, /\blogica matematica\b/] },
  { concept: 'processos_negocios', patterns: [/\bmodelagem de processos\b/, /\bprocessos e negocios\b/] },
  { concept: 'pesquisa_operacional', patterns: [/\bpesquisa operacional\b/] },
  { concept: 'sistemas_informacao', patterns: [/\bsistemas? de informacao\b/, /\bfundamentos de sistema de informacao\b/] },
  { concept: 'requisitos', patterns: [/\bengenharia de requisitos\b/, /\brequisitos\b/] },
  { concept: 'metricas', patterns: [/\bmetricas\b/, /\bestimativa de software\b/] },
  { concept: 'configuracao', patterns: [/\bgerencia de configuracao\b/] },
  { concept: 'visualizacao', patterns: [/\bvisualizacao de dados\b/, /\bstorytelling\b/] },
  { concept: 'computacao_grafica', patterns: [/\bcomputacao grafica\b/, /\bprocessamento de imagens?\b/, /\bvisao computacional\b/, /\bimagens? digitais?\b/] },
  { concept: 'distribuidos', patterns: [/\bsistemas distribuidos\b/] },
  { concept: 'compiladores', patterns: [/\bcompiladores\b/, /\blinguagens formais\b/] },
  { concept: 'teoria_computacao', patterns: [/\bteoria da computacao\b/, /\bteoria dos grafos\b/] },
]

export function normalize(text: string): string {
  return text
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function tokenize(text: string): Set<string> {
  return new Set(
    normalize(text)
      .split(' ')
      .filter(
        (token) =>
          (token.length > 2 && !STOPWORDS.has(token)) ||
          /^(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)$/.test(token),
      ),
  )
}

const ROMAN_SEQUENCE: Record<string, string> = {
  i: '1',
  ii: '2',
  iii: '3',
  iv: '4',
  v: '5',
  vi: '6',
  vii: '7',
  viii: '8',
  ix: '9',
  x: '10',
  a: '1',
  b: '2',
  c: '3',
}

export function sequence(text: string): string | null {
  const tokens = normalize(text).split(' ')
  for (let index = tokens.length - 1; index >= 0; index -= 1) {
    const token = tokens[index]
    if (ROMAN_SEQUENCE[token]) return ROMAN_SEQUENCE[token]
    if (/^\d+$/.test(token)) {
      const value = Number(token)
      if (value >= 1 && value <= 10) return String(value)
    }
  }
  return null
}

export function isLab(text: string): boolean {
  return /\b(laboratorio|laboratorios|experimental)\b/.test(normalize(text))
}

export function concepts(text: string): Set<string> {
  const normalized = normalize(text)
  const found = new Set<string>()
  for (const { concept, patterns } of CONCEPT_PATTERNS) {
    if (patterns.some((pattern) => pattern.test(normalized))) {
      found.add(concept)
    }
  }
  return found
}

export interface NameScore {
  score: number
  parcial: boolean
  conceitos: string[]
  tokens: string[]
  motivo: string
}

export interface PairScore {
  score: number
  confianca: Confidence
  parcial: boolean
  conceitos: string[]
  tokens: string[]
  workloadFit: number
}

export function nameScore(targetName: string, sourceName: string): NameScore {
  const targetConcepts = concepts(targetName)
  const sourceConcepts = concepts(sourceName)
  const targetTokens = tokenize(targetName)
  const sourceTokens = tokenize(sourceName)
  const sharedTokens = [...targetTokens].filter((token) => sourceTokens.has(token)).sort()
  const union = new Set([...targetTokens, ...sourceTokens])
  const jaccard = union.size ? sharedTokens.length / union.size : 0
  const targetSequence = sequence(targetName)
  const sourceSequence = sequence(sourceName)

  if (targetSequence && sourceSequence && targetSequence !== sourceSequence) {
    return {
      score: 0,
      parcial: true,
      conceitos: [...sourceConcepts].sort(),
      tokens: sharedTokens,
      motivo: 'sequência diferente',
    }
  }

  if (isLab(targetName) !== isLab(sourceName)) {
    return {
      score: 0,
      parcial: true,
      conceitos: [...sourceConcepts].sort(),
      tokens: sharedTokens,
      motivo: 'teoria/laboratório',
    }
  }

  const specificTargetTokens = [...targetTokens].filter(
    (token) => !GENERIC_NAME_TOKENS.has(token),
  )
  const specificSharedTokens = specificTargetTokens.filter((token) => sourceTokens.has(token))
  const specificUnion = new Set([...specificTargetTokens, ...sourceTokens])
  const specificJaccard = specificUnion.size
    ? specificSharedTokens.length / specificUnion.size
    : 0
  const specificContainment = specificTargetTokens.length
    ? specificSharedTokens.length / specificTargetTokens.length
    : 0
  const targetSpecificConcepts = [...targetConcepts].filter(
    (concept) => !BROAD_CONCEPTS.has(concept),
  )
  const specificConceptShared = targetSpecificConcepts.some((concept) =>
    sourceConcepts.has(concept),
  )

  if (
    specificTargetTokens.length > 0 &&
    specificSharedTokens.length === 0 &&
    !specificConceptShared
  ) {
    return {
      score: 0,
      parcial: true,
      conceitos: [...sourceConcepts].sort(),
      tokens: sharedTokens,
      motivo: 'apenas tokens genéricos',
    }
  }

  if (targetConcepts.size > 0) {
    if (
      targetSpecificConcepts.length > 0 &&
      !targetSpecificConcepts.some((concept) => sourceConcepts.has(concept))
    ) {
      return {
        score: 0,
        parcial: true,
        conceitos: [...sourceConcepts].sort(),
        tokens: sharedTokens,
        motivo: 'conceito específico ausente',
      }
    }
    const common = [...targetConcepts].filter((concept) => sourceConcepts.has(concept))
    const overlap = common.length / targetConcepts.size
    if (overlap === 0) {
      return {
        score: 0,
        parcial: true,
        conceitos: [...sourceConcepts].sort(),
        tokens: sharedTokens,
        motivo: 'sem conceito em comum',
      }
    }
    let score = Math.min(1, overlap + 0.1 * Math.max(jaccard, specificJaccard))
    if (overlap === 1) score = Math.max(score, 0.9)
    return {
      score,
      parcial: overlap < 1,
      conceitos: common.sort(),
      tokens: sharedTokens,
      motivo: 'conceito',
    }
  }

  if (targetTokens.size === 0) {
    return {
      score: 0,
      parcial: true,
      conceitos: [...sourceConcepts].sort(),
      tokens: sharedTokens,
      motivo: 'nome sem tokens',
    }
  }

  const containment = Math.max(sharedTokens.length / targetTokens.size, specificContainment)
  const tokenJaccard = Math.max(jaccard, specificJaccard)
  if (containment >= 0.6 && tokenJaccard >= 0.4) {
    return {
      score: 0.6 * containment + 0.4 * tokenJaccard,
      parcial: true,
      conceitos: [...sourceConcepts].sort(),
      tokens: sharedTokens,
      motivo: 'tokens',
    }
  }

  return {
    score: 0,
    parcial: true,
    conceitos: [...sourceConcepts].sort(),
    tokens: sharedTokens,
    motivo: 'tokens insuficientes',
  }
}

export function workloadFit(targetHours: number, sourceHours: number): number {
  if (targetHours <= 0) return 0
  if (sourceHours >= targetHours) return 1
  const ratio = sourceHours / targetHours
  if (ratio >= 0.75) return 0.8
  if (ratio >= 0.5) return 0.5
  return 0.2
}

export function pairScore(
  targetName: string,
  targetHours: number,
  sourceName: string,
  sourceHours: number,
): PairScore {
  const details = nameScore(targetName, sourceName)
  const fit = workloadFit(targetHours, sourceHours)
  let score = 0.8 * details.score + 0.2 * fit
  if (details.score < 0.5 || score < 0.55) score = 0

  let confianca: Confidence = 'baixa'
  if (score >= 0.85 && !details.parcial && details.tokens.length > 0) {
    confianca = 'alta'
  } else if (score >= 0.7) {
    confianca = 'media'
  }

  return {
    score: Math.round(score * 10000) / 10000,
    confianca,
    parcial: details.parcial,
    conceitos: details.conceitos,
    tokens: details.tokens,
    workloadFit: fit,
  }
}
