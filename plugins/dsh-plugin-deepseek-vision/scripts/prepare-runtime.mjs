import { copyFileSync, mkdirSync, readdirSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const pluginRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(pluginRoot, '..', '..')
const runtimeDir = join(pluginRoot, 'runtime')
const temporaryDist = join(pluginRoot, '.runtime-dist')

rmSync(runtimeDir, { recursive: true, force: true })
rmSync(temporaryDist, { recursive: true, force: true })
mkdirSync(runtimeDir, { recursive: true })

const python = process.env.VISION_BUILD_PYTHON || process.env.PYTHON || 'python3'
const result = spawnSync(python, ['-m', 'build', '--wheel', '--outdir', temporaryDist, repositoryRoot], {
  cwd: repositoryRoot,
  stdio: 'inherit',
  windowsHide: true,
})
if (result.status !== 0) {
  throw new Error(`building embedded Python wheel failed with exit ${result.status}`)
}

const wheels = readdirSync(temporaryDist).filter(name => name.endsWith('.whl'))
if (wheels.length !== 1) throw new Error(`expected exactly one wheel, found ${wheels.length}`)
copyFileSync(join(temporaryDist, wheels[0]), join(runtimeDir, wheels[0]))
copyFileSync(join(repositoryRoot, 'LICENSE'), join(pluginRoot, 'LICENSE'))
rmSync(temporaryDist, { recursive: true, force: true })
console.log(`prepared ${wheels[0]}`)
