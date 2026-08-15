import { chmodSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'

export const name = 'deepseek-vision-host'
export const inject = []

const MAX_PASTE_BYTES = 20 * 1024 * 1024
const PASTE_TTL_MS = 60 * 60 * 1000
const ROUTE = '/_dsh/deepseek-vision/paste'
const SETTINGS_ROUTE = '/_dsh/deepseek-vision/settings'
const MAX_SETTINGS_BYTES = 32 * 1024
const DEFAULT_SETTINGS = Object.freeze({
  provider: 'zhipu',
  model: 'glm-4.6v-flash',
  baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
})
const PROVIDERS = new Set(['zhipu', 'siliconflow', 'dashscope', 'custom'])
const TEST_IMAGE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='

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

export function settingsPath(environment = process.env) {
  const home = environment.DSH_HOME ? resolve(environment.DSH_HOME) : join(homedir(), '.dsh')
  return join(home, 'deepseek-vision.json')
}

export function validateSettings(value) {
  if (!value || typeof value !== 'object') throw new TypeError('配置必须是对象')
  const provider = String(value.provider ?? '').trim()
  const model = String(value.model ?? '').trim()
  const baseUrl = String(value.baseUrl ?? '').trim().replace(/\/+$/, '')
  if (!PROVIDERS.has(provider)) throw new TypeError('不支持的视觉服务商')
  if (!model || model.length > 200) throw new TypeError('模型名称不能为空或过长')
  let parsed
  try {
    parsed = new URL(baseUrl)
  } catch {
    throw new TypeError('Base URL 格式无效')
  }
  const loopback = ['127.0.0.1', '::1', 'localhost'].includes(parsed.hostname)
  if (parsed.username || parsed.password || (parsed.protocol !== 'https:' && !(loopback && parsed.protocol === 'http:'))) {
    throw new TypeError('Base URL 必须使用 HTTPS（本机回环地址可使用 HTTP）且不能包含凭据')
  }
  return { provider, model, baseUrl }
}

export function loadVisionSettings(environment = process.env) {
  const path = settingsPath(environment)
  if (!existsSync(path)) return { ...DEFAULT_SETTINGS }
  try {
    return validateSettings(JSON.parse(readFileSync(path, 'utf8')))
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveVisionSettings(value, environment = process.env) {
  const validated = validateSettings(value)
  const path = settingsPath(environment)
  mkdirSync(dirname(path), { recursive: true })
  const temporary = `${path}.${process.pid}.tmp`
  writeFileSync(temporary, `${JSON.stringify(validated, null, 2)}\n`, { mode: 0o600 })
  renameSync(temporary, path)
  chmodSync(path, 0o600)
  return validated
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

async function readJson(req) {
  const bytes = await readBounded(req, MAX_SETTINGS_BYTES)
  try {
    return JSON.parse(bytes.toString('utf8'))
  } catch {
    throw new TypeError('请求 JSON 格式无效')
  }
}

async function credentialView(credentials) {
  const view = await credentials.describe('VISION_API_KEY')
  return {
    configured: view.configured === true,
    writable: view.writable !== false,
    source: view.source,
  }
}

function publicConnectionError(error) {
  if (error?.name === 'AbortError') return '连接超时，请检查网络或 Base URL'
  return error instanceof Error ? error.message.replace(/sk-[A-Za-z0-9._-]+/g, '[REDACTED]') : '连接失败'
}

export async function testVisionConnection(settings, key, fetchImpl = fetch) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 20_000)
  timer.unref?.()
  try {
    const response = await fetchImpl(`${settings.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model: settings.model,
        messages: [{ role: 'user', content: [
          { type: 'text', text: '这是一张连接测试图片。只回复 OK。' },
          { type: 'image_url', image_url: { url: TEST_IMAGE } },
        ] }],
        max_tokens: 8,
        temperature: 0,
      }),
      signal: controller.signal,
    })
    if (!response.ok) {
      const hints = {
        401: 'API Key 无效或已过期',
        403: 'API Key 无权访问该模型',
        404: '模型或 Base URL 不存在',
        429: '服务商限流，请稍后重试',
      }
      throw new Error(`${hints[response.status] ?? '视觉服务请求失败'}（HTTP ${response.status}）`)
    }
    const payload = await response.json()
    if (!payload?.choices?.[0]) throw new Error('服务已响应，但返回格式不是 OpenAI 兼容格式')
    return { ok: true, model: payload.model || settings.model }
  } finally {
    clearTimeout(timer)
  }
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

export function registerSettingsRoute(ctx) {
  return ctx.webServer.register({
    name: 'deepseek-vision-settings',
    kind: 'exact',
    path: SETTINGS_ROUTE,
    handler: async (req, res) => {
      if (req.method === 'GET') {
        try {
          return json(res, 200, {
            settings: loadVisionSettings(),
            credential: await credentialView(ctx.credentials),
          })
        } catch {
          return json(res, 503, { error: '视觉配置暂时不可用' })
        }
      }
      if (req.method !== 'POST') return json(res, 405, { error: 'method-not-allowed' })
      if (!isSameOrigin(req)) return json(res, 403, { error: 'cross-origin-request-denied' })
      try {
        const body = await readJson(req)
        if (body.action === 'save') {
          const settings = saveVisionSettings(body.settings)
          const key = typeof body.apiKey === 'string' ? body.apiKey.trim() : ''
          if (key) await ctx.credentials.set('VISION_API_KEY', key)
          return json(res, 200, {
            settings,
            credential: await credentialView(ctx.credentials),
            restartRequired: true,
          })
        }
        if (body.action === 'unset-key') {
          await ctx.credentials.unset('VISION_API_KEY')
          return json(res, 200, { credential: await credentialView(ctx.credentials) })
        }
        if (body.action === 'test') {
          const settings = validateSettings(body.settings)
          const supplied = typeof body.apiKey === 'string' ? body.apiKey.trim() : ''
          const resolved = supplied || (await ctx.credentials.resolve('VISION_API_KEY'))?.value?.trim()
          if (!resolved) throw new TypeError('请先填写视觉 API Key')
          return json(res, 200, await testVisionConnection(settings, resolved))
        }
        throw new TypeError('未知操作')
      } catch (error) {
        const status = error instanceof TypeError ? 400 : 502
        return json(res, status, { error: publicConnectionError(error) })
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
    ctx.inject(['webServer', 'credentials'], scope => registerSettingsRoute(scope))
  }
}
