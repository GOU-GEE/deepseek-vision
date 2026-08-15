import assert from 'node:assert/strict'
import { mkdtemp, readFile, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { detectImageExtension, ensureLauncherShim, isSameOrigin, launcherShimPath, loadVisionSettings, saveVisionSettings, settingsPath, storePastedImage, testVisionConnection, validateSettings } from '../index.js'

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3])

test('detects supported image magic bytes', () => {
  assert.equal(detectImageExtension(PNG), '.png')
  assert.equal(detectImageExtension(Buffer.from([0xff, 0xd8, 0xff, 0x00])), '.jpg')
  assert.equal(detectImageExtension(Buffer.from('not an image')), undefined)
})

test('stores pasted images privately with a safe generated name', async () => {
  const root = await mkdtemp(join(tmpdir(), 'deepseek-vision-test-'))
  const path = await storePastedImage(PNG, root)
  assert.match(path, /deepseek-vision-dsh-.*\/paste\.png$/)
  assert.deepEqual(await readFile(path), PNG)
  if (process.platform !== 'win32') assert.equal((await stat(path)).mode & 0o777, 0o600)
})

test('rejects content that only claims to be an image', async () => {
  await assert.rejects(() => storePastedImage(Buffer.from('<html>oops</html>')), /不是受支持/)
})

test('creates a launcher shim inside DSH_HOME without registry lookup', async () => {
  const home = await mkdtemp(join(tmpdir(), 'deepseek-vision-dsh-home-'))
  const environment = { DSH_HOME: home }
  const path = ensureLauncherShim(environment)
  assert.equal(path, launcherShimPath(environment))
  assert.match(await readFile(path, 'utf8'), /launcher\.js/)
  if (process.platform !== 'win32') assert.equal((await stat(path)).mode & 0o777, 0o700)
})

test('rejects browser requests from a different origin', () => {
  assert.equal(isSameOrigin({ headers: { host: '127.0.0.1:3080' } }), true)
  assert.equal(isSameOrigin({ headers: { host: '127.0.0.1:3080', origin: 'http://127.0.0.1:3080' } }), true)
  assert.equal(isSameOrigin({ headers: { host: '127.0.0.1:3080', origin: 'https://evil.example' } }), false)
})

test('stores non-secret visual settings privately and reloads them', async () => {
  const home = await mkdtemp(join(tmpdir(), 'deepseek-vision-settings-'))
  const environment = { DSH_HOME: home }
  const settings = saveVisionSettings({
    provider: 'siliconflow',
    model: 'Qwen/Qwen2.5-VL-7B-Instruct',
    baseUrl: 'https://api.siliconflow.cn/v1/',
    apiKey: 'must-not-be-written',
  }, environment)
  assert.equal(settings.baseUrl, 'https://api.siliconflow.cn/v1')
  assert.deepEqual(loadVisionSettings(environment), settings)
  assert.doesNotMatch(await readFile(settingsPath(environment), 'utf8'), /must-not-be-written/)
  if (process.platform !== 'win32') assert.equal((await stat(settingsPath(environment))).mode & 0o777, 0o600)
})

test('visual settings reject unsafe base URLs and embedded credentials', () => {
  assert.throws(() => validateSettings({ provider: 'zhipu', model: 'm', baseUrl: 'http://example.com/v1' }), /HTTPS/)
  assert.throws(() => validateSettings({ provider: 'custom', model: 'm', baseUrl: 'https://user:pass@example.com/v1' }), /凭据/)
  assert.equal(validateSettings({ provider: 'custom', model: 'm', baseUrl: 'http://127.0.0.1:8000/v1' }).baseUrl, 'http://127.0.0.1:8000/v1')
})

test('connection test sends a minimal image request and reports the model', async () => {
  let request
  const result = await testVisionConnection(
    { model: 'glm-4.6v-flash', baseUrl: 'https://vision.example/v1' },
    'private-test-key',
    async (url, options) => {
      request = { url, options, body: JSON.parse(options.body) }
      return { ok: true, json: async () => ({ model: 'glm-4.6v-flash', choices: [{}] }) }
    },
  )
  assert.deepEqual(result, { ok: true, model: 'glm-4.6v-flash' })
  assert.equal(request.url, 'https://vision.example/v1/chat/completions')
  assert.equal(request.options.headers.authorization, 'Bearer private-test-key')
  assert.equal(request.body.max_tokens, 8)
  assert.match(request.body.messages[0].content[1].image_url.url, /^data:image\/png;base64,/)
})

test('connection test maps provider failures without exposing the key', async () => {
  await assert.rejects(
    () => testVisionConnection(
      { model: 'glm-4.6v-flash', baseUrl: 'https://vision.example/v1' },
      'private-test-key',
      async () => ({ ok: false, status: 429 }),
    ),
    error => {
      assert.match(error.message, /限流.*HTTP 429/)
      assert.doesNotMatch(error.message, /private-test-key/)
      return true
    },
  )
})
