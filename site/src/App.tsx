import { useEffect, useMemo, useState } from 'react'
import { ResultLedger } from './components/ResultLedger'
import { SummaryPanel } from './components/SummaryPanel'
import { TargetPicker } from './components/TargetPicker'
import { TranscriptPanel } from './components/TranscriptPanel'
import { DEMO_TRANSCRIPT } from './data/demo'
import { matchCurriculum } from './lib/match'
import { parseTranscriptFile } from './lib/transcript'
import type { CourseRecord, CoursesFile, Curriculum, Transcript } from './lib/types'

function dataUrl(file: string): string {
  return `${import.meta.env.BASE_URL}data/${file}`
}

async function fetchJson<T>(file: string): Promise<T> {
  const response = await fetch(dataUrl(file))
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${file} (HTTP ${response.status}).`)
  }
  return response.json() as Promise<T>
}

export default function App() {
  const [targets, setTargets] = useState<Curriculum[]>([])
  const [courses, setCourses] = useState<CourseRecord[]>([])
  const [selectedId, setSelectedId] = useState('uninter-ads')
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [transcriptLabel, setTranscriptLabel] = useState('Histórico fictício')
  const [isDemo, setIsDemo] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [ads, software, courseFile] = await Promise.all([
          fetchJson<Curriculum>('uninter_ads.json'),
          fetchJson<Curriculum>('uninter_eng_software.json'),
          fetchJson<CoursesFile>('cursos.json'),
        ])
        if (cancelled) return
        setTargets([ads, software])
        setCourses(courseFile.cursos)
        setTranscript(DEMO_TRANSCRIPT)
        setTranscriptLabel('Histórico fictício')
        setIsDemo(true)
        setLoading(false)
      } catch (loadFailure) {
        if (cancelled) return
        setLoadError(
          loadFailure instanceof Error
            ? loadFailure.message
            : 'Não foi possível carregar os dados públicos.',
        )
        setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedTarget = targets.find((target) => target.id === selectedId) ?? targets[0] ?? null
  const result = useMemo(
    () => (selectedTarget && transcript ? matchCurriculum(selectedTarget, transcript) : null),
    [selectedTarget, transcript],
  )

  async function handleFile(file: File) {
    setError(null)
    try {
      const parsed = await parseTranscriptFile(file)
      setTranscript(parsed)
      setTranscriptLabel('Histórico importado')
      setIsDemo(false)
    } catch (fileError) {
      setError(
        fileError instanceof Error ? fileError.message : 'Não foi possível ler o arquivo.',
      )
    }
  }

  function handleDemo() {
    setTranscript(DEMO_TRANSCRIPT)
    setTranscriptLabel('Histórico fictício')
    setIsDemo(true)
    setError(null)
  }

  function handleDownload() {
    if (!selectedTarget || !transcript || !result) return
    const payload = {
      gerado_em: new Date().toISOString(),
      alvo: selectedTarget,
      historico: transcript,
      resultado: result,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `equivale-${selectedTarget.id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="page">
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Equivale, início">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
          </span>
          <span className="brand-word">Equivale</span>
        </a>
        <div className="header-meta">
          <span className="tag tag--muted">protótipo</span>
          <a href="#resultado">ver resultado</a>
        </div>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <h1>Quanto do seu histórico já vale em outro curso?</h1>
            <p className="hero-sub">
              Compare seu histórico com a grade de outro curso e veja o que pode ser abatido,
              o que falta e uma estimativa de tempo. O arquivo fica no seu navegador.
            </p>
          </div>
          <div className="hero-aside">
            <div className="privacy-note">
              <span className="privacy-dot" aria-hidden="true" />
              <p>
                <strong>Processamento local.</strong> Nenhum histórico é enviado. O site só
                baixa os dados públicos das grades.
              </p>
            </div>
            <p className="hero-footnote">
              Nesta etapa, importe JSON/CSV. O adaptador PDF entra na próxima.
            </p>
          </div>
        </section>

        {loadError ? (
          <div className="load-error" role="alert">
            <p>{loadError}</p>
            <button type="button" className="button button--ghost" onClick={() => window.location.reload()}>
              Tentar de novo
            </button>
          </div>
        ) : loading ? (
          <p className="loading">Carregando dados públicos…</p>
        ) : (
          <>
            <div className="workbench">
              <div className="workbench-main">
                <section className="step" aria-labelledby="step-target">
                  <div className="step-head">
                    <span className="step-num">01</span>
                    <h2 id="step-target">Escolha o curso alvo</h2>
                  </div>
                  <TargetPicker
                    targets={targets}
                    courses={courses}
                    selectedId={selectedTarget?.id ?? ''}
                    onSelect={setSelectedId}
                  />
                  <p className="section-note">
                    Status e grade vêm das fontes públicas listadas. Confirme o reconhecimento
                    do curso no e-MEC antes de qualquer decisão.
                  </p>
                </section>

                <section className="step" aria-labelledby="step-transcript">
                  <div className="step-head">
                    <span className="step-num">02</span>
                    <h2 id="step-transcript">Traga seu histórico</h2>
                  </div>
                  <TranscriptPanel
                    transcript={transcript}
                    label={transcriptLabel}
                    isDemo={isDemo}
                    error={error}
                    onFile={(file) => void handleFile(file)}
                    onDemo={handleDemo}
                  />
                </section>
              </div>

              <SummaryPanel result={result} target={selectedTarget} />
            </div>

            <section className="step result-step" id="resultado" aria-labelledby="step-result">
              <div className="step-head">
                <span className="step-num">03</span>
                <h2 id="step-result">Leia o resultado</h2>
              </div>
              {result ? (
                <ResultLedger result={result} onDownload={handleDownload} />
              ) : (
                <p className="empty-note">Importe um histórico para ver o resultado.</p>
              )}
            </section>
          </>
        )}
      </main>

      <footer className="site-footer">
        <div>
          <p>
            <strong>Equivale</strong> é um protótipo de comparador de currículos.
          </p>
          <p>
            Dados públicos: UNINTER ADS e Engenharia de Software. Fontes nas páginas dos
            cursos.
          </p>
        </div>
        <div>
          <p>Sem backend. Sem analytics. Sem upload de histórico.</p>
          <p>Estimativa, não decisão oficial de equivalência.</p>
        </div>
      </footer>
    </div>
  )
}
