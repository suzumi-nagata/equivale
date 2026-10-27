import assert from 'node:assert/strict'
import test from 'node:test'
import { matchCurriculum } from './match'
import type { Curriculum, CurriculumGroup, EquivalenceRule, Transcript } from './types'

function makeCurriculum(groups: CurriculumGroup[], eletivas: Record<string, string[]> = {}): Curriculum {
  const total = groups.reduce((sum, group) => sum + group.horas, 0)
  return {
    id: 'teste',
    instituicao: 'Instituição de teste',
    curso: 'Curso de teste',
    grau: 'bacharelado',
    modalidade: 'presencial',
    duracao_meses: 60,
    carga_horaria_total: total,
    fonte: 'https://example.test/curriculo',
    grupos: groups.map((group, index) => ({ ...group, ordem: index + 1 })),
    eletivas,
  }
}

function fixedGroup(name: string, disciplines: Array<[string, number, string?]>): CurriculumGroup {
  return {
    ordem: 0,
    nome: name,
    horas: disciplines.reduce((sum, [, hours]) => sum + hours, 0),
    disciplinas: disciplines.map(([nome, horas, codigo]) => ({
      nome,
      horas,
      codigo: codigo ?? null,
      tipo: 'obrigatoria',
    })),
  }
}

function makeTranscript(
  items: Array<[string, number, string?]>,
  instituicao = 'Instituição de teste',
): Transcript {
  return {
    instituicao,
    disciplinas: items.map(([nome, horas, codigo], index) => ({
      codigo: codigo ?? `T${index}`,
      codigo_normalizado: codigo ?? `T${index}`,
      nome,
      horas,
      situacao: 'aprovado',
    })),
  }
}

test('uma origem de 60h cobre dois slots de 30h', () => {
  const target = makeCurriculum([fixedGroup('Física', [['Física Geral III', 30], ['Física Geral III', 30]])])
  const result = matchCurriculum(target, makeTranscript([['Física Geral III', 60]]))

  assert.equal(result.allocations.length, 2)
  assert.equal(result.summary.horasAbatidas, 60)
  assert.equal(result.summary.slotsCobertos, 2)
  assert.equal(result.summary.coberturaAbativel, 1)
  assert.equal(
    result.allocations.reduce((sum, allocation) => sum + allocation.horas, 0),
    60,
  )
})

test('duas origens combinam para cobrir um slot de 90h', () => {
  const target = makeCurriculum([fixedGroup('Cálculo', [['Cálculo', 90]])])
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Cálculo I', 45],
      ['Cálculo II', 60],
    ]),
  )

  assert.equal(result.allocations.length, 2)
  assert.equal(result.summary.horasAbatidas, 90)
  assert.equal(result.summary.slotsCobertos, 1)
  assert.equal(result.summary.coberturaAbativel, 1)
})

test('não usa mais horas do que a origem possui', () => {
  const target = makeCurriculum([
    fixedGroup('Cálculo', [['Cálculo I', 90], ['Cálculo II', 90]]),
  ])
  const result = matchCurriculum(target, makeTranscript([['Cálculo I', 60]]))

  assert.equal(result.summary.horasAbatidas, 60)
  assert.equal(result.summary.horasRestantesAbativeis, 120)
  assert.ok(result.allocations.every((allocation) => allocation.horas <= 60))
})

test('slot de eletiva livre aceita qualquer origem elegível', () => {
  const target = makeCurriculum(
    [
      {
        ordem: 0,
        nome: 'Eletivas II (6 créditos)',
        horas: 90,
        componentes: [
          {
            nome: 'Eletivas II',
            horas: 90,
            tipo: 'eletiva',
            opcoes_ref: 'LIVRE',
            livre: true,
          },
        ],
      },
    ],
    { LIVRE: ['Qualquer disciplina elegível'] },
  )
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Desenho Técnico', 60],
      ['Oficinas I', 30],
    ]),
  )

  assert.equal(result.allocations.length, 2)
  assert.equal(result.summary.horasAbatidas, 90)
  assert.equal(result.summary.slotsCobertos, 1)
  assert.ok(result.allocations.every((allocation) => allocation.confianca === 'baixa'))
})

test('a sobra de uma origem vai para a eletiva livre depois do slot específico', () => {
  const target = makeCurriculum(
    [
      fixedGroup('Núcleo Comum', [['Cálculo I', 45]]),
      {
        ordem: 0,
        nome: 'Eletivas I (3 créditos)',
        horas: 45,
        componentes: [
          {
            nome: 'Eletivas I',
            horas: 45,
            tipo: 'eletiva',
            opcoes_ref: 'LIVRE',
            livre: true,
          },
        ],
      },
    ],
    { LIVRE: ['Qualquer disciplina elegível'] },
  )
  const result = matchCurriculum(target, makeTranscript([['Cálculo I', 90]]))

  assert.equal(result.allocations.length, 2)
  assert.equal(result.summary.horasAbatidas, 90)
  assert.equal(result.summary.slotsCobertos, 2)
  const specific = result.allocations.find((allocation) => allocation.slotNome === 'Cálculo I')
  const free = result.allocations.find((allocation) => allocation.slotNome === 'Eletivas I')
  assert.equal(specific?.horas, 45)
  assert.equal(free?.horas, 45)
})

test('projeto final de graduação não é abatível e não vem da origem', () => {
  const target = makeCurriculum([
    fixedGroup('Obrigatórias', [['Projeto Final de Graduação', 180]]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Projeto Final de Graduação', 180]]),
  )

  assert.equal(result.slots.length, 0)
  assert.equal(result.naoAbativeis.length, 1)
  assert.equal(result.summary.horasNaoAbativeis, 180)
  assert.equal(result.summary.horasAbativeis, 0)
  assert.equal(result.summary.horasAbatidas, 0)
  assert.equal(result.allocations.length, 0)
  assert.equal(result.fontes.length, 0)
})

test('regra de ementa combina duas origens com cobertura parcial', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral III', 60, 'F 328']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-f328',
      alvo: {
        instituicao: 'Instituição de teste',
        curso: 'Curso de teste',
        codigo: 'F 328',
        componente: 'Física Geral III',
      },
      origens: [
        {
          codigo: 'EE521',
          nome: 'Introdução à Teoria Eletromagnética',
          horas_cobertura: 30,
          score: 0.82,
          confianca: 'media',
          rotulo: 'Eletrostática e magnetostática',
        },
        {
          codigo: 'EE540',
          nome: 'Teoria Eletromagnética',
          horas_cobertura: 30,
          score: 0.78,
          confianca: 'media',
          rotulo: 'Maxwell e ondas',
        },
      ],
      fonte: 'https://example.test/ementas',
    },
  ]
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Introdução à Teoria Eletromagnética', 60, 'EE521'],
      ['Teoria Eletromagnética', 60, 'EE540'],
    ]),
    rules,
  )

  assert.equal(result.allocations.length, 2)
  assert.equal(result.summary.horasAbatidas, 60)
  assert.equal(result.summary.slotsCobertos, 1)
  assert.equal(result.summary.coberturaAbativel, 1)
  assert.ok(result.allocations.every((allocation) => allocation.ruleId === 'teste-f328'))
  assert.deepEqual(
    result.allocations.map((allocation) => allocation.horas).sort((a, b) => a - b),
    [30, 30],
  )
})

test('regra não ultrapassa a cobertura declarada', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral III', 60, 'F 328']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-f328',
      alvo: { instituicao: 'Instituição de teste', curso: 'Curso de teste', codigo: 'F 328' },
      origens: [
        {
          codigo: 'EE521',
          horas_cobertura: 30,
          score: 0.8,
          confianca: 'media',
        },
      ],
    },
  ]
  const result = matchCurriculum(
    target,
    makeTranscript([['Introdução à Teoria Eletromagnética', 60, 'EE521']]),
    rules,
  )

  assert.equal(result.allocations.length, 1)
  assert.equal(result.summary.horasAbatidas, 30)
  assert.equal(result.summary.slotsParciais, 1)
})

test('regra com carga ignorada cobre 60h com uma origem de 45h', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Resistência dos Materiais', 60, 'EM424']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-em424',
      alvo: { instituicao: 'Instituição de teste', curso: 'Curso de teste', codigo: 'EM424' },
      origens: [
        {
          codigo: 'EM423',
          horas_cobertura: 60,
          score: 0.95,
          confianca: 'alta',
          ignorar_carga_horaria: true,
        },
      ],
    },
  ]
  const result = matchCurriculum(
    target,
    makeTranscript([['Resistência dos Materiais', 45, 'EM423']]),
    rules,
  )

  assert.equal(result.allocations.length, 1)
  assert.equal(result.allocations[0].horas, 60)
  assert.equal(result.summary.horasAbatidas, 60)
  assert.equal(result.summary.slotsCobertos, 1)
  assert.equal(result.summary.coberturaAbativel, 1)
})

test('laboratório de programação não cobre projeto e análise de algoritmos', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Projeto e Análise de Algoritmos I', 60, 'MC458']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Laboratório de Programação Básica de Sistemas Digitais', 60, 'EA871'],
    ]),
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.horasAbatidas, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('não confunde sequências diferentes de uma disciplina', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Cálculo I', 60, 'MA111']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Cálculo II', 60, 'MA211']]),
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('reconhece Física Geral I como Física I', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral I', 60, 'F 128']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Física I', 45, '4323101']]),
  )

  assert.equal(result.allocations.length, 1)
  assert.equal(result.summary.horasAbatidas, 45)
  assert.equal(result.summary.slotsParciais, 1)
})

test('reconhece Física Geral IV como Física IV', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral IV', 60, 'F 428']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Física IV', 60, '4323204']]),
  )

  assert.equal(result.allocations.length, 1)
  assert.equal(result.summary.horasAbatidas, 60)
  assert.equal(result.summary.slotsCobertos, 1)
})

const nameCases: Array<{
  label: string
  target: [string, number]
  source: [string, number]
  expectedHours: number
}> = [
  {
    label: 'Métodos da Engenharia Elétrica casa com Introdução à Engenharia Elétrica',
    target: ['Métodos da Engenharia Elétrica', 60],
    source: ['Introdução à Engenharia Elétrica', 60],
    expectedHours: 60,
  },
  {
    label: 'lab de software básico não é lab de OOP',
    target: ['Laboratório de Programação de Software Básico', 60],
    source: ['Laboratório de Programação Orientada a Objetos para Engenharia Elétrica', 60],
    expectedHours: 0,
  },
  {
    label: 'Ciências do Ambiente casa com o curso de energia/ambiente',
    target: ['Ciências do Ambiente', 30],
    source: ['Energia, Meio Ambiente e Sustentabilidade', 60],
    expectedHours: 30,
  },
  {
    label: 'Análise de Sinais casa com Sistemas e Sinais',
    target: ['Análise de Sinais', 60],
    source: ['Sistemas e Sinais', 60],
    expectedHours: 60,
  },
  {
    label: 'Cálculo Numérico casa com Métodos Numéricos',
    target: ['Cálculo Numérico', 60],
    source: ['Métodos Numéricos', 60],
    expectedHours: 60,
  },
  {
    label: 'Resistência dos Materiais casa com Engenharia dos Materiais',
    target: ['Resistência dos Materiais', 60],
    source: ['Fundamentos de Ciência e Engenharia dos Materiais', 30],
    expectedHours: 30,
  },
  {
    label: 'Física Experimental I casa com Física Experimental A',
    target: ['Introdução à Física Experimental I', 30],
    source: ['Física Experimental A', 30],
    expectedHours: 30,
  },
  {
    label: 'Física Experimental II não casa com Física Experimental A',
    target: ['Introdução à Física Experimental II', 30],
    source: ['Física Experimental A', 30],
    expectedHours: 0,
  },
  {
    label: 'Física Experimental II casa com Física Experimental B',
    target: ['Introdução à Física Experimental II', 30],
    source: ['Física Experimental B', 30],
    expectedHours: 30,
  },
  {
    label: 'Princípios de Controle casa com Sistemas de Controle',
    target: ['Princípios de Controle e Servomecanismo', 60],
    source: ['Sistemas de Controle', 60],
    expectedHours: 60,
  },
  {
    label: 'Circuitos Lógicos casa com Sistemas Digitais I',
    target: ['Circuitos Lógicos', 60],
    source: ['Sistemas Digitais I', 60],
    expectedHours: 60,
  },
  {
    label: 'Modelos Probabilísticos casa com Probabilidade',
    target: ['Introdução aos Modelos Probabilísticos', 60],
    source: ['Probabilidade', 30],
    expectedHours: 30,
  },
]

for (const item of nameCases) {
  test(item.label, () => {
    const target = makeCurriculum([
      fixedGroup('Núcleo Comum', [[item.target[0], item.target[1], 'TARGET']]),
    ])
    const result = matchCurriculum(
      target,
      makeTranscript([[item.source[0], item.source[1], 'SOURCE']]),
    )
    assert.equal(result.summary.horasAbatidas, item.expectedHours)
  })
}

test('regra de conteúdo respeita o conceito específico do alvo', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Projeto e Análise de Algoritmos I', 60, 'MC458']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-paa',
      alvo: { instituicao: 'Instituição de teste', curso: 'Curso de teste', codigo: 'MC458' },
      origens: [
        {
          codigo: 'MC102',
          nome: 'Algoritmos e Programação de Computadores',
          horas_cobertura: 60,
          score: 0.8,
          confianca: 'media',
        },
      ],
    },
  ]
  const result = matchCurriculum(
    target,
    makeTranscript([['Algoritmos e Programação de Computadores', 90, 'MC102']]),
    rules,
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('teoria e laboratório são pareados com o tipo certo', () => {
  const target = makeCurriculum([
    fixedGroup('Obrigatórias', [
      ['Análise Linear de Sistemas', 60, 'EA001'],
      ['Laboratório de Análise Linear', 30, 'EA619'],
    ]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Análise Linear de Sistemas', 60, 'EA001'],
      ['Laboratório de Análise Linear', 30, 'EA619'],
    ]),
  )

  const theory = result.slots.find((slot) => slot.slot.nome === 'Análise Linear de Sistemas')
  const lab = result.slots.find((slot) => slot.slot.nome === 'Laboratório de Análise Linear')
  assert.equal(theory?.allocations[0]?.sourceNome, 'Análise Linear de Sistemas')
  assert.equal(lab?.allocations[0]?.sourceNome, 'Laboratório de Análise Linear')
  assert.equal(result.summary.slotsCobertos, 2)
})

test('computação gráfica não é coberta por programação genérica', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [
      ['Introdução à Computação Gráfica e ao Processamento de Imagem', 60, 'MC920'],
    ]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([
      ['Algoritmos e Programação de Computadores', 30, 'MC102'],
      ['Laboratório de Programação Básica de Sistemas Digitais', 30, 'EA871'],
    ]),
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.horasAbatidas, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('tokens genéricos não cobrem sistemas embarcados', () => {
  const target = makeCurriculum([
    fixedGroup('Obrigatórias', [['Introdução aos Sistemas Embarcados', 90, 'EA701']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Introdução aos Sistemas de Potência', 60, 'PEA3301']]),
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('modo sem carga horária permite uma origem de 30h cobrir 90h', () => {
  const target = makeCurriculum([
    fixedGroup('Obrigatórias', [['Processamento Digital de Sinais', 90, 'EA999']]),
  ])
  const transcript = makeTranscript([
    ['Introdução ao Processamento Digital de Sinais', 30, 'PTC3361'],
  ])

  const conservative = matchCurriculum(target, transcript)
  assert.equal(conservative.allocations.length, 1)
  assert.equal(conservative.summary.horasAbatidas, 30)
  assert.equal(conservative.summary.slotsParciais, 1)

  const permissive = matchCurriculum(target, transcript, [], { ignoreWorkload: true })
  assert.equal(permissive.allocations.length, 1)
  assert.equal(permissive.summary.horasAbatidas, 90)
  assert.equal(permissive.summary.slotsCobertos, 1)
  assert.equal(permissive.summary.coberturaAbativel, 1)
})

test('regra gerada para UNICAMP não se aplica a histórico USP', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral III', 60, 'F 328']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-origem',
      alvo: { instituicao: 'Instituição de teste', curso: 'Curso de teste', codigo: 'F 328' },
      origem_instituicao: 'UNICAMP',
      origens: [
        {
          codigo: 'EE540',
          nome: 'Teoria Eletromagnética',
          horas_cobertura: 60,
          score: 0.8,
          confianca: 'media',
        },
      ],
    },
  ]
  const transcript = makeTranscript([['Teoria Eletromagnética', 60, 'EE540']], 'USP')
  const result = matchCurriculum(target, transcript, rules)

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})

test('modo sem carga permite 60h cobrir um slot de 90h', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física I', 90, 'A']]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Física I', 60, 'A']]),
    [],
    { ignoreWorkload: true },
  )

  assert.equal(result.summary.horasAbatidas, 90)
})

test('modo sem carga não deixa a mesma origem cobrir dois slots', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [
      ['Física A', 90, 'A'],
      ['Física B', 90, 'B'],
    ]),
  ])
  const result = matchCurriculum(
    target,
    makeTranscript([['Física', 60, 'A']]),
    [],
    { ignoreWorkload: true },
  )

  assert.equal(result.summary.horasAbatidas, 90)
})

test('regra de ementa não cruza sequências diferentes', () => {
  const target = makeCurriculum([
    fixedGroup('Núcleo Comum', [['Física Geral IV', 60, 'F 428']]),
  ])
  const rules: EquivalenceRule[] = [
    {
      id: 'teste-fisica-iv',
      alvo: { instituicao: 'Instituição de teste', curso: 'Curso de teste', codigo: 'F 428' },
      origem_instituicao: 'Instituição de teste',
      origens: [
        {
          codigo: 'F315',
          nome: 'Física III',
          horas_cobertura: 60,
          score: 0.8,
          confianca: 'alta',
        },
      ],
    },
  ]
  const result = matchCurriculum(
    target,
    makeTranscript([['Física III', 60, 'F315']]),
    rules,
  )

  assert.equal(result.allocations.length, 0)
  assert.equal(result.summary.slotsAbertos, 1)
})
