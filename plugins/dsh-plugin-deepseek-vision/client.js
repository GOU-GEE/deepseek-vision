window.__ModuleLoader__.load({
  id: 'dsh-plugin-deepseek-vision',
  factory: (require) => {
    const module = { exports: {} }
    const React = require('react')
    const { createElement: h, useEffect, useState } = React
    const { IconChevronDownOutline14 } = require('@deepseek-ai/dsh-client-ui-primitives')
    const ROUTE = '/_dsh/deepseek-vision/paste'
    const SETTINGS_ROUTE = '/_dsh/deepseek-vision/settings'
    const PROVIDERS = {
      zhipu: { label: '智谱 GLM（推荐免费）', model: 'glm-4.6v-flash', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
      siliconflow: { label: '硅基流动', model: 'Qwen/Qwen2.5-VL-7B-Instruct', baseUrl: 'https://api.siliconflow.cn/v1' },
      dashscope: { label: '通义千问', model: 'qwen-vl-plus', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
      custom: { label: '自定义 OpenAI 兼容服务', model: '', baseUrl: '' },
    }
    const cardStyle = { listStyle: 'none', border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', background: 'var(--dsw-alias-bg-layer-3, transparent)', borderRadius: 12, overflow: 'hidden' }
    const headerStyle = { appearance: 'none', width: '100%', font: 'inherit', color: 'inherit', textAlign: 'left', cursor: 'pointer', background: 'transparent', border: 0, borderRadius: 12, display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px' }
    const fieldStyle = { width: '100%', height: 34, boxSizing: 'border-box', padding: '0 12px', borderRadius: 8, border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', background: 'var(--dsw-alias-bg-layer-3, transparent)', color: 'var(--dsw-alias-label-primary, inherit)', font: 'inherit', fontSize: 13 }
    const buttonStyle = { appearance: 'none', padding: '5px 14px', borderRadius: 8, border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', background: 'transparent', color: 'var(--dsw-alias-label-secondary, inherit)', cursor: 'pointer', font: 'inherit', fontSize: 13, lineHeight: 1.5 }
    const previewDockStyle = { boxSizing: 'border-box', display: 'flex', alignItems: 'stretch', gap: 8, width: 'calc(100% - var(--dsh-composer-side-clearance, 0px) - var(--dsh-composer-side-clearance, 0px) - var(--dsh-composer-dock-inset, 10px) - var(--dsh-composer-dock-inset, 10px))', maxWidth: 'calc(var(--dsh-composer-card-max-width, 760px) - var(--dsh-composer-dock-inset, 10px) - var(--dsh-composer-dock-inset, 10px))', margin: '0 auto calc(0px - var(--dsh-composer-stack-gap, 10px) - 3px)', padding: '8px var(--dsh-composer-dock-inset, 10px)', overflowX: 'auto', background: 'var(--dsw-alias-bg-layer-3, transparent)', border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', borderRadius: '12px 12px 0 0', borderBottom: 'none' }
    const previewItemStyle = { position: 'relative', flex: 'none', width: 76, display: 'grid', gap: 4, justifyItems: 'center' }
    const previewFrameStyle = { position: 'relative', width: 64, height: 64, display: 'block' }
    const previewImageStyle = { width: 64, height: 64, objectFit: 'cover', display: 'block', borderRadius: 8, border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', background: 'var(--dsw-alias-bg-layer-2, #f6f8fa)' }
    const previewRemoveStyle = { position: 'absolute', top: -6, right: -6, width: 20, height: 20, padding: 0, display: 'grid', placeItems: 'center', appearance: 'none', border: '1px solid var(--dsw-alias-border-l2, #d0d7de)', borderRadius: '999px', background: 'var(--dsw-alias-bg-layer-2, #fff)', color: 'var(--dsw-alias-label-secondary, inherit)', cursor: 'pointer', fontSize: 13, lineHeight: 1, zIndex: 1 }
    const previewBadgeStyle = { position: 'absolute', inset: 'auto 0 0 auto', margin: '0 3px 3px 0', padding: '1px 5px', borderRadius: 999, fontSize: 11, lineHeight: '16px', background: 'var(--dsw-alias-state-business-tertiary, rgba(38,132,255,.16))', color: 'var(--dsw-alias-label-primary-bluish, #0969da)' }
    const previewNameStyle = { maxWidth: 72, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11, lineHeight: '14px', color: 'var(--dsw-alias-label-tertiary, #777)' }

    function clipboardImages(event) {
      return Array.from(event.clipboardData?.items ?? [])
        .filter(item => item.kind === 'file')
        .map(item => item.getAsFile())
        .filter(file => file && /^image\//i.test(file.type))
    }

    function droppedImages(event) {
      return Array.from(event.dataTransfer?.files ?? [])
        .filter(file => /^image\//i.test(file.type))
    }

    function targetsDeepSeek() {
      const buttons = document.querySelectorAll('button[aria-label]')
      for (const button of buttons) {
        const label = button.getAttribute('aria-label') ?? ''
        if (/deepseek/i.test(label) && !/(vision|视觉|\bvl\b)/i.test(label)) return true
      }
      return false
    }

    async function upload(file) {
      const response = await fetch(ROUTE, { method: 'POST', body: await file.arrayBuffer() })
      const body = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(body.error || `图片上传失败（HTTP ${response.status}）`)
      return body.path
    }

    const REFERENCE_SOURCE = 'deepseek-vision'
    const previewListeners = new Set()
    let previewItems = []
    let previewSequence = 0
    let batchSequence = 0
    let services = null
    let activeSessionId = null
    // Last session id this plugin's dock was bound to; a change means the user
    // switched conversations, so the previous session's preview strip must not
    // linger in the new composer.
    let boundSessionId = null
    const insertedBatches = new Map()

    function publicPreview(item) {
      return {
        id: item.id,
        batchId: item.batchId,
        name: item.name,
        size: item.size,
        type: item.type,
        objectUrl: item.objectUrl,
        path: item.path,
        status: item.status,
        error: item.error,
      }
    }

    function emitPreviews() {
      const snapshot = previewItems.map(publicPreview)
      for (const listener of previewListeners) listener(snapshot)
    }

    function subscribePreviews(listener) {
      previewListeners.add(listener)
      return () => previewListeners.delete(listener)
    }

    function createObjectUrl(file) {
      try {
        return URL.createObjectURL?.(file) ?? ''
      } catch {
        return ''
      }
    }

    function revokeObjectUrl(url) {
      if (!url) return
      try {
        URL.revokeObjectURL?.(url)
      } catch {
        // Revocation is best-effort; the browser releases it with the document.
      }
    }

    function inputSnapshot() {
      if (!services?.sessions || !services?.conversation || !activeSessionId) return null
      try {
        const actx = services.sessions.scope(activeSessionId)
        if (!actx) return null
        const input = services.conversation.input.for(actx)
        const state = input?.state?.getSnapshot?.()
        return state ? { input, state } : null
      } catch {
        return null
      }
    }

    function referenceLabel(paths) {
      return paths.length > 1 ? `🖼️×${paths.length}` : '🖼️'
    }

    function insertPreviewReference(batchId, paths) {
      const resolved = inputSnapshot()
      if (!resolved || typeof resolved.input.insertReference !== 'function') return false
      const span = { start: resolved.state.draft.length, end: resolved.state.draft.length, draftRev: resolved.state.draftRev }
      const inserted = resolved.input.insertReference({
        source: REFERENCE_SOURCE,
        ref: batchId,
        label: referenceLabel(paths),
        clipboardText: '',
      }, span)
      if (inserted) insertedBatches.set(batchId, paths)
      return inserted
    }

    function replacePreviewReference(batchId, paths) {
      const resolved = inputSnapshot()
      if (!resolved) {
        insertedBatches.delete(batchId)
        return false
      }
      const occurrence = resolved.state.occurrences.find(candidate => candidate.source === REFERENCE_SOURCE && candidate.ref === batchId)
      if (occurrence && typeof resolved.input.setDraft === 'function') {
        const draft = resolved.state.draft
        resolved.input.setDraft(draft.slice(0, occurrence.offset) + draft.slice(occurrence.offset + 1))
      }
      if (paths.length > 0) return insertPreviewReference(batchId, paths)
      insertedBatches.delete(batchId)
      return true
    }

    function removeAllPreviewReferences() {
      const resolved = inputSnapshot()
      if (!resolved) {
        insertedBatches.clear()
        return
      }
      const occurrences = resolved.state.occurrences
        .filter(candidate => candidate.source === REFERENCE_SOURCE)
        .sort((a, b) => b.offset - a.offset)
      if (occurrences.length > 0 && typeof resolved.input.setDraft === 'function') {
        let draft = resolved.state.draft
        for (const occurrence of occurrences) draft = draft.slice(0, occurrence.offset) + draft.slice(occurrence.offset + 1)
        resolved.input.setDraft(draft)
      }
      insertedBatches.clear()
    }

    function resetPreviews() {
      removeAllPreviewReferences()
      for (const item of previewItems) revokeObjectUrl(item.objectUrl)
      previewItems = []
      emitPreviews()
    }

    function instructionForPaths(paths) {
      return `请调用 mcp__deepseek-vision__${paths.length > 1 ? 'compare_images' : 'analyze_image'} 分析我刚粘贴的图片：${paths.join(' ')} `
    }

    function draftWithoutOccurrences(state) {
      let draft = state.draft
      const occurrences = [...state.occurrences].sort((a, b) => b.offset - a.offset)
      for (const occurrence of occurrences) {
        if (occurrence.offset < 0 || occurrence.offset >= draft.length) continue
        draft = draft.slice(0, occurrence.offset) + draft.slice(occurrence.offset + 1)
      }
      return draft
    }

    function serializeReference(ref) {
      const paths = insertedBatches.get(ref)
      if (!paths || paths.length === 0) throw new Error('DeepSeek Vision 图片引用已失效，请重新粘贴图片')
      const resolved = inputSnapshot()
      const userText = resolved ? draftWithoutOccurrences(resolved.state).trim() : ''
      // The user typed their own request: only surface the uploaded image
      // paths, never the preset tool-call command.
      if (userText) return `🖼️ 图片路径：${paths.join(' ')}`
      return instructionForPaths(paths)
    }

    function watchInputForSend() {
      const resolved = inputSnapshot()
      if (!resolved?.input?.state?.subscribe) return () => undefined
      const read = () => resolved.input.state.getSnapshot()
      let hadReference = read().occurrences.some(candidate => candidate.source === REFERENCE_SOURCE)
      let clearTimer = null
      const unsubscribe = resolved.input.state.subscribe(() => {
        const next = read()
        const hasReference = next.occurrences.some(candidate => candidate.source === REFERENCE_SOURCE)
        if (hadReference && !hasReference && next.phase === 'plain') {
          // A synchronous remove+reinsert (thumbnail × during a multi-image
          // batch) also briefly drops the reference; re-check on the next
          // macrotask so only a real send (reference stays gone) clears.
          clearTimer = setTimeout(() => {
            const after = read()
            if (after.phase === 'plain' && !after.occurrences.some(candidate => candidate.source === REFERENCE_SOURCE)) resetPreviews()
          }, 0)
        }
        hadReference = hasReference
      })
      return () => {
        if (clearTimer !== null) clearTimeout(clearTimer)
        unsubscribe()
      }
    }

    const visionReferenceSource = {
      trigger: '/',
      name: REFERENCE_SOURCE,
      order: 900,
      candidates: async () => [],
      onPick: () => undefined,
      codec: {
        clipboardText: () => '',
        serialize: async ref => serializeReference(ref),
      },
    }

    function addPreview(file, batchId) {
      const item = {
        id: `vision-${++previewSequence}`,
        batchId,
        name: file.name || 'image',
        size: file.size || 0,
        type: file.type || '',
        objectUrl: createObjectUrl(file),
        path: null,
        status: 'uploading',
        error: '',
      }
      previewItems.push(item)
      emitPreviews()
      return item
    }

    function patchPreview(id, patch) {
      const item = previewItems.find(candidate => candidate.id === id)
      if (!item) return
      Object.assign(item, patch)
      emitPreviews()
    }

    function removePreview(id) {
      const index = previewItems.findIndex(candidate => candidate.id === id)
      if (index < 0) return false
      const [item] = previewItems.splice(index, 1)
      revokeObjectUrl(item.objectUrl)
      const remaining = previewItems.filter(candidate => candidate.batchId === item.batchId && candidate.path)
      replacePreviewReference(item.batchId, remaining.map(candidate => candidate.path))
      emitPreviews()
      return true
    }

    function releaseNativeDropOverlay(target) {
      // The real drop is intentionally intercepted so DSH does not add a
      // duplicate native attachment. Follow it with an empty synthetic drop:
      // DSH can clear its drag overlay, while this plugin ignores it because it
      // contains no image files.
      try {
        const event = new Event('drop', { bubbles: true, cancelable: true })
        // DSH only resets its drag-depth state when types contains "Files".
        // Supplying that type with an empty file list reaches its reset branch
        // without adding a second native attachment.
        Object.defineProperty(event, 'dataTransfer', {
          value: { types: ['Files'], files: [] },
        })
        ;(target?.dispatchEvent ? target : document).dispatchEvent(event)
      } catch {
        // DSH also registers dragend on window as an unconditional reset.
        window.dispatchEvent(new Event('dragend'))
      }
    }

    async function handleImages(event, images, action) {
      // Only take over a positively identified text-only DeepSeek route.
      // Unknown or native-vision models retain DSH's normal attachment path.
      if (images.length === 0 || !targetsDeepSeek()) return
      event.preventDefault()
      event.stopImmediatePropagation()
      const batchId = `vision-batch-${++batchSequence}`
      const entries = images.map(file => ({ file, item: addPreview(file, batchId) }))
      // Snapshot the draft at upload start so the final reference insertion
      // can tell "user typed/sent meanwhile" apart from "draft untouched".
      const startSnapshot = inputSnapshot()?.state
      const startDraft = startSnapshot?.draft ?? null
      const startRev = startSnapshot?.draftRev ?? -1
      try {
        await Promise.all(entries.map(async ({ file, item }) => {
          try {
            const path = await upload(file)
            patchPreview(item.id, { path, status: 'ready', error: '' })
          } catch (error) {
            patchPreview(item.id, { status: 'error', error: error?.message ?? String(error) })
          }
        }))
        const resolved = inputSnapshot()
        const endDraft = resolved?.state?.draft ?? null
        const endRev = resolved?.state?.draftRev ?? -1
        // The draft was emptied by an edit or a send while uploads were in
        // flight (a plain paste leaves it untouched: same text, same rev).
        const draftWiped = endDraft === '' && (startDraft !== '' || endRev > startRev)
        const ready = previewItems.filter(item => item.batchId === batchId && item.path)
        if (ready.length > 0 && !draftWiped && resolved?.state?.phase === 'plain') {
          // Idempotent rebuild: covers thumbnails removed mid-upload (the
          // reference now matches the final ready set) and the plain insert.
          replacePreviewReference(batchId, ready.map(item => item.path))
        } else if (draftWiped) {
          // Never inject a reference into a fresh post-send draft — it would
          // silently attach the image to the NEXT message. Drop this batch's
          // previews (the uploaded temp files are server-side cleaned later).
          const doomed = previewItems.filter(item => item.batchId === batchId)
          if (doomed.length > 0) {
            previewItems = previewItems.filter(item => item.batchId !== batchId)
            for (const item of doomed) revokeObjectUrl(item.objectUrl)
            emitPreviews()
          }
          insertedBatches.delete(batchId)
        }
      } catch (error) {
        console.error(`[deepseek-vision] ${action} failed: ${error?.message ?? error}`)
      } finally {
        if (action === 'drop') releaseNativeDropOverlay(event.target)
      }
    }

    async function onPaste(event) {
      await handleImages(event, clipboardImages(event), 'paste')
    }

    async function onDrop(event) {
      await handleImages(event, droppedImages(event), 'drop')
    }

    function onDragOver(event) {
      if (droppedImages(event).length > 0 && targetsDeepSeek()) event.preventDefault()
    }

    async function settingsRequest(body) {
      const response = await fetch(SETTINGS_ROUTE, body ? {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      } : undefined)
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || `请求失败（HTTP ${response.status}）`)
      return payload
    }

    function VisionSettingsCard() {
      const [open, setOpen] = useState(false)
      const [loading, setLoading] = useState(true)
      const [settings, setSettings] = useState({ ...PROVIDERS.zhipu, provider: 'zhipu' })
      const [credential, setCredential] = useState({ configured: false, writable: true })
      const [fallbackCredential, setFallbackCredential] = useState({ configured: false, writable: true })
      const [apiKey, setApiKey] = useState('')
      const [fallbackApiKey, setFallbackApiKey] = useState('')
      const [busy, setBusy] = useState('')
      const [message, setMessage] = useState('')
      const [error, setError] = useState('')

      useEffect(() => {
        let active = true
        settingsRequest().then(payload => {
          if (!active) return
          setSettings(payload.settings)
          setCredential(payload.credential)
          setFallbackCredential(payload.fallbackCredential)
        }).catch(reason => {
          if (active) setError(reason.message || String(reason))
        }).finally(() => {
          if (active) setLoading(false)
        })
        return () => { active = false }
      }, [])

      const changeProvider = event => {
        const provider = event.target.value
        const preset = PROVIDERS[provider]
        setSettings(current => ({
          ...current,
          provider,
          model: provider === 'custom' ? current.model : preset.model,
          baseUrl: provider === 'custom' ? current.baseUrl : preset.baseUrl,
        }))
        setMessage('')
        setError('')
      }

      const act = async (action, target = 'primary') => {
        const busyName = action === 'test' ? `test-${target}` : action
        setBusy(busyName)
        setMessage('')
        setError('')
        try {
          const payload = await settingsRequest({ action, target, settings, apiKey, fallbackApiKey })
          if (payload.credential) setCredential(payload.credential)
          if (payload.fallbackCredential) setFallbackCredential(payload.fallbackCredential)
          if (action === 'save') {
            setApiKey('')
            setFallbackApiKey('')
            setMessage('保存成功。请按 ⌘Q 完全退出并重新打开 DeepSeek Harness，使 MCP 使用新配置。')
          } else {
            setMessage(`${target === 'fallback' ? '备用服务' : '主服务'}连接正常，实际响应模型：${payload.model || settings.model}`)
          }
        } catch (reason) {
          setError(reason.message || String(reason))
        } finally {
          setBusy('')
        }
      }

      const unsetKey = async () => {
        setBusy('unset-key')
        setMessage('')
        setError('')
        try {
          const payload = await settingsRequest({ action: 'unset-key' })
          setCredential(payload.credential)
          setApiKey('')
          setMessage('已清除视觉 API Key。')
        } catch (reason) {
          setError(reason.message || String(reason))
        } finally {
          setBusy('')
        }
      }

      const unsetFallbackKey = async () => {
        setBusy('unset-fallback-key')
        setMessage('')
        setError('')
        try {
          const payload = await settingsRequest({ action: 'unset-fallback-key' })
          setFallbackCredential(payload.fallbackCredential)
          setFallbackApiKey('')
          setMessage('已清除备用服务 API Key。')
        } catch (reason) {
          setError(reason.message || String(reason))
        } finally {
          setBusy('')
        }
      }

      const changeFallbackProvider = event => {
        const provider = event.target.value
        const preset = PROVIDERS[provider]
        setSettings(current => ({
          ...current,
          fallback: {
            ...current.fallback,
            provider,
            model: provider === 'custom' ? current.fallback.model : preset.model,
            baseUrl: provider === 'custom' ? current.fallback.baseUrl : preset.baseUrl,
          },
        }))
        setMessage('')
        setError('')
      }

      const row = (label, control, hint) => h('label', { style: { display: 'grid', gap: 6, padding: '12px 0' } },
        h('span', { style: { fontSize: 13, fontWeight: 500, lineHeight: 1.5 } }, label),
        control,
        hint ? h('span', { style: { fontSize: 12, color: 'var(--dsw-alias-label-tertiary, #777)', lineHeight: 1.5 } }, hint) : null,
      )
      const providerSelect = (value, onChange) => h('span', { style: { position: 'relative', display: 'block' } },
        h('select', {
          value,
          onChange,
          style: { ...fieldStyle, appearance: 'none', paddingRight: 44, cursor: 'pointer' },
        }, Object.entries(PROVIDERS).map(([optionValue, item]) => h('option', { key: optionValue, value: optionValue }, item.label))),
        h('svg', {
          'aria-hidden': true,
          width: 14,
          height: 14,
          viewBox: '0 0 14 14',
          focusable: 'false',
          style: { position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--dsw-alias-label-tertiary, #777)' },
        }, h('path', { d: 'M3 5 7 9 11 5', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'round', strokeLinejoin: 'round' })),
      )

      return h('li', { style: { ...cardStyle, ...(open ? { background: 'var(--dsw-alias-bg-layer-2, transparent)', borderColor: 'var(--dsw-alias-label-dimmed, #aab2bd)' } : {}) } },
        h('button', {
          type: 'button',
          'aria-expanded': open,
          'aria-label': `${open ? '收起' : '展开'}：DeepSeek Vision`,
          onClick: () => setOpen(value => !value),
          style: headerStyle,
        }, h('span', { style: { display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, gap: 4 } },
          h('span', { style: { color: 'var(--dsw-alias-label-primary, inherit)', fontSize: 15, fontWeight: 600, lineHeight: 1.4 } }, 'DeepSeek Vision'),
          h('span', { style: { color: 'var(--dsw-alias-label-tertiary, #777)', fontSize: 13, lineHeight: 1.5 } }, '视觉服务商、模型与 API Key'),
        ), h(IconChevronDownOutline14, { style: { flex: 'none', color: 'var(--dsw-alias-label-tertiary, #777)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .16s' } })),
        open ? h('div', { style: { borderTop: '1px solid var(--dsw-alias-border-l2, #d0d7de)', margin: '0 16px', paddingBottom: 8, display: 'grid' } },
          loading ? h('p', null, '正在读取配置…') : null,
          row('视觉服务商', providerSelect(settings.provider, changeProvider)),
          row('模型', h('input', { value: settings.model, onChange: event => setSettings(current => ({ ...current, model: event.target.value })), style: fieldStyle, autoComplete: 'off' })),
          row('Base URL', h('input', { value: settings.baseUrl, onChange: event => setSettings(current => ({ ...current, baseUrl: event.target.value })), style: fieldStyle, autoComplete: 'off' }), '必须是 OpenAI 兼容接口；本机地址外必须使用 HTTPS。'),
          row('视觉 API Key', h('input', { type: 'password', value: apiKey, onChange: event => setApiKey(event.target.value), style: fieldStyle, autoComplete: 'new-password', placeholder: credential.configured ? '已安全保存；留空则保持不变' : '请输入 API Key' }), credential.configured ? `状态：已配置${credential.source ? `（${credential.source}）` : ''}` : '状态：未配置'),
          h('div', { style: { borderTop: '1px solid var(--dsw-alias-border-secondary, #d0d7de)', paddingTop: 12, display: 'grid', gap: 12 } },
            h('label', { style: { display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600 } },
              h('input', {
                type: 'checkbox',
                checked: settings.fallback?.enabled === true,
                onChange: event => setSettings(current => ({ ...current, fallback: { ...(current.fallback || PROVIDERS.siliconflow), enabled: event.target.checked, provider: current.fallback?.provider || 'siliconflow' } })),
              }),
              '启用备用视觉服务（主服务持续限流时自动切换）',
            ),
            settings.fallback?.enabled ? h(React.Fragment, null,
              row('备用服务商', providerSelect(settings.fallback.provider, changeFallbackProvider)),
              row('备用模型', h('input', { value: settings.fallback.model, onChange: event => setSettings(current => ({ ...current, fallback: { ...current.fallback, model: event.target.value } })), style: fieldStyle, autoComplete: 'off' })),
              row('备用 Base URL', h('input', { value: settings.fallback.baseUrl, onChange: event => setSettings(current => ({ ...current, fallback: { ...current.fallback, baseUrl: event.target.value } })), style: fieldStyle, autoComplete: 'off' })),
              row('备用 API Key', h('input', { type: 'password', value: fallbackApiKey, onChange: event => setFallbackApiKey(event.target.value), style: fieldStyle, autoComplete: 'new-password', placeholder: fallbackCredential.configured ? '已安全保存；留空则保持不变' : '请输入备用服务 Key' }), fallbackCredential.configured ? `状态：已配置${fallbackCredential.source ? `（${fallbackCredential.source}）` : ''}` : '状态：未配置'),
            ) : null,
          ),
          h('p', { style: { margin: 0, fontSize: 12, opacity: 0.72 } }, '“测试连接”会发送一张 1×1 图片和最多 8 tokens，产生一次极小的真实视觉请求。Key 不会回显到页面、日志或普通配置。'),
          h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
            h('button', { type: 'button', disabled: Boolean(busy) || loading, onClick: () => act('save'), style: buttonStyle }, busy === 'save' ? '保存中…' : '保存'),
            h('button', { type: 'button', disabled: Boolean(busy) || loading, onClick: () => act('test', 'primary'), style: buttonStyle }, busy === 'test-primary' ? '测试中…' : '测试主服务'),
            settings.fallback?.enabled ? h('button', { type: 'button', disabled: Boolean(busy) || loading, onClick: () => act('test', 'fallback'), style: buttonStyle }, busy === 'test-fallback' ? '测试中…' : '测试备用服务') : null,
            credential.configured ? h('button', { type: 'button', disabled: Boolean(busy) || !credential.writable, onClick: unsetKey, style: buttonStyle }, busy === 'unset-key' ? '清除中…' : '清除 Key') : null,
            settings.fallback?.enabled && fallbackCredential.configured ? h('button', { type: 'button', disabled: Boolean(busy) || !fallbackCredential.writable, onClick: unsetFallbackKey, style: buttonStyle }, busy === 'unset-fallback-key' ? '清除中…' : '清除备用 Key') : null,
          ),
          message ? h('p', { role: 'status', style: { margin: 0, color: 'var(--dsw-alias-label-success, #1a7f37)' } }, message) : null,
          error ? h('p', { role: 'alert', style: { margin: 0, color: 'var(--dsw-alias-label-danger, #cf222e)' } }, error) : null,
        ) : null,
      )
    }

    function VisionPreviewDock() {
      const [items, setItems] = useState(() => previewItems.map(publicPreview))
      useEffect(() => {
        const offPreviews = subscribePreviews(snapshot => setItems(snapshot))
        const offInput = watchInputForSend()
        return () => {
          offPreviews()
          offInput()
        }
      }, [])
      if (items.length === 0) return null
      return h('div', { style: previewDockStyle, 'aria-label': 'DeepSeek Vision 图片预览' },
        items.map(item => h('div', { key: item.id, style: previewItemStyle },
          h('span', { style: previewFrameStyle },
            item.objectUrl ? h('img', { src: item.objectUrl, alt: item.name, style: previewImageStyle }) : h('span', { style: previewImageStyle, 'aria-hidden': true }),
            h('button', {
              type: 'button',
              'aria-label': `移除图片：${item.name}`,
              title: '移除图片',
              style: previewRemoveStyle,
              onClick: () => removePreview(item.id),
            }, '×'),
            h('span', { style: item.status === 'error' ? { ...previewBadgeStyle, background: 'var(--dsw-alias-state-error-tertiary, rgba(207,34,46,.12))', color: 'var(--dsw-alias-state-error-primary, #cf222e)' } : previewBadgeStyle },
              item.status === 'ready' ? '已就绪' : item.status === 'error' ? '上传失败' : '上传中'),
          ),
          h('span', { style: previewNameStyle, title: item.error || item.name }, item.name),
        )),
      )
    }

    function apply(ctx) {
      services = {
        sessions: ctx.sessions,
        conversation: ctx.conversation,
        inputTriggers: ctx.inputTriggers,
      }
      document.addEventListener('paste', onPaste, true)
      document.addEventListener('drop', onDrop, true)
      document.addEventListener('dragover', onDragOver, true)
      ctx.effect?.(() => () => {
        document.removeEventListener('paste', onPaste, true)
        document.removeEventListener('drop', onDrop, true)
        document.removeEventListener('dragover', onDragOver, true)
        resetPreviews()
        services = null
        activeSessionId = null
        boundSessionId = null
      }, 'deepseek-vision: image listeners')
      ctx.effect?.(() => services?.inputTriggers?.registerSource?.(visionReferenceSource), 'deepseek-vision: reference source')
      ctx.slots.inject('settings.plugin.item', () => ctx.slots.register({
        name: 'settings.plugin.item',
        id: 'deepseek-vision',
        order: 25,
        inject: () => ({}),
      }, VisionSettingsCard))
      ctx.slots.inject('conversation.input.dock', () => ctx.slots.register({
        name: 'conversation.input.dock',
        id: 'deepseek-vision-preview',
        order: 10,
        inject: (sessionId) => {
          if (typeof sessionId === 'string') {
            if (sessionId !== boundSessionId) {
              const previous = boundSessionId
              boundSessionId = sessionId
              activeSessionId = sessionId
              if (previous !== null) {
                // Session switched: drop the previous conversation's preview
                // strip. Deferred to a microtask so we never reset (and
                // re-render subscribers) in the middle of a render pass.
                queueMicrotask(() => {
                  if (boundSessionId === sessionId) resetPreviews()
                })
              }
            }
          }
          return {}
        },
      }, VisionPreviewDock))
    }

    module.exports.apply = apply
    module.exports.inject = ['slots', 'sessions', 'conversation', 'inputTriggers']
    module.exports.PROVIDERS = PROVIDERS
    module.exports.previewInternals = {
      list: () => previewItems.map(publicPreview),
      remove: removePreview,
      subscribe: subscribePreviews,
      reset: resetPreviews,
      watchInput: watchInputForSend,
    }
    return module.exports
  },
})
