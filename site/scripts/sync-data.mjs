import { cp, mkdir, readdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const siteRoot = dirname(here)
const repoRoot = dirname(siteRoot)
const sourceDir = join(repoRoot, 'data', 'spike', 'curriculos')
const targetDir = join(siteRoot, 'public', 'data')

await mkdir(targetDir, { recursive: true })

for (const file of await readdir(sourceDir)) {
  if (file.endsWith('.json')) {
    await cp(join(sourceDir, file), join(targetDir, file))
  }
}

await cp(join(repoRoot, 'data', 'spike', 'cursos.json'), join(targetDir, 'cursos.json'))

console.log(`Dados públicos sincronizados em ${targetDir}`)
