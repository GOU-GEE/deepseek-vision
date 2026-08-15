import { mkdirSync, writeFileSync } from 'node:fs'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { dirname, join } from 'node:path'

export const name = 'deepseek-vision-host'
export const inject = []

const MAX_PASTE_BYTES = 20 * 1024 * 1024
const PASTE_TTL_MS = 60 * 60 * 1000
const ROUTE = '/_dsh/deepseek-vision/paste'

const IMAGE_SIGNATURES = [
  ['.png', bytes => bytes.length >= 8 && bytes.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))],
  ['.jpg', bytes => bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff],
  ['.gif', bytes => bytes.length >= 6 && ['GIF87a', 'GIF89a'].includes(bytes.toString('ascii', 0, 6))],
  ['.webp', bytes => bytes.length >= 12 && bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP'],
]

export function detectImageExtension(bytes) {
  return IMAGE_SIGNATURES.find(([, matches]) => matches(bytes))?.[0]
}

async function readBounded(req, limit = MAX_PASTE_BYTES) {
  const chunks = []
  let total = 0
  for await (const chunk of req) {
    total += chunk.length
    if (total > limit) throw new RangeError(`图片超过 ${limit} 字节限制`)
    chunks.push(chunk)
  }
  return Buffer.concat(chunks)
}

export async function storePastedImage(bytes, root = tmpdir()) {
  const extension = detectImageExtension(bytes)
  if (!extension) throw new TypeError('不是受支持的 PNG/JPEG/GIF/WebP 图片')
  const directory = await mkdtemp(join(root, 'deepseek-vision-dsh-'))
  const path = join(directory, `paste${extension}`)
  await writeFile(path, bytes, { mode: 0o600 })
  const cleanup = setTimeout(() => void rm(directory, { recursive: true, force: true }), PASTE_TTL_MS)
  cleanup.unref?.()
  return path
}

export function isSameOrigin(req) {
  const origin = req.headers?.origin
  if (!origin) return true
  try {
    return new URL(origin).host === req.headers?.host
  } catch {
    return false
  }
}

export function launcherShimPath(environment = process.env) {
  const home = environment.DSH_HOME || join(homedir(), '.dsh')
  return join(home, 'cache', 'deepseek-vision-mcp', 'launcher.mjs')
}

export function ensureLauncherShim(environment = process.env) {
  const target = launcherShimPath(environment)
  mkdirSync(dirname(target), { recursive: true })
  const launcher = new URL('./launcher.js', import.meta.url).href
  writeFileSync(target, `import { main } from ${JSON.stringify(launcher)}\nmain()\n`, { mode: 0o700 })
  return target
}

function json(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
  res.end(JSON.stringify(body))
}

export function registerPasteRoute(ctx) {
  return ctx.webServer.register({
    name: 'deepseek-vision-paste',
    kind: 'exact',
    path: ROUTE,
    handler: async (req, res) => {
      if (req.method !== 'POST') return json(res, 405, { error: 'method-not-allowed' })
      if (!isSameOrigin(req)) return json(res, 403, { error: 'cross-origin-request-denied' })
      try {
        const path = await storePastedImage(await readBounded(req))
        return json(res, 200, { path })
      } catch (error) {
        const status = error instanceof RangeError ? 413 : error instanceof TypeError ? 400 : 500
        return json(res, status, { error: error instanceof Error ? error.message : String(error) })
      }
    },
  })
}

export function apply(ctx) {
  ensureLauncherShim()
  // webServer is unavailable in the headless profile. Optional scoped
  // injection keeps the host plugin usable there without blocking startup.
  if (typeof ctx.inject === 'function') {
    ctx.inject(['webServer'], scope => registerPasteRoute(scope))
  }
}
