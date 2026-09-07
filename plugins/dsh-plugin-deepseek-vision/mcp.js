// Keep the Bundle Patch inside this plugin's namespace while delegating the
// MCP protocol implementation to the client shipped by DeepSeek Harness.
export { Config, apply, inject } from '@deepseek-ai/dsh-mcp-client'

export const name = 'deepseek-vision-mcp'
