// 临时联调验证脚本：CDP 驱动 Chrome headless 对新页面截图
const { spawn } = require('node:child_process')
const fs = require('node:fs')

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const PORT = 9222
const BASE = 'http://localhost:5173'
const API = 'http://127.0.0.1:8000'
const OUT = 'D:/pythonproject/knowledgeforge/frontend/_smoke'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function getToken() {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'admin123' }),
  })
  const json = await res.json()
  if (json.code !== 0) throw new Error('login failed: ' + JSON.stringify(json))
  return json.data.access_token
}

function launchChrome() {
  return spawn(CHROME, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--user-data-dir=' + OUT + '/chrome-profile',
    '--no-sandbox',
    '--disable-gpu',
    '--window-size=1400,900',
    'about:blank',
  ], { stdio: 'ignore' })
}

async function getWsUrl() {
  for (let i = 0; i < 20; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`)
      const targets = await res.json()
      const page = targets.find((t) => t.type === 'page')
      if (page) return page.webSocketDebuggerUrl
    } catch {}
    await sleep(500)
  }
  throw new Error('chrome not ready')
}

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl)
    let id = 0
    const pending = new Map()
    ws.onopen = () => resolve({ ws, send })
    ws.onerror = (e) => reject(new Error('ws error ' + e.message))
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg.result)
        pending.delete(msg.id)
      }
    }
    function send(method, params = {}) {
      return new Promise((res) => {
        const mid = ++id
        pending.set(mid, res)
        ws.send(JSON.stringify({ id: mid, method, params }))
      })
    }
  })
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const token = await getToken()
  console.log('token ok, len=' + token.length)

  const chrome = launchChrome()
  await sleep(2500)
  const wsUrl = await getWsUrl()
  const { ws, send } = await connect(wsUrl)
  console.log('chrome connected')

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Log.enable')

  const consoleErrors = []
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
      consoleErrors.push(JSON.stringify(msg.params.args.map((a) => a.value || a.description || '')))
    }
    if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') {
      consoleErrors.push(msg.params.entry.text)
    }
  })

  // 先截登录页（未注入 token）
  await send('Page.navigate', { url: BASE + '/login' })
  await sleep(3000)
  const loginShot = await send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(`${OUT}/login.png`, Buffer.from(loginShot.data, 'base64'))
  console.log('shot: login')

  // 注入 token 到 localStorage，使路由守卫放行
  await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `localStorage.setItem('access_token', ${JSON.stringify(token)});`,
  })

  const pages = [
    ['generate', '/question-management/generate'],
    ['tasks', '/question-management/tasks'],
    ['task-detail', '/question-management/tasks/1'],
    ['review', '/question-management/review'],
    ['questions', '/question-management/questions'],
    ['question-detail', '/question-management/questions/1'],
  ]

  for (const [name, path] of pages) {
    await send('Page.navigate', { url: BASE + path })
    await sleep(9000)
    const shot = await send('Page.captureScreenshot', { format: 'png' })
    fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(shot.data, 'base64'))
    console.log('shot: ' + name)
  }

  console.log('CONSOLE_ERRORS=' + consoleErrors.length)
  consoleErrors.slice(0, 10).forEach((e) => console.log('  ERR: ' + e))

  ws.close()
  chrome.kill()
  process.exit(0)
}

main().catch((e) => {
  console.error('FATAL', e)
  process.exit(1)
})
