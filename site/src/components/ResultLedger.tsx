import type { MatchResult, Slot, SlotResult } from '../lib/types'

interface Props {
  result: MatchResult
  onDownload: () => void
}

function formatHours(hours: number): string {
  return `${new Intl.NumberFormat('pt-BR').format(Math.round(hours))}h`
}

function remainingByGroup(slots: SlotResult[]): Array<[string, SlotResult[]]> {
  const groups = new Map<string, SlotResult[]>()
  for (const item of slots) {
    const list = groups.get(item.slot.grupoNome) ?? []
    list.push(item)
    groups.set(item.slot.grupoNome, list)
  }
  return [...groups.entries()]
}

function nonWaivableByGroup(slots: Slot[]): Array<[string, Slot[]]> {
  const groups = new Map<string, Slot[]>()
  for (const slot of slots) {
    const list = groups.get(slot.grupoNome) ?? []
    list.push(slot)
    groups.set(slot.grupoNome, list)
  }
  return [...groups.entries()]
}

export function ResultLedger({ result, onDownload }: Props) {
  const matched = result.slots.filter((slot) => slot.allocations.length > 0)
  const remaining = result.slots.filter((slot) => slot.status !== 'coberto')
  const nonWaivable = result.naoAbativeis
  const nonWaivableGroups = nonWaivableByGroup(nonWaivable)
  const totalNonWaivable = nonWaivable.reduce((total, slot) => total + slot.horas, 0)

  return (
    <div className="ledger">
      <div className="ledger-intro">
        <div>
          <p className="ledger-kicker">Leitura do resultado</p>
          <p className="ledger-headline">
            {matched.length} componente(s) com match · {remaining.length} restante(s)
          </p>
        </div>
        <button type="button" className="button button--ghost" onClick={onDownload}>
          Baixar relatório JSON
        </button>
      </div>

      <div className="ledger-note">
        <p>
          Estimativa m-para-n por nome + carga horária, sem ementa. A decisão final é da
          instituição de destino.
        </p>
        <details>
          <summary>Ver premissas</summary>
          <ul>
            {result.avisos.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </details>
      </div>

      <div className="table-scroll">
        <table className="ledger-table">
          <thead>
            <tr>
              <th scope="col">No currículo alvo</th>
              <th scope="col">Vem do seu histórico</th>
              <th scope="col" className="num">Horas</th>
              <th scope="col">Confiança</th>
            </tr>
          </thead>
          <tbody>
            {matched.length === 0 && (
              <tr>
                <td colSpan={4} className="empty-cell">
                  Nenhum componente coberto com os critérios atuais. Veja o que falta abaixo.
                </td>
              </tr>
            )}
            {matched.map((slot) => {
              const optionNotes = [
                ...new Set(
                  slot.allocations
                    .map((allocation) => allocation.opcao)
                    .filter((option) => option && option !== slot.slot.nome),
                ),
              ]
              return slot.allocations.map((allocation, index) => (
                <tr key={`${slot.slot.id}-${allocation.sourceId}-${index}`} className={index > 0 ? 'is-continuation' : ''}>
                  {index === 0 && (
                    <td rowSpan={slot.allocations.length} className="target-cell">
                      <span className="target-group">{slot.slot.grupoNome}</span>
                      <span className="target-name">{slot.slot.nome}</span>
                      {slot.status === 'parcial' && <span className="tag tag--risk">parcial</span>}
                      {optionNotes.map((option) => (
                        <span className="target-option-note" key={option}>opção: {option}</span>
                      ))}
                    </td>
                  )}
                  <td className="source-cell">
                    <span className="source-code">{allocation.sourceCodigo}</span>
                    <span className="source-name">{allocation.sourceNome}</span>
                    {allocation.sourcePeriodo && (
                      <span className="source-period">{allocation.sourcePeriodo}</span>
                    )}
                  </td>
                  <td className="num">{formatHours(allocation.horas)}</td>
                  <td>
                    <span className={`tag tag--${allocation.confianca}`}>{allocation.confianca}</span>
                  </td>
                </tr>
              ))
            })}
          </tbody>
        </table>
      </div>

      <section className="remaining-section">
        <h3>O que falta</h3>
        <p className="section-note">
          Componentes abatíveis que ainda não foram cobertos — ou cobertos só em parte.
        </p>
        {remaining.length === 0 ? (
          <p className="empty-note">Todos os componentes abatíveis foram cobertos.</p>
        ) : (
          <div className="remaining-grid">
            {remainingByGroup(remaining).map(([groupName, slots]) => (
              <div className="remaining-group" key={groupName}>
                <h4>{groupName}</h4>
                <ul>
                  {slots.map((slot) => (
                    <li key={slot.slot.id}>
                      <span>{slot.slot.nome}</span>
                      <span className="remaining-hours">
                        {slot.status === 'parcial' ? 'faltam ' : ''}
                        {formatHours(slot.restante)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="nonwaivable-section">
        <h3>Não abatível na estimativa</h3>
        <p className="section-note">
          {formatHours(totalNonWaivable)} em estágio, TCC, extensão, atividades complementares
          ou projetos. A instituição pode ter regras próprias para esses componentes.
        </p>
        <details>
          <summary>Ver componentes</summary>
          <div className="remaining-grid">
            {nonWaivableGroups.map(([groupName, slots]) => (
              <div className="remaining-group" key={groupName}>
                <h4>{groupName}</h4>
                <ul>
                  {slots.map((slot) => (
                    <li key={slot.id}>
                      <span>{slot.nome}</span>
                      <span className="remaining-hours">{formatHours(slot.horas)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </details>
      </section>
    </div>
  )
}
