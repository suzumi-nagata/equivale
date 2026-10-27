import type { Curriculum, MatchResult } from '../lib/types'

interface Props {
  result: MatchResult | null
  target: Curriculum | null
}

function number(value: number): string {
  return new Intl.NumberFormat('pt-BR').format(Math.round(value))
}

function score(value: number): string {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function SummaryPanel({ result, target }: Props) {
  if (!result || !target) {
    return (
      <aside className="summary-panel" aria-live="polite">
        <p className="panel-kicker">Resumo</p>
        <p className="summary-empty">Importe um histórico para ver o resumo.</p>
      </aside>
    )
  }

  const { summary } = result
  const total = summary.horasAbatidas + summary.horasRestantesAbativeis + summary.horasNaoAbativeis
  const covered = total ? (summary.horasAbatidas / total) * 100 : 0
  const remaining = total ? (summary.horasRestantesAbativeis / total) * 100 : 0
  const nonWaivable = total ? (summary.horasNaoAbativeis / total) * 100 : 0
  const remainingDisciplines = summary.slotsAbertos + summary.slotsParciais

  return (
    <aside className="summary-panel" aria-live="polite">
      <p className="panel-kicker">Resumo</p>
      <div className="metric-hero">
        <span className="metric-value">{number(summary.horasAbatidas)}h</span>
        <span className="metric-label">abatidas de {number(summary.horasAbativeis)}h abatíveis</span>
      </div>

      <div
        className="coverage-bar"
        role="img"
        aria-label={`${Math.round(covered)}% abatido, ${Math.round(remaining)}% restante abatível e ${Math.round(nonWaivable)}% não abatível`}
      >
        <span className="coverage-segment coverage-segment--covered" style={{ width: `${covered}%` }} />
        <span className="coverage-segment coverage-segment--remaining" style={{ width: `${remaining}%` }} />
        <span className="coverage-segment coverage-segment--fixed" style={{ width: `${nonWaivable}%` }} />
      </div>
      <ul className="coverage-legend">
        <li><span className="legend-dot legend-dot--covered" /> abatido</li>
        <li><span className="legend-dot legend-dot--remaining" /> restante abatível</li>
        <li><span className="legend-dot legend-dot--fixed" /> não abatível</li>
      </ul>

      <dl className="metric-list">
        <div>
          <dt>Cobertura do abatível</dt>
          <dd>{Math.round(summary.coberturaAbativel * 100)}%</dd>
        </div>
        <div>
          <dt>Disciplinas restantes</dt>
          <dd>
            {remainingDisciplines}
            {summary.slotsParciais > 0 ? ` (${summary.slotsParciais} parcial(is))` : ''}
          </dd>
        </div>
        <div>
          <dt>Semestres restantes</dt>
          <dd>
            {summary.semestresRestantes} <span className="metric-sub">de {summary.semestresTotais}</span>
          </dd>
        </div>
        <div>
          <dt>Score médio (0–1)</dt>
          <dd>{score(summary.confiancaMedia)}</dd>
        </div>
      </dl>

      <p className="summary-footnote">
        Estimativa bruta por nome + carga horária. Não considera pré-requisitos, oferta,
        teto de aproveitamento ou optativa livre. O score médio é uma heurística, não uma
        probabilidade de aceite.
      </p>
      <p className="summary-target">
        Alvo: {target.instituicao}, {target.curso}
      </p>
    </aside>
  )
}
