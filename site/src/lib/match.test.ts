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

function makeTranscript(items: Array<[string, number, string?]>): Transcript {
  return {
    instituicao: 'Instituição de teste',
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
  const target = makeCurriculum([fixedGroup('Cálculo', [['Cálculo A', 90]])])
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
