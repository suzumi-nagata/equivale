import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const siteRoot = dirname(here)
const repoRoot = dirname(siteRoot)
const curriculumDirs = [
  join(repoRoot, 'data', 'spike', 'curriculos'),
  join(repoRoot, 'data', 'targets', 'unicamp'),
  join(repoRoot, 'data', 'targets', 'usp'),
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

const ruleFiles = ['unicamp_2026_regras.json', 'usp_2026_regras.json']
const regras = []
for (const file of ruleFiles) {
  try {
    const payload = JSON.parse(
      await readFile(join(repoRoot, 'data', 'ontology', file), 'utf8'),
    )
    if (Array.isArray(payload.regras)) regras.push(...payload.regras)
  } catch {
    // A fonte pode não existir em um checkout parcial.
  }
}
await writeFile(
  join(targetDir, 'regras.json'),
  `${JSON.stringify({ regras }, null, 2)}\n`,
)

try {
  await cp(
    join(repoRoot, 'data', 'embeddings', 'cursos.json'),
    join(targetDir, 'embeddings.json'),
  )
} catch {
  // O site continua funcionando com nome + regras se o índice não existir.
}

console.log(`Dados públicos sincronizados em ${targetDir}`)
