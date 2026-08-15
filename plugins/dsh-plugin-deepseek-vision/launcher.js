#!/usr/bin/env node

import { chmodSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { homedir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'
import { parseDocument } from 'yaml'

const PACKAGE_ROOT = dirname(fileURLToPath(import.meta.url))
const PACKAGE_VERSION = JSON.parse(readFileSync(join(PACKAGE_ROOT, 'package.json'), 'utf8')).version
const REQUIRED_PYTHON = [3, 10]
const UV_VERSION = '0.12.5'
const UV_ASSETS = {
  'darwin-arm64': ['uv-aarch64-apple-darwin.tar.gz', '5bb0e5fe008a773c3dbcb97ff79cd89e1241464fe9d2f986d52ad8f1b037bd62'],
  'darwin-x64': ['uv-x86_64-apple-darwin.tar.gz', 'b3b2137477cf96c9686ebfb71524614cec780c673fd73e59bce099aef02e70e8'],
  'linux-arm64': ['uv-aarch64-unknown-linux-gnu.tar.gz', '9bf43b4d1a07665bf64d4c4e710930b382321a785e0eb10aac07f46471f86a31'],
  'linux-x64': ['uv-x86_64-unknown-linux-gnu.tar.gz', '68a509da24b06b4223a1c0175fb5eb5bc79342b76cbeff0cfe51ac3f5b17b6b2'],
  'win32-arm64': ['uv-aarch64-pc-windows-msvc.zip', '724279317fee6e5fa8ad1908e4eba2bbe764ef1ece5b3f4597927b62b1fe562a'],
  'win32-x64': ['uv-x86_64-pc-windows-msvc.zip', '4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a'],
}

export function uvAsset(platform = process.platform, arch = process.arch) {
  const value = UV_ASSETS[`${platform}-${arch}`]
  if (!value) throw new Error(`暂不支持自动准备 Python：${platform}-${arch}`)
  return { name: value[0], sha256: value[1] }
}

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
  choose('VISION_SERVICE_ID', settings.provider, 'primary')
  if (!child.VISION_FALLBACKS_JSON?.trim() && settings.fallback?.enabled) {
    child.VISION_FALLBACKS_JSON = JSON.stringify([{
      id: settings.fallback.provider,
      model: settings.fallback.model,
      base_url: settings.fallback.baseUrl,
      api_key_env: 'VISION_FALLBACK_API_KEY',
    }])
  }
  return child
}

export function loadDshCredential(environment = process.env, name = 'VISION_API_KEY') {
  if (environment[name]?.trim()) return environment[name].trim()
  const dshHome = environment.DSH_HOME ? resolve(environment.DSH_HOME) : join(homedir(), '.dsh')
  const filename = join(dshHome, '.credentials.yaml')
  if (!existsSync(filename)) return ''
  // Parser diagnostics can quote source lines. Never forward them because
  // every value in this file is a secret.
  const document = parseDocument(readFileSync(filename, 'utf8'), { prettyErrors: false, uniqueKeys: true })
  if (document.errors.length > 0) throw new Error(`DSH 凭据文件格式无效：${filename}`)
  const value = document.toJS()?.[name]
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

function bootstrapRoot() {
  return join(dirname(runtimeRoot()), 'bootstrap')
}

export async function ensureUv(fetchImpl = fetch) {
  const asset = uvAsset()
  const directory = join(bootstrapRoot(), `uv-${UV_VERSION}`)
  const executable = join(directory, asset.name.replace(/\.(tar\.gz|zip)$/, ''), process.platform === 'win32' ? 'uv.exe' : 'uv')
  if (existsSync(executable)) return executable

  mkdirSync(directory, { recursive: true })
  const archive = join(directory, asset.name)
  console.error(`[deepseek-vision] 未找到 Python 3.10+，正在准备隔离运行时引导器 uv ${UV_VERSION}…`)
  const response = await fetchImpl(`https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${asset.name}`)
  if (!response.ok) throw new Error(`下载 uv 失败（HTTP ${response.status}）`)
  const bytes = Buffer.from(await response.arrayBuffer())
  const digest = createHash('sha256').update(bytes).digest('hex')
  if (digest !== asset.sha256) throw new Error('uv 下载文件 SHA-256 校验失败，已拒绝执行')
  writeFileSync(archive, bytes, { mode: 0o600 })
  // bsdtar is built into supported macOS/Windows systems and GNU tar handles
  // both .tar.gz and .zip here. Argument arrays keep paths with spaces safe.
  checked('tar', ['-xf', archive, '-C', directory])
  rmSync(archive, { force: true })
  if (!existsSync(executable)) throw new Error('uv 解压完成但未找到可执行文件')
  if (process.platform !== 'win32') chmodSync(executable, 0o700)
  return executable
}

export async function ensureRuntime() {
  const root = runtimeRoot()
  const venv = join(root, 'venv')
  const marker = join(root, 'installed')
  const interpreter = venvPython(venv)
  if (existsSync(marker) && existsSync(interpreter)) return interpreter

  mkdirSync(root, { recursive: true })
  // An interrupted preparation must never be mistaken for a complete one.
  if (existsSync(venv)) rmSync(venv, { recursive: true, force: true })
  let python
  try {
    python = findPython()
  } catch {
    const uv = await ensureUv()
    const uvEnvironment = {
      ...process.env,
      UV_PYTHON_INSTALL_DIR: join(bootstrapRoot(), 'python'),
      UV_NO_PROGRESS: '1',
    }
    checked(uv, ['venv', '--python', '3.12', venv], { env: uvEnvironment })
    checked(uv, ['pip', 'install', '--python', interpreter, '--quiet', runtimeWheel()], { env: uvEnvironment })
    writeFileSync(marker, `${new Date().toISOString()}\n`, { mode: 0o600 })
    return interpreter
  }
  checked(python[0], [...python.slice(1), '-m', 'venv', venv])
  checked(interpreter, ['-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '--no-input', runtimeWheel()])
  writeFileSync(marker, `${new Date().toISOString()}\n`, { mode: 0o600 })
  return interpreter
}

export async function main() {
  try {
    const interpreter = await ensureRuntime()
    const key = loadDshCredential()
    const fallbackKey = loadDshCredential(process.env, 'VISION_FALLBACK_API_KEY')
    const childEnvironment = buildChildEnvironment()
    if (key) childEnvironment.VISION_API_KEY = key
    if (fallbackKey) childEnvironment.VISION_FALLBACK_API_KEY = fallbackKey
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

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) void main()
