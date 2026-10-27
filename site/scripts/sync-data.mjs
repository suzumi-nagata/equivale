import { cp, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const siteRoot = dirname(here)
const repoRoot = dirname(siteRoot)
const sourceDir = join(repoRoot, 'data', 'spike', 'curriculos')
const targetDir = join(siteRoot, 'public', 'data')

await mkdir(targetDir, { recursive: true })

const files = (await readdir(sourceDir)).filter((file) => file.endsWith('.json')).sort()
const index = []

for (const file of files) {
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
  })
  await cp(join(sourceDir, file), join(targetDir, file))
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

console.log(`Dados públicos sincronizados em ${targetDir}`)
