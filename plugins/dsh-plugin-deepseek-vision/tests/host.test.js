import assert from 'node:assert/strict'
import { mkdtemp, readFile, stat } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { detectImageExtension, ensureLauncherShim, isSameOrigin, launcherShimPath, storePastedImage } from '../index.js'

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
