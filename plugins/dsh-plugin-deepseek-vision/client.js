window.__ModuleLoader__.load({
  id: 'dsh-plugin-deepseek-vision',
  factory: () => {
    const module = { exports: {} }
    const ROUTE = '/_dsh/deepseek-vision/paste'

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

    function apply(ctx) {
      document.addEventListener('paste', onPaste, true)
      document.addEventListener('drop', onDrop, true)
      document.addEventListener('dragover', onDragOver, true)
      ctx.effect?.(() => () => {
        document.removeEventListener('paste', onPaste, true)
        document.removeEventListener('drop', onDrop, true)
        document.removeEventListener('dragover', onDragOver, true)
      }, 'deepseek-vision: image listeners')
    }

    module.exports.apply = apply
    module.exports.inject = []
    return module.exports
  },
})
