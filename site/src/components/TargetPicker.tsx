import { useEffect, useMemo, useState } from 'react'
import { normalize } from '../lib/normalize'
import type { CourseRecord, Curriculum } from '../lib/types'

interface Props {
  targets: Curriculum[]
  courses: CourseRecord[]
  selectedId: string
  onSelect: (id: string) => void
}

function degreeLabel(grau: string): string {
  if (grau === 'tecnologo') return 'Tecnólogo'
  if (grau === 'bacharelado') return 'Bacharelado'
  if (grau === 'licenciatura') return 'Licenciatura'
  return grau
}

function formatHours(hours: number): string {
  return `${new Intl.NumberFormat('pt-BR').format(hours)}h`
}

function mecLabel(status: string | undefined): string {
  if (status === 'reconhecido') return 'MEC reconhecido'
  if (status === 'em_reconhecimento') return 'MEC aguardando reconhecimento'
  if (status === 'nao_verificado') return 'MEC: ato não consultado'
  return 'MEC não informado'
}

function mecTone(status: string | undefined): string {
  if (status === 'reconhecido') return 'tag--ok'
  if (status === 'em_reconhecimento') return 'tag--risk'
  return 'tag--muted'
}

function completudeLabel(value: string | undefined): string {
  if (value === 'grade_com_ch') return 'grade pública com CH'
  if (value === 'grade_sem_ch') return 'grade sem CH'
  if (value === 'so_marketing') return 'dados parciais'
  if (value === 'minimo') return 'dados mínimos'
  return 'dados públicos'
}

export function TargetPicker({ targets, courses, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [instituicao, setInstituicao] = useState('')
  const [modalidade, setModalidade] = useState('')
  const [grau, setGrau] = useState('')

  const institutions = useMemo(
    () => [...new Set(targets.map((target) => target.instituicao))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [targets],
  )
  const modalities = useMemo(
    () => [...new Set(targets.map((target) => target.modalidade))].sort((a, b) => a.localeCompare(b, 'pt-BR')),
    [targets],
  )
  const degrees = useMemo(
    () => [...new Set(targets.map((target) => target.grau))].sort((a, b) => degreeLabel(a).localeCompare(degreeLabel(b), 'pt-BR')),
    [targets],
  )

  const filtered = useMemo(() => {
    const term = normalize(query)
    return targets.filter((target) => {
      if (instituicao && target.instituicao !== instituicao) return false
      if (modalidade && target.modalidade !== modalidade) return false
      if (grau && target.grau !== grau) return false
      if (!term) return true
      const haystack = normalize(
        `${target.instituicao} ${target.curso} ${target.habilitacao ?? ''} ${target.grau} ${target.modalidade}`,
      )
      return haystack.includes(term)
    })
  }, [targets, query, instituicao, modalidade, grau])

  useEffect(() => {
    if (filtered.length === 0) return
    if (!filtered.some((target) => target.id === selectedId)) {
      onSelect(filtered[0].id)
    }
  }, [filtered, selectedId, onSelect])

  const hasFilters = Boolean(query || instituicao || modalidade || grau)
  const reset = () => {
    setQuery('')
    setInstituicao('')
    setModalidade('')
    setGrau('')
  }

  return (
    <>
      <div className="target-filters" role="search" aria-label="Filtrar cursos alvo">
        <label className="target-filter target-filter--search">
          <span>Buscar</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="curso, instituição ou habilitação"
          />
        </label>
        <label className="target-filter">
          <span>Instituição</span>
          <select value={instituicao} onChange={(event) => setInstituicao(event.target.value)}>
            <option value="">Todas</option>
            {institutions.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="target-filter">
          <span>Modalidade</span>
          <select value={modalidade} onChange={(event) => setModalidade(event.target.value)}>
            <option value="">Todas</option>
            {modalities.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="target-filter">
          <span>Grau</span>
          <select value={grau} onChange={(event) => setGrau(event.target.value)}>
            <option value="">Todos</option>
            {degrees.map((item) => (
              <option key={item} value={item}>{degreeLabel(item)}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="button button--ghost target-filter-reset"
          onClick={reset}
          disabled={!hasFilters}
        >
          Limpar
        </button>
      </div>
      <p className="filter-count">
        {filtered.length} de {targets.length} cursos
      </p>

      <fieldset className="target-picker">
        <legend className="sr-only">Curso alvo</legend>
        {filtered.length === 0 && (
          <p className="empty-note">Nenhum curso corresponde aos filtros.</p>
        )}
        {filtered.map((target) => {
          const record = courses.find((course) => course.id === target.id)
          const selected = target.id === selectedId
          const status = record?.mec?.status ?? target.mec?.status
          const completude = record?.dados?.completude ?? target.dados?.completude
          const publica = record?.mec?.instituicao_publica ?? target.mec?.instituicao_publica
          const mecNote = record?.mec?.observacao ?? target.mec?.observacao ?? undefined

          return (
            <label key={target.id} className={`target-option${selected ? ' is-selected' : ''}`}>
              <input
                type="radio"
                name="target"
                value={target.id}
                checked={selected}
                onChange={() => onSelect(target.id)}
              />
              <span className="target-radio" aria-hidden="true" />
              <span className="target-copy">
                <span className="target-title">{target.curso}</span>
                {target.habilitacao && (
                  <span className="target-variant">{target.habilitacao}</span>
                )}
                <span className="target-meta">
                  {target.instituicao}, {degreeLabel(target.grau)}, {target.modalidade},{' '}
                  {target.duracao_meses} meses, {formatHours(target.carga_horaria_total)}
                </span>
                <span className="target-tags">
                  <span className={`tag ${mecTone(status)}`} title={mecNote}>
                    {mecLabel(status)}
                  </span>
                  {publica && <span className="tag tag--muted">instituição pública</span>}
                  <span className="tag tag--muted">{completudeLabel(completude)}</span>
                  {target.curriculo_versao && (
                    <span className="tag tag--muted">catálogo {target.curriculo_versao}</span>
                  )}
                  {record?.ingresso?.segunda_graduacao_sem_vestibular === true && (
                    <span className="tag tag--ok">2ª graduação sem vestibular</span>
                  )}
                </span>
              </span>
              <a
                className="source-link"
                href={target.fonte}
                target="_blank"
                rel="noreferrer"
                onClick={(event) => event.stopPropagation()}
              >
                fonte
              </a>
            </label>
          )
        })}
      </fieldset>
    </>
  )
}
