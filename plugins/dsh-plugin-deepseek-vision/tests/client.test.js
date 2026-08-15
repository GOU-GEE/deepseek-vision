import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

async function loadClient() {
  let specification
  globalThis.window = { __ModuleLoader__: { load(value) { specification = value } } }
  const source = await readFile(new URL('../client.js', import.meta.url), 'utf8')
  ;(0, eval)(source)
  const React = {
    createElement: (...args) => ({ args }),
    useEffect: () => undefined,
    useState: initial => [initial, () => undefined],
  }
  return specification.factory(name => {
    if (name === 'react') return React
    throw new Error(`unexpected client require: ${name}`)
  })
}

test('client registers image listeners and a DSH settings card', async () => {
  const client = await loadClient()
  assert.deepEqual(client.inject, ['slots'])
  assert.equal(client.PROVIDERS.zhipu.model, 'glm-4.6v-flash')
  let registered
  const listeners = []
  globalThis.document = {
    addEventListener: (...args) => listeners.push(args),
    removeEventListener: () => undefined,
  }
  client.apply({
    effect: effect => effect(),
    slots: {
      inject: (name, effect) => {
        assert.equal(name, 'settings.plugin.item')
        return effect()
      },
      register: (options, component) => {
        registered = { options, component }
        return () => undefined
      },
    },
  })
  assert.deepEqual(listeners.map(([name]) => name), ['paste', 'drop', 'dragover'])
  assert.equal(registered.options.id, 'deepseek-vision')
  assert.equal(typeof registered.component, 'function')
})
