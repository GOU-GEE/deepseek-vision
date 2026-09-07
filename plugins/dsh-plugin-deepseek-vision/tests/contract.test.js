import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const root = new URL('../', import.meta.url)
const manifest = JSON.parse(readFileSync(new URL('package.json', root), 'utf8'))
const patch = readFileSync(new URL('cordis.patch.yml', root), 'utf8')
const bridge = readFileSync(new URL('mcp.js', root), 'utf8')

test('declares the current DSH compatibility window exactly', () => {
  assert.equal(manifest.version, '0.4.2')
  assert.equal(manifest.dsh.compatibility.node, manifest.engines.node)
  assert.deepEqual(manifest.dsh.compatibility.profiles, ['web'])
  assert.deepEqual(manifest.dsh.compatibility.dshReleases, {
    '0.1.2-alpha.5': 'compatible',
    '0.1.2-rc.1': 'compatible',
    '0.1.3-alpha.1': 'compatible',
  })
})

test('bundle owns its entry names and delegates through its exported bridge', () => {
  assert.equal(manifest.exports['./mcp'], './mcp.js')
  assert.ok(manifest.files.includes('mcp.js'))
  assert.match(patch, /^\s*name: dsh-plugin-deepseek-vision\/mcp$/m)
  assert.doesNotMatch(patch, /^\s*name:\s*['"]?@deepseek-ai\//m)
  assert.deepEqual(
    [...patch.matchAll(/^\s*- id:\s*([A-Za-z0-9._-]+)\s*$/gm)].map(match => match[1]),
    ['deepseek-vision-host', 'deepseek-vision-mcp'],
  )
  assert.match(bridge, /from '@deepseek-ai\/dsh-mcp-client'/)
  assert.match(bridge, /name = 'deepseek-vision-mcp'/)
})
