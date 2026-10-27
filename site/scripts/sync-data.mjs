import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const siteRoot = dirname(here)
const repoRoot = dirname(siteRoot)
const curriculumDirs = [
  join(repoRoot, 'data', 'spike', 'curriculos'),
  join(repoRoot, 'data', 'targets', 'unicamp'),
]
const targetDir = join(siteRoot, 'public', 'data')

await mkdir(targetDir, { recursive: true })

const index = []
const seen = new Set()

for (const sourceDir of curriculumDirs) {
  let files = []
  try {
    files = (await readdir(sourceDir)).filter((file) => file.endsWith('.json')).sort()
  } catch {
    continue
  }

  for (const file of files) {
    if (seen.has(file)) throw new Error(`Currículo duplicado no índice: ${file}`)
    seen.add(file)

    const curriculum = JSON.parse(await readFile(join(sourceDir, file), 'utf8'))
    index.push({
      file,
      id: curriculum.id,
      instituicao: curriculum.instituicao,
      curso: curriculum.curso,
      grau: curriculum.grau,
      modalidade: curriculum.modalidade,
      duracao_meses: curriculum.duracao_meses,
      carga_horaria_total: curriculum.carga_horaria_total,
      fonte: curriculum.fonte,
      habilitacao: curriculum.habilitacao ?? null,
      curriculo_versao: curriculum.curriculo_versao ?? null,
    })
    await cp(join(sourceDir, file), join(targetDir, file))
  }
}

index.sort(
  (a, b) =>
    (a.duracao_meses ?? 0) - (b.duracao_meses ?? 0) ||
    a.curso.localeCompare(b.curso, 'pt-BR'),
)

await writeFile(
  join(targetDir, 'index.json'),
  `${JSON.stringify({ curriculos: index }, null, 2)}\n`,
)
await cp(join(repoRoot, 'data', 'spike', 'cursos.json'), join(targetDir, 'cursos.json'))
await cp(
  join(repoRoot, 'data', 'ontology', 'unicamp_2026_regras.json'),
  join(targetDir, 'regras.json'),
)

console.log(`Dados públicos sincronizados em ${targetDir}`)
