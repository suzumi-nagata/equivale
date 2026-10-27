import { useState } from 'react'
import type { Transcript } from '../lib/types'
import { approvedDisciplineCount, approvedHours, isApproved } from '../lib/transcript'

interface Props {
  transcript: Transcript | null
  label: string
  isDemo: boolean
  error: string | null
  onFile: (file: File) => void
  onDemo: () => void
}

function formatHours(hours: number): string {
  return `${new Intl.NumberFormat('pt-BR').format(hours)}h`
}

function statusLabel(status: string): string {
  if (status === 'aprovado') return 'aprovado'
  if (status === 'aprovado_proficiencia') return 'proficiência'
  if (status === 'suficiente') return 'suficiente'
  if (status === 'desistencia') return 'desistência'
  if (status === 'reprovado') return 'reprovado'
  return status
}

export function TranscriptPanel({ transcript, label, isDemo, error, onFile, onDemo }: Props) {
  const [dragging, setDragging] = useState(false)
  const ignored = transcript
    ? transcript.disciplinas.length - approvedDisciplineCount(transcript)
    : 0

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (file) onFile(file)
  }

  return (
    <div className="import-panel">
      <div
        className={`dropzone${dragging ? ' is-dragging' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          handleFiles(event.dataTransfer.files)
        }}
      >
        <p className="dropzone-title">Solte um JSON ou CSV aqui</p>
        <p className="dropzone-hint">O arquivo é lido no navegador. Nada é enviado.</p>
        <div className="dropzone-actions">
          <label className="button button--primary" htmlFor="transcript-file">
            Escolher arquivo
          </label>
          <input
            id="transcript-file"
            className="visually-hidden"
            type="file"
            accept=".json,.csv,application/json,text/csv"
            onChange={(event) => {
              handleFiles(event.currentTarget.files)
              event.currentTarget.value = ''
            }}
          />
          <button type="button" className="button button--ghost" onClick={onDemo}>
            Usar demonstração
          </button>
        </div>
        <p className="dropzone-hint">CSV: cabeçalho <code>codigo,nome,horas,situacao,periodo</code>.</p>
      </div>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {transcript && (
        <div className="transcript-preview">
          <div className="transcript-head">
            <div>
              <p className="transcript-label">{label}</p>
              <p className="transcript-summary">
                {approvedDisciplineCount(transcript)} disciplinas aprovadas ·{' '}
                {formatHours(approvedHours(transcript))}
                {ignored > 0 ? ` · ${ignored} registro(s) ignorado(s)` : ''}
              </p>
            </div>
            <span className="tag tag--muted">local</span>
          </div>

          {isDemo && (
            <p className="demo-note">
              Histórico fictício para demonstrar o fluxo. Nenhum dado real. Importe o seu
              arquivo acima para ver o seu resultado.
            </p>
          )}

          <div className="table-scroll transcript-scroll">
            <table className="transcript-table">
              <thead>
                <tr>
                  <th scope="col">Código</th>
                  <th scope="col">Disciplina</th>
                  <th scope="col" className="num">CH</th>
                  <th scope="col">Situação</th>
                </tr>
              </thead>
              <tbody>
                {transcript.disciplinas.map((discipline, index) => (
                  <tr
                    key={`${discipline.codigo ?? discipline.nome}-${index}`}
                    className={isApproved(discipline.situacao) ? '' : 'is-muted'}
                  >
                    <td className="code">{discipline.codigo ?? '—'}</td>
                    <td>{discipline.nome}</td>
                    <td className="num">{discipline.horas ? formatHours(discipline.horas) : '—'}</td>
                    <td>{statusLabel(discipline.situacao)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <details className="howto">
        <summary>Como gerar o JSON do PDF</summary>
        <p>
          O adaptador PDF no navegador ainda não está pronto. Rode o parser local e importe o
          JSON gerado:
        </p>
        <pre>
          <code>python3 -I prototype/parse_transcripts.py HISTORICO.pdf --out-dir /tmp/transcript-parser</code>
        </pre>
        <p>
          O PDF e o JSON ficam na sua máquina. O site não recebe nenhum dos dois.
        </p>
      </details>
    </div>
  )
}
