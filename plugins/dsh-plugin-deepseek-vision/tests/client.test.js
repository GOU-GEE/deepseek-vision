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

test('intercepted image drop releases the native DSH overlay without a duplicate file', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const synthetic = []
  globalThis.DataTransfer = class { constructor() { this.files = [] } }
  globalThis.DragEvent = class {
    constructor(type, options) { this.type = type; Object.assign(this, options) }
  }
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ path: '/tmp/paste.png' }) })
  globalThis.document = {
    activeElement: null,
    execCommand: () => true,
    querySelectorAll: () => [{ getAttribute: () => 'DeepSeek Chat' }],
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: () => undefined,
    dispatchEvent: event => synthetic.push(event),
  }
  client.apply({
    effect: effect => effect(),
    slots: { inject: () => undefined },
  })
  const target = {
    matches: () => true,
    focus: () => undefined,
    dispatchEvent: event => synthetic.push(event),
  }
  await listeners.get('drop')({
    target,
    dataTransfer: { files: [{ type: 'image/png', arrayBuffer: async () => new ArrayBuffer(1) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  assert.equal(synthetic.length, 1)
  assert.equal(synthetic[0].type, 'drop')
  assert.equal(synthetic[0].dataTransfer.files.length, 0)
})
