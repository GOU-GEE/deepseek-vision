window.__ModuleLoader__.load({
  id: 'dsh-plugin-deepseek-vision',
  factory: (require) => {
    const module = { exports: {} }
    const React = require('react')
    const { createElement: h, useEffect, useState } = React
    const ROUTE = '/_dsh/deepseek-vision/paste'
    const SETTINGS_ROUTE = '/_dsh/deepseek-vision/settings'
    const PROVIDERS = {
      zhipu: { label: '智谱 GLM（推荐免费）', model: 'glm-4.6v-flash', baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
      siliconflow: { label: '硅基流动', model: 'Qwen/Qwen2.5-VL-7B-Instruct', baseUrl: 'https://api.siliconflow.cn/v1' },
      dashscope: { label: '通义千问', model: 'qwen-vl-plus', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
      custom: { label: '自定义 OpenAI 兼容服务', model: '', baseUrl: '' },
    }
    const fieldStyle = { width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid var(--dsw-alias-border-secondary, #d0d7de)', background: 'var(--dsw-alias-background-primary, transparent)', color: 'inherit' }
    const buttonStyle = { padding: '7px 12px', borderRadius: 6, border: '1px solid var(--dsw-alias-border-secondary, #d0d7de)', background: 'var(--dsw-alias-background-secondary, transparent)', color: 'inherit', cursor: 'pointer' }

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
      const [apiKey, setApiKey] = useState('')
      const [busy, setBusy] = useState('')
      const [message, setMessage] = useState('')
      const [error, setError] = useState('')

      useEffect(() => {
        let active = true
        settingsRequest().then(payload => {
          if (!active) return
          setSettings(payload.settings)
          setCredential(payload.credential)
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
          provider,
          model: provider === 'custom' ? current.model : preset.model,
          baseUrl: provider === 'custom' ? current.baseUrl : preset.baseUrl,
        }))
        setMessage('')
        setError('')
      }

      const act = async (action) => {
        setBusy(action)
        setMessage('')
        setError('')
        try {
          const payload = await settingsRequest({ action, settings, apiKey })
          if (payload.credential) setCredential(payload.credential)
          if (action === 'save') {
            setApiKey('')
            setMessage('保存成功。请按 ⌘Q 完全退出并重新打开 DeepSeek Harness，使 MCP 使用新配置。')
          } else {
            setMessage(`连接正常，实际响应模型：${payload.model || settings.model}`)
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

      const row = (label, control, hint) => h('label', { style: { display: 'grid', gap: 5 } },
        h('span', { style: { fontSize: 13, fontWeight: 600 } }, label),
        control,
        hint ? h('span', { style: { fontSize: 12, opacity: 0.7 } }, hint) : null,
      )

      return h('li', { style: { listStyle: 'none', border: '1px solid var(--dsw-alias-border-secondary, #d0d7de)', borderRadius: 10, overflow: 'hidden' } },
        h('button', {
          type: 'button',
          'aria-expanded': open,
          onClick: () => setOpen(value => !value),
          style: { width: '100%', padding: '12px 14px', border: 0, background: 'transparent', color: 'inherit', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', textAlign: 'left' },
        }, h('span', null, h('strong', null, 'DeepSeek Vision'), h('br'), h('small', { style: { opacity: 0.7 } }, '视觉服务商、模型与 API Key')), h('span', null, open ? '▴' : '▾')),
        open ? h('div', { style: { padding: '0 14px 14px', display: 'grid', gap: 12 } },
          loading ? h('p', null, '正在读取配置…') : null,
          row('视觉服务商', h('select', { value: settings.provider, onChange: changeProvider, style: fieldStyle },
            Object.entries(PROVIDERS).map(([value, item]) => h('option', { key: value, value }, item.label)),
          )),
          row('模型', h('input', { value: settings.model, onChange: event => setSettings(current => ({ ...current, model: event.target.value })), style: fieldStyle, autoComplete: 'off' })),
          row('Base URL', h('input', { value: settings.baseUrl, onChange: event => setSettings(current => ({ ...current, baseUrl: event.target.value })), style: fieldStyle, autoComplete: 'off' }), '必须是 OpenAI 兼容接口；本机地址外必须使用 HTTPS。'),
          row('视觉 API Key', h('input', { type: 'password', value: apiKey, onChange: event => setApiKey(event.target.value), style: fieldStyle, autoComplete: 'new-password', placeholder: credential.configured ? '已安全保存；留空则保持不变' : '请输入 API Key' }), credential.configured ? `状态：已配置${credential.source ? `（${credential.source}）` : ''}` : '状态：未配置'),
          h('p', { style: { margin: 0, fontSize: 12, opacity: 0.72 } }, '“测试连接”会发送一张 1×1 图片和最多 8 tokens，产生一次极小的真实视觉请求。Key 不会回显到页面、日志或普通配置。'),
          h('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
            h('button', { type: 'button', disabled: Boolean(busy) || loading, onClick: () => act('save'), style: buttonStyle }, busy === 'save' ? '保存中…' : '保存'),
            h('button', { type: 'button', disabled: Boolean(busy) || loading, onClick: () => act('test'), style: buttonStyle }, busy === 'test' ? '测试中…' : '测试连接'),
            credential.configured ? h('button', { type: 'button', disabled: Boolean(busy) || !credential.writable, onClick: unsetKey, style: buttonStyle }, busy === 'unset-key' ? '清除中…' : '清除 Key') : null,
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
