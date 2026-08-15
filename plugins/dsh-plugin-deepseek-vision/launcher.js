#!/usr/bin/env node

import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'
import { parseDocument } from 'yaml'

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url))
const PACKAGE_VERSION = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8')).version
const REQUIRED_PYTHON = [3, 10]

export function parsePythonVersion(text) {
  const match = /Python\s+(\d+)\.(\d+)(?:\.(\d+))?/.exec(text)
  return match ? [Number(match[1]), Number(match[2]), Number(match[3] ?? 0)] : null
}

export function supportsPython(version) {
  return Boolean(version && (version[0] > REQUIRED_PYTHON[0] || (version[0] === REQUIRED_PYTHON[0] && version[1] >= REQUIRED_PYTHON[1])))
}

function candidates() {
  const values = []
  if (process.env.VISION_PYTHON) values.push([process.env.VISION_PYTHON])
  if (process.platform === 'win32') values.push(['py', '-3.13'], ['py', '-3.12'], ['py', '-3.11'], ['py', '-3.10'])
  values.push(['python3'], ['python'])
  return values
}

export function findPython(run = spawnSync) {
  for (const candidate of candidates()) {
    const result = run(candidate[0], [...candidate.slice(1), '--version'], { encoding: 'utf8', windowsHide: true })
    const version = parsePythonVersion(`${result.stdout ?? ''}\n${result.stderr ?? ''}`)
    if (result.status === 0 && supportsPython(version)) return candidate
  }
  throw new Error('未找到 Python 3.10+。请先安装 Python，或设置 VISION_PYTHON 为解释器绝对路径。')
}

function runtimeWheel() {
  const directory = join(PACKAGE_ROOT, 'runtime')
  const wheel = existsSync(directory) ? readdirSync(directory).find(name => /^deepseek_vision_mcp-.*\.whl$/.test(name)) : undefined
  if (!wheel) throw new Error('npm 包缺少内置 deepseek-vision-mcp wheel，请重新安装插件。')
  return join(directory, wheel)
}

function venvPython(venv) {
  return process.platform === 'win32' ? join(venv, 'Scripts', 'python.exe') : join(venv, 'bin', 'python')
}

export function runtimeRoot() {
  const dshHome = process.env.DSH_HOME ? resolve(process.env.DSH_HOME) : join(homedir(), '.dsh')
  return join(dshHome, 'cache', 'deepseek-vision-mcp', PACKAGE_VERSION)
}

export function loadVisionSettings(environment = process.env) {
  const dshHome = environment.DSH_HOME ? resolve(environment.DSH_HOME) : join(homedir(), '.dsh')
  const filename = join(dshHome, 'deepseek-vision.json')
  if (!existsSync(filename)) return {}
  try {
    const value = JSON.parse(readFileSync(filename, 'utf8'))
    return value && typeof value === 'object' ? value : {}
  } catch {
    throw new Error(`DSH 视觉配置文件格式无效：${filename}`)
  }
}

export function buildChildEnvironment(environment = process.env) {
  const child = { ...environment }
  const settings = loadVisionSettings(environment)
  const choose = (name, stored, fallback) => {
    const explicit = typeof child[name] === 'string' ? child[name].trim() : ''
    child[name] = explicit || (typeof stored === 'string' ? stored.trim() : '') || fallback
  }
  choose('VISION_MODEL', settings.model, 'glm-4.6v-flash')
  choose('VISION_BASE_URL', settings.baseUrl, 'https://open.bigmodel.cn/api/paas/v4')
  choose('VISION_PROVIDER', undefined, 'openai_compatible')
  return child
}

export function loadDshCredential(environment = process.env) {
  if (environment.VISION_API_KEY?.trim()) return environment.VISION_API_KEY.trim()
  const dshHome = environment.DSH_HOME ? resolve(environment.DSH_HOME) : join(homedir(), '.dsh')
  const filename = join(dshHome, '.credentials.yaml')
  if (!existsSync(filename)) return ''
  // Parser diagnostics can quote source lines. Never forward them because
  // every value in this file is a secret.
  const document = parseDocument(readFileSync(filename, 'utf8'), { prettyErrors: false, uniqueKeys: true })
  if (document.errors.length > 0) throw new Error(`DSH 凭据文件格式无效：${filename}`)
  const value = document.toJS()?.VISION_API_KEY
  return typeof value === 'string' ? value.trim() : ''
}

function checked(command, args, options = {}) {
  // stdout is the MCP JSON-RPC channel even during first-run preparation.
  // Send every installer byte to stderr so pip/venv can never corrupt it.
  const result = spawnSync(command, args, {
    stdio: ['ignore', process.stderr, process.stderr],
    windowsHide: true,
    ...options,
  })
  if (result.status !== 0) throw new Error(`命令失败（exit ${result.status}）：${basename(command)} ${args.join(' ')}`)
}

export function ensureRuntime() {
  const root = runtimeRoot()
  const venv = join(root, 'venv')
  const marker = join(root, 'installed')
  const interpreter = venvPython(venv)
  if (existsSync(marker) && existsSync(interpreter)) return interpreter

  mkdirSync(root, { recursive: true })
  // An interrupted preparation must never be mistaken for a complete one.
  if (existsSync(venv)) rmSync(venv, { recursive: true, force: true })
  const python = findPython()
  checked(python[0], [...python.slice(1), '-m', 'venv', venv])
  checked(interpreter, ['-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '--no-input', runtimeWheel()])
  writeFileSync(marker, `${new Date().toISOString()}\n`, { mode: 0o600 })
  return interpreter
}

export function main() {
  try {
    const interpreter = ensureRuntime()
    const key = loadDshCredential()
    const childEnvironment = buildChildEnvironment()
    if (key) childEnvironment.VISION_API_KEY = key
    const child = spawn(interpreter, ['-m', 'deepseek_vision_mcp'], {
      stdio: 'inherit',
      env: childEnvironment,
      windowsHide: true,
    })
    for (const signal of ['SIGINT', 'SIGTERM']) {
      process.on(signal, () => child.kill(signal))
    }
    child.on('error', error => {
      console.error(`[deepseek-vision] 无法启动 MCP：${error.message}`)
      process.exitCode = 1
    })
    child.on('exit', (code, signal) => {
      process.exitCode = code ?? (signal ? 1 : 0)
    })
  } catch (error) {
    console.error(`[deepseek-vision] 托管运行时准备失败：${error instanceof Error ? error.message : error}`)
    process.exitCode = 1
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
