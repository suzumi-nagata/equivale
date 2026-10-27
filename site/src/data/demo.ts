import type { Transcript } from '../lib/types'

/**
 * Histórico fictício, usado apenas para demonstrar o fluxo.
 * Não corresponde a nenhuma pessoa ou instituição real.
 */
export const DEMO_TRANSCRIPT: Transcript = {
  instituicao: 'Demonstração',
  curso: {
    curso: 'Engenharia Elétrica (fictício)',
    habilitacao: 'Ênfase fictícia',
  },
  disciplinas: [
    { codigo: 'DEMO01', codigo_normalizado: 'DEMO01', nome: 'Cálculo Diferencial e Integral I', horas: 90, situacao: 'aprovado', periodo: '2019.1' },
    { codigo: 'DEMO02', codigo_normalizado: 'DEMO02', nome: 'Cálculo Diferencial e Integral II', horas: 90, situacao: 'aprovado', periodo: '2019.2' },
    { codigo: 'DEMO03', codigo_normalizado: 'DEMO03', nome: 'Álgebra Linear', horas: 60, situacao: 'aprovado', periodo: '2019.1' },
    { codigo: 'DEMO04', codigo_normalizado: 'DEMO04', nome: 'Geometria Analítica', horas: 60, situacao: 'aprovado', periodo: '2019.1' },
    { codigo: 'DEMO05', codigo_normalizado: 'DEMO05', nome: 'Algoritmos e Programação', horas: 90, situacao: 'aprovado', periodo: '2019.1' },
    { codigo: 'DEMO06', codigo_normalizado: 'DEMO06', nome: 'Estruturas de Dados', horas: 90, situacao: 'aprovado', periodo: '2020.1' },
    { codigo: 'DEMO07', codigo_normalizado: 'DEMO07', nome: 'Programação Orientada a Objetos', horas: 60, situacao: 'aprovado', periodo: '2020.1' },
    { codigo: 'DEMO08', codigo_normalizado: 'DEMO08', nome: 'Redes de Computadores', horas: 60, situacao: 'aprovado', periodo: '2020.2' },
    { codigo: 'DEMO09', codigo_normalizado: 'DEMO09', nome: 'Sistemas Operacionais', horas: 60, situacao: 'aprovado', periodo: '2020.2' },
    { codigo: 'DEMO10', codigo_normalizado: 'DEMO10', nome: 'Banco de Dados', horas: 60, situacao: 'aprovado', periodo: '2021.1' },
    { codigo: 'DEMO11', codigo_normalizado: 'DEMO11', nome: 'Engenharia de Software', horas: 60, situacao: 'aprovado', periodo: '2021.1' },
    { codigo: 'DEMO12', codigo_normalizado: 'DEMO12', nome: 'Probabilidade e Estatística', horas: 60, situacao: 'aprovado', periodo: '2020.1' },
    { codigo: 'DEMO13', codigo_normalizado: 'DEMO13', nome: 'Física I', horas: 60, situacao: 'aprovado', periodo: '2019.1' },
    { codigo: 'DEMO14', codigo_normalizado: 'DEMO14', nome: 'Física II', horas: 60, situacao: 'aprovado', periodo: '2019.2' },
    { codigo: 'DEMO15', codigo_normalizado: 'DEMO15', nome: 'Circuitos Digitais', horas: 60, situacao: 'aprovado', periodo: '2020.1' },
    { codigo: 'DEMO16', codigo_normalizado: 'DEMO16', nome: 'Inteligência Artificial', horas: 60, situacao: 'aprovado', periodo: '2021.2' },
    { codigo: 'DEMO17', codigo_normalizado: 'DEMO17', nome: 'Segurança da Informação', horas: 60, situacao: 'aprovado', periodo: '2021.2' },
    { codigo: 'DEMO18', codigo_normalizado: 'DEMO18', nome: 'Trabalho de Conclusão de Curso', horas: 80, situacao: 'suficiente', periodo: '2022.1' },
    { codigo: 'DEMO19', codigo_normalizado: 'DEMO19', nome: 'Estágio Supervisionado', horas: 180, situacao: 'suficiente', periodo: '2022.1' },
  ],
}
