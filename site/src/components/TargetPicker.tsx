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
  return (
    <fieldset className="target-picker">
      <legend className="sr-only">Curso alvo</legend>
      {targets.map((target) => {
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
  )
}
