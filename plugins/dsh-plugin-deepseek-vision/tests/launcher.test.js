import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { buildChildEnvironment, findPython, loadDshCredential, parsePythonVersion, supportsPython, uvAsset } from '../launcher.js'

test('parses and gates Python versions', () => {
  assert.deepEqual(parsePythonVersion('Python 3.12.8'), [3, 12, 8])
  assert.equal(supportsPython([3, 10, 0]), true)
  assert.equal(supportsPython([3, 9, 20]), false)
})

test('prefers the first supported interpreter', () => {
  const calls = []
  const found = findPython((command, args) => {
    calls.push([command, ...args])
    return command === 'python3'
      ? { status: 0, stdout: 'Python 3.12.8', stderr: '' }
      : { status: 1, stdout: '', stderr: '' }
  })
  assert.deepEqual(found, ['python3'])
  assert.ok(calls.length >= 1)
})

test('reads VISION_API_KEY from DSH credential storage', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-credential-test-'))
  writeFileSync(join(home, '.credentials.yaml'), 'VISION_API_KEY: "secret-from-dsh"\n')
  assert.equal(loadDshCredential({ DSH_HOME: home }), 'secret-from-dsh')
  assert.equal(loadDshCredential({ DSH_HOME: home, VISION_API_KEY: 'environment-wins' }), 'environment-wins')
})

test('credential parser errors never echo a secret source line', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-credential-test-'))
  writeFileSync(join(home, '.credentials.yaml'), 'VISION_API_KEY: [super-secret\n')
  assert.throws(() => loadDshCredential({ DSH_HOME: home }), error => {
    assert.doesNotMatch(error.message, /super-secret/)
    return true
  })
})

test('desktop settings configure the managed MCP while environment still wins', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-vision-launcher-settings-'))
  writeFileSync(join(home, 'deepseek-vision.json'), JSON.stringify({
    model: 'saved-model',
    baseUrl: 'https://saved.example/v1',
  }))
  const saved = buildChildEnvironment({ DSH_HOME: home, VISION_MODEL: '', VISION_BASE_URL: '' })
  assert.equal(saved.VISION_MODEL, 'saved-model')
  assert.equal(saved.VISION_BASE_URL, 'https://saved.example/v1')
  const explicit = buildChildEnvironment({
    DSH_HOME: home,
    VISION_MODEL: 'environment-model',
    VISION_BASE_URL: 'https://environment.example/v1',
  })
  assert.equal(explicit.VISION_MODEL, 'environment-model')
  assert.equal(explicit.VISION_BASE_URL, 'https://environment.example/v1')
})

test('desktop fallback settings become a non-secret provider route', async () => {
  const home = await mkdtemp(join(tmpdir(), 'dsh-vision-launcher-fallback-'))
  writeFileSync(join(home, 'deepseek-vision.json'), JSON.stringify({
    provider: 'zhipu',
    model: 'glm-4.6v-flash',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    fallback: {
      enabled: true,
      provider: 'siliconflow',
      model: 'backup-vl',
      baseUrl: 'https://api.siliconflow.cn/v1',
    },
  }))
  const child = buildChildEnvironment({ DSH_HOME: home })
  assert.equal(child.VISION_SERVICE_ID, 'zhipu')
  assert.deepEqual(JSON.parse(child.VISION_FALLBACKS_JSON), [{
    id: 'siliconflow',
    model: 'backup-vl',
    base_url: 'https://api.siliconflow.cn/v1',
    api_key_env: 'VISION_FALLBACK_API_KEY',
  }])
  assert.doesNotMatch(child.VISION_FALLBACKS_JSON, /fallback-secret-value/)
})

test('uv bootstrap assets are pinned by platform and sha256', () => {
  const asset = uvAsset('darwin', 'arm64')
  assert.equal(asset.name, 'uv-aarch64-apple-darwin.tar.gz')
  assert.match(asset.sha256, /^[a-f0-9]{64}$/)
  assert.throws(() => uvAsset('plan9', 'mips'), /暂不支持/)
})
