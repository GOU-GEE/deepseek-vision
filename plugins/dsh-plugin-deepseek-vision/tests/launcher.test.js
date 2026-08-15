import assert from 'node:assert/strict'
import { writeFileSync } from 'node:fs'
import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { findPython, loadDshCredential, parsePythonVersion, supportsPython } from '../launcher.js'

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
