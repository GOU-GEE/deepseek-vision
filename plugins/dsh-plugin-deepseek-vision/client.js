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

    function insertText(target, text) {
      const element = target?.matches?.('textarea,input') ? target : document.activeElement
      if (!element?.matches?.('textarea,input')) return false
      element.focus()
      let inserted = false
      try {
        inserted = document.execCommand('insertText', false, text)
      } catch {
        inserted = false
      }
      if (!inserted) {
        const prototype = element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
        Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, `${element.value}${text}`)
        element.dispatchEvent(new Event('input', { bubbles: true }))
      }
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
      try {
        const paths = await Promise.all(images.map(upload))
        const instruction = `请调用 mcp__deepseek-vision__${paths.length > 1 ? 'compare_images' : 'analyze_image'} 分析我刚粘贴的图片：${paths.join(' ')} `
        insertText(event.target, instruction)
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
          row('视觉服务商', h('select', { value: settings.provider, onChange: changeProvider, style: fieldStyle },
            Object.entries(PROVIDERS).map(([value, item]) => h('option', { key: value, value }, item.label)),
          )),
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
              row('备用服务商', h('select', { value: settings.fallback.provider, onChange: changeFallbackProvider, style: fieldStyle },
                Object.entries(PROVIDERS).map(([value, item]) => h('option', { key: value, value }, item.label)),
              )),
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

    function apply(ctx) {
      document.addEventListener('paste', onPaste, true)
      document.addEventListener('drop', onDrop, true)
      document.addEventListener('dragover', onDragOver, true)
      ctx.effect?.(() => () => {
        document.removeEventListener('paste', onPaste, true)
        document.removeEventListener('drop', onDrop, true)
        document.removeEventListener('dragover', onDragOver, true)
      }, 'deepseek-vision: image listeners')
      ctx.slots.inject('settings.plugin.item', () => ctx.slots.register({
        name: 'settings.plugin.item',
        id: 'deepseek-vision',
        order: 25,
        inject: () => ({}),
      }, VisionSettingsCard))
    }

    module.exports.apply = apply
    module.exports.inject = ['slots']
    module.exports.PROVIDERS = PROVIDERS
    return module.exports
  },
})
