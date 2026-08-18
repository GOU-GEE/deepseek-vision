import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const NativeURL = globalThis.URL

async function loadClient() {
  globalThis.URL = NativeURL
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
    if (name === '@deepseek-ai/dsh-client-ui-primitives') {
      return { IconChevronDownOutline14: props => ({ type: 'chevron', props }) }
    }
    throw new Error(`unexpected client require: ${name}`)
  })
}

function textDeepSeekDocument(target, listeners) {
  return {
    activeElement: target,
    execCommand: () => false,
    querySelectorAll: () => [{ getAttribute: () => 'DeepSeek Chat' }],
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: () => undefined,
    dispatchEvent: () => undefined,
  }
}

function makeInputFacade() {
  const state = { draft: '', draftRev: 0, occurrences: [], phase: 'plain' }
  const listeners = new Set()
  const inserted = []
  const setDrafts = []
  const notify = () => {
    for (const listener of [...listeners]) listener()
  }
  const input = {
    state: {
      getSnapshot: () => ({ ...state, occurrences: [...state.occurrences] }),
      subscribe: listener => {
        listeners.add(listener)
        return () => listeners.delete(listener)
      },
    },
    insertReference(reference, span) {
      if (span.draftRev !== state.draftRev) return false
      state.draft = `${state.draft.slice(0, span.end)}\uFFFC${state.draft.slice(span.end)}`
      state.occurrences.push({
        source: reference.source,
        ref: reference.ref,
        label: reference.label,
        clipboardText: reference.clipboardText,
        offset: span.end,
      })
      state.draftRev += 1
      inserted.push({ reference, span })
      return true
    },
    setDraft(draft) {
      setDrafts.push(draft)
      state.draft = draft
      state.draftRev += 1
      // The production machine rebuilds occurrences; for this contract test
      // our plugin always reinserts the survivors right after this call.
      state.occurrences = []
    },
  }
  return { state, input, inserted, setDrafts, notify }
}

function applyWithHarness(client, listeners, facade, extra) {
  const injectedSlots = []
  const registeredSlots = []
  const registeredSources = []
  const actx = { scope: 'session-test' }
  const ctx = {
    effect: effect => effect(),
    slots: {
      inject: (name, effect) => {
        injectedSlots.push(name)
        return effect()
      },
      register: (options, component) => {
        registeredSlots.push({ options, component })
        return () => undefined
      },
    },
    sessions: { scope: id => (id === 'session-test' ? actx : undefined) },
    conversation: { input: { for: () => facade.input } },
    inputTriggers: { registerSource: source => { registeredSources.push(source); return () => undefined } },
    ...extra,
  }
  client.apply(ctx)
  const dock = registeredSlots.find(entry => entry.options.id === 'deepseek-vision-preview')
  if (dock) assert.deepEqual(dock.options.inject('session-test'), {})
  return { ctx, injectedSlots, registeredSlots, registeredSources }
}

test('client registers listeners, settings card, composer dock, and hidden reference codec', async () => {
  const client = await loadClient()
  assert.deepEqual(client.inject, ['slots', 'sessions', 'conversation', 'inputTriggers'])
  assert.equal(client.PROVIDERS.zhipu.model, 'glm-4.6v-flash')
  assert.equal(client.PROVIDERS.gemini.model, 'gemini-2.5-flash')
  assert.equal(client.PROVIDERS.gemini.baseUrl, 'https://generativelanguage.googleapis.com/v1beta/openai/')
  const listeners = new Map()
  globalThis.document = {
    addEventListener: (...args) => listeners.set(args[0], args[1]),
    removeEventListener: () => undefined,
  }
  const facade = makeInputFacade()
  const harness = applyWithHarness(client, listeners, facade)
  assert.deepEqual([...listeners.keys()], ['paste', 'drop', 'dragover'])
  assert.deepEqual(harness.injectedSlots, ['settings.plugin.item', 'conversation.input.dock'])
  const settingsCard = harness.registeredSlots.find(entry => entry.options.key === 'deepseek-vision')
  assert.ok(settingsCard)
  assert.equal(settingsCard.options.key, 'deepseek-vision')
  assert.equal(harness.registeredSources.length, 1)
  assert.equal(harness.registeredSources[0].name, 'deepseek-vision')
  assert.equal(await harness.registeredSources[0].codec.clipboardText('batch'), '')
})

test('intercepted image drop releases the native DSH overlay without a duplicate file', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const synthetic = []
  let nativeOverlayVisible = true
  let nativeAttachments = 0
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
  const facade = makeInputFacade()
  client.apply({
    effect: effect => effect(),
    slots: { inject: () => undefined },
    sessions: { scope: () => undefined },
    conversation: { input: { for: () => facade.input } },
    inputTriggers: { registerSource: () => () => undefined },
  })
  const target = {
    matches: () => true,
    focus: () => undefined,
    dispatchEvent: event => {
      synthetic.push(event)
      if (event.dataTransfer?.types.includes('Files')) {
        nativeOverlayVisible = false
        nativeAttachments += event.dataTransfer.files.length
      }
    },
  }
  await listeners.get('drop')({
    target,
    dataTransfer: { files: [{ type: 'image/png', arrayBuffer: async () => new ArrayBuffer(1) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  assert.equal(synthetic.length, 1)
  assert.equal(synthetic[0].type, 'drop')
  assert.deepEqual(synthetic[0].dataTransfer.types, ['Files'])
  assert.equal(synthetic[0].dataTransfer.files.length, 0)
  assert.equal(nativeOverlayVisible, false)
  assert.equal(nativeAttachments, 0)
})

test('paste inserts a hidden image reference instead of visible instruction text', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  const revoked = []
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: url => revoked.push(url) }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ path: '/tmp/paste-a.jpg' }) })
  const target = {
    matches: () => true,
    focus: () => undefined,
    dispatchEvent: () => undefined,
  }
  globalThis.document = textDeepSeekDocument(target, listeners)
  const harness = applyWithHarness(client, listeners, facade)
  await listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 100, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  const previews = client.previewInternals.list()
  assert.equal(previews.length, 1)
  assert.equal(previews[0].status, 'ready')
  assert.equal(facade.state.draft, '\uFFFC')
  assert.ok(!facade.state.draft.includes('analyze_image'))
  assert.equal(facade.state.occurrences.length, 1)
  assert.equal(facade.state.occurrences[0].source, 'deepseek-vision')
  assert.equal(facade.state.occurrences[0].label, '🖼️')
  const modelForm = await harness.registeredSources[0].codec.serialize(facade.state.occurrences[0].ref)
  assert.ok(modelForm.includes('mcp__deepseek-vision__analyze_image'))
  assert.ok(modelForm.includes('/tmp/paste-a.jpg'))
  assert.equal(client.previewInternals.remove(previews[0].id), true)
  assert.equal(facade.state.draft, '')
  assert.deepEqual(revoked, ['blob:a.jpg'])
})

test('multi-image paste serializes compare_images and removal rebuilds the hidden reference', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: () => undefined }
  const pathForBody = { a: '/tmp/a.jpg', b: '/tmp/b.jpg' }
  globalThis.fetch = async (_route, options) => ({ ok: true, json: async () => ({ path: pathForBody[options.body] }) })
  const target = {
    matches: () => true,
    focus: () => undefined,
    dispatchEvent: () => undefined,
  }
  globalThis.document = textDeepSeekDocument(target, listeners)
  const harness = applyWithHarness(client, listeners, facade)
  const file = (name, body) => ({ name, type: 'image/jpeg', size: 100, arrayBuffer: async () => body })
  await listeners.get('paste')({
    target,
    clipboardData: {
      items: [
        { kind: 'file', getAsFile: () => file('a.jpg', 'a') },
        { kind: 'file', getAsFile: () => file('b.jpg', 'b') },
      ],
    },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  assert.equal(client.previewInternals.list().length, 2)
  assert.equal(facade.state.occurrences.length, 1)
  assert.equal(facade.state.occurrences[0].label, '🖼️×2')
  const firstRef = facade.state.occurrences[0].ref
  let modelForm = await harness.registeredSources[0].codec.serialize(firstRef)
  assert.ok(modelForm.includes('mcp__deepseek-vision__compare_images'))
  assert.ok(modelForm.includes('/tmp/a.jpg'))
  assert.ok(modelForm.includes('/tmp/b.jpg'))
  client.previewInternals.remove(client.previewInternals.list()[0].id)
  assert.equal(facade.state.occurrences.length, 1)
  assert.equal(facade.state.occurrences[0].label, '🖼️')
  modelForm = await harness.registeredSources[0].codec.serialize(facade.state.occurrences[0].ref)
  assert.ok(modelForm.includes('mcp__deepseek-vision__analyze_image'))
  assert.ok(!modelForm.includes('/tmp/a.jpg'))
  assert.ok(modelForm.includes('/tmp/b.jpg'))
})

test('upload failure keeps an error thumbnail and inserts no hidden reference', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: () => undefined }
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ error: '模拟上传失败' }) })
  const target = {
    matches: () => true,
    focus: () => undefined,
    dispatchEvent: () => undefined,
  }
  globalThis.document = textDeepSeekDocument(target, listeners)
  applyWithHarness(client, listeners, facade)
  await listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 1, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  const previews = client.previewInternals.list()
  assert.equal(previews.length, 1)
  assert.equal(previews[0].status, 'error')
  assert.equal(previews[0].error, '模拟上传失败')
  assert.equal(facade.state.draft, '')
  assert.equal(facade.state.occurrences.length, 0)
  client.previewInternals.reset()
  assert.deepEqual(client.previewInternals.list(), [])
  assert.equal(facade.state.draft, '')
})

test('reference serializes the preset command only when the user typed nothing', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: () => undefined }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ path: '/tmp/paste-a.jpg' }) })
  const target = { matches: () => true, focus: () => undefined, dispatchEvent: () => undefined }
  globalThis.document = textDeepSeekDocument(target, listeners)
  const harness = applyWithHarness(client, listeners, facade)
  await listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 100, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  const ref = facade.state.occurrences[0].ref
  let modelForm = await harness.registeredSources[0].codec.serialize(ref)
  assert.ok(modelForm.includes('mcp__deepseek-vision__analyze_image'))

  facade.state.draft = '\uFFFC 这个是什么意思'
  modelForm = await harness.registeredSources[0].codec.serialize(ref)
  assert.ok(!modelForm.includes('mcp__deepseek-vision__analyze_image'))
  assert.ok(modelForm.includes('/tmp/paste-a.jpg'))
  assert.ok(modelForm.includes('🖼️'))
})

test('successful send auto-clears the thumbnail strip; a failed send keeps it', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  const revoked = []
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: url => revoked.push(url) }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ path: '/tmp/paste-a.jpg' }) })
  const target = { matches: () => true, focus: () => undefined, dispatchEvent: () => undefined }
  globalThis.document = textDeepSeekDocument(target, listeners)
  applyWithHarness(client, listeners, facade)
  await listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 100, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  assert.equal(client.previewInternals.list().length, 1)
  client.previewInternals.watchInput()
  const originalRef = facade.state.occurrences[0].ref

  // A synchronous drop+reinsert (multi-image remove path) must NOT clear.
  facade.state.occurrences = []
  facade.state.draft = ''
  facade.notify()
  facade.state.occurrences = [{ source: 'deepseek-vision', ref: originalRef, label: '🖼️', clipboardText: '', offset: 0 }]
  facade.state.draft = '\uFFFC'
  facade.notify()
  await new Promise(resolve => setTimeout(resolve, 5))
  assert.equal(client.previewInternals.list().length, 1)

  // Successful send: the reference disappears and stays gone.
  facade.state.occurrences = []
  facade.state.draft = ''
  facade.notify()
  await new Promise(resolve => setTimeout(resolve, 5))
  assert.deepEqual(client.previewInternals.list(), [])
  assert.deepEqual(revoked, ['blob:a.jpg'])
})

test('switching conversation sessions clears the previous session preview strip', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: () => undefined }
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ path: '/tmp/paste-a.jpg' }) })
  const target = { matches: () => true, focus: () => undefined, dispatchEvent: () => undefined }
  globalThis.document = textDeepSeekDocument(target, listeners)
  const harness = applyWithHarness(client, listeners, facade)
  const dock = harness.registeredSlots.find(entry => entry.options.id === 'deepseek-vision-preview')
  assert.ok(dock)
  await listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 100, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  assert.equal(client.previewInternals.list().length, 1)
  assert.equal(facade.state.occurrences.length, 1)
  // Re-injecting the SAME session is a no-op: the strip stays.
  dock.options.inject('session-test')
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(client.previewInternals.list().length, 1)
  // Switching sessions drops the previous strip (the old draft keeps its chip).
  dock.options.inject('session-other')
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.deepEqual(client.previewInternals.list(), [])
})

test('removing a thumbnail mid-upload rebuilds the reference from the final ready set', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: () => undefined }
  let resolveB
  const gateB = new Promise(resolve => { resolveB = resolve })
  globalThis.fetch = async (_route, options) => options?.body === 'b'
    ? gateB
    : ({ ok: true, json: async () => ({ path: '/tmp/a.jpg' }) })
  const target = { matches: () => true, focus: () => undefined, dispatchEvent: () => undefined }
  globalThis.document = textDeepSeekDocument(target, listeners)
  const harness = applyWithHarness(client, listeners, facade)
  const file = (name, body) => ({ name, type: 'image/jpeg', size: 100, arrayBuffer: async () => body })
  const paste = listeners.get('paste')({
    target,
    clipboardData: {
      items: [
        { kind: 'file', getAsFile: () => file('a.jpg', 'a') },
        { kind: 'file', getAsFile: () => file('b.jpg', 'b') },
      ],
    },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  // a settled, b still uploading: no reference exists yet.
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(client.previewInternals.list().length, 2)
  assert.equal(facade.state.occurrences.length, 0)
  // Remove the settled a while b uploads.
  const settledA = client.previewInternals.list().find(item => item.name === 'a.jpg')
  client.previewInternals.remove(settledA.id)
  assert.equal(facade.state.occurrences.length, 0)
  resolveB({ ok: true, json: async () => ({ path: '/tmp/paste-b.jpg' }) })
  await paste
  // The final reference covers only the survivor b.
  assert.equal(facade.state.occurrences.length, 1)
  assert.equal(facade.state.occurrences[0].label, '🖼️')
  const modelForm = await harness.registeredSources[0].codec.serialize(facade.state.occurrences[0].ref)
  assert.ok(modelForm.includes('/tmp/paste-b.jpg'))
  assert.ok(!modelForm.includes('/tmp/a.jpg'))
  assert.equal(client.previewInternals.list().length, 1)
})

test('a send while uploads are in flight never injects a reference into the next draft', async () => {
  const client = await loadClient()
  const listeners = new Map()
  const facade = makeInputFacade()
  const revoked = []
  globalThis.Event = class { constructor(type, options) { this.type = type; Object.assign(this, options) } }
  globalThis.URL = { createObjectURL: file => `blob:${file.name}`, revokeObjectURL: url => revoked.push(url) }
  let resolveUpload
  const gate = new Promise(resolve => { resolveUpload = resolve })
  globalThis.fetch = async () => gate
  const target = { matches: () => true, focus: () => undefined, dispatchEvent: () => undefined }
  globalThis.document = textDeepSeekDocument(target, listeners)
  applyWithHarness(client, listeners, facade)
  const paste = listeners.get('paste')({
    target,
    clipboardData: { items: [{ kind: 'file', getAsFile: () => ({ name: 'a.jpg', type: 'image/jpeg', size: 100, arrayBuffer: async () => new ArrayBuffer(1) }) }] },
    preventDefault: () => undefined,
    stopImmediatePropagation: () => undefined,
  })
  await new Promise(resolve => setTimeout(resolve, 0))
  assert.equal(client.previewInternals.list().length, 1)
  // The user typed and sent while the upload was pending: draft emptied.
  facade.input.setDraft('')
  resolveUpload({ ok: true, json: async () => ({ path: '/tmp/paste-a.jpg' }) })
  await paste
  assert.deepEqual(client.previewInternals.list(), [])
  assert.equal(facade.state.occurrences.length, 0)
  assert.equal(facade.state.draft, '')
  assert.deepEqual(revoked, ['blob:a.jpg'])
})
