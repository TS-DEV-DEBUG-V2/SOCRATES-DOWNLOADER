const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const fsp = require('fs/promises');
const os = require('os');
const https = require('https');
const http = require('http');
const { spawn } = require('child_process');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

// ─── Paths ────────────────────────────────────────────────────────────────────
const DLL_PATH = path.join(__dirname, 'libs', 'DepotDownloaderMod.dll');
const CONFIG_PATH = path.join(os.homedir(), 'Downloads', 'ddgui_config.json');
const BASE = 'https://manifest.morrenus.xyz/api/v1';

// ─── Config ───────────────────────────────────────────────────────────────────
function loadConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8')); }
  catch { return {}; }
}
function saveConfig(cfg) {
  try { fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2)); }
  catch {}
}

// ─── HTTP helper ──────────────────────────────────────────────────────────────
function fetchUrl(url, options = {}) {
  return new Promise((resolve, reject) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.get(url, { headers: { 'User-Agent': 'DDGui/4', ...options.headers } }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        const buf = Buffer.concat(chunks);
        if (res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
        } else {
          resolve({ buffer: buf, text: buf.toString('utf8'), status: res.statusCode });
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => { req.destroy(); reject(new Error('Request timed out')); });
  });
}

// ─── Lua parser ───────────────────────────────────────────────────────────────
function parseLua(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const depots = {};
  // parse keys
  for (const m of text.matchAll(/addappid\(\s*(\d+)\s*,\s*\d+\s*,\s*"([0-9a-fA-F]+)"\s*\)/g)) {
    const [, d, k] = m;
    if (!depots[d]) depots[d] = { key: null, manifest: null };
    depots[d].key = k;
  }
  // plain appids
  for (const m of text.matchAll(/addappid\(\s*(\d+)\s*\)/g)) {
    if (!depots[m[1]]) depots[m[1]] = { key: null, manifest: null };
  }
  // manifest ids
  for (const m of text.matchAll(/setManifestid\(\s*(\d+)\s*,\s*"(\d+)"\s*\)/g)) {
    const [, d, v] = m;
    if (!depots[d]) depots[d] = { key: null, manifest: null };
    depots[d].manifest = v;
  }
  return depots;
}

function parseManifestFilename(fn) {
  const m = path.basename(fn).match(/^[a-zA-Z]*(\d+)_(\d+)\.manifest$/);
  return m ? [m[1], m[2]] : [null, null];
}

function writeTempKeyfile(luaDepots) {
  const lines = Object.entries(luaDepots)
    .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
    .filter(([, i]) => i.key)
    .map(([d, i]) => `${d};${i.key}`);
  if (!lines.length) return null;
  const tmp = path.join(os.tmpdir(), `ddgui_${Date.now()}.key`);
  fs.writeFileSync(tmp, lines.join('\n'));
  return tmp;
}

// ─── ZIP extraction (manual, no dependency) ───────────────────────────────────
function extractZip(zipBuf, destDir) {
  // Write temp zip
  const zipPath = path.join(destDir, 'dl.zip');
  fs.writeFileSync(zipPath, zipBuf);

  // Try using system unzip / powershell
  return new Promise((resolve, reject) => {
    let cmd, args;
    if (process.platform === 'win32') {
      cmd = 'powershell';
      args = ['-NoProfile', '-Command',
        `Expand-Archive -Path "${zipPath}" -DestinationPath "${destDir}" -Force`];
    } else {
      cmd = 'unzip';
      args = ['-o', zipPath, '-d', destDir];
    }
    const p = spawn(cmd, args);
    p.on('close', code => {
      try { fs.unlinkSync(zipPath); } catch {}
      if (code === 0) resolve();
      else reject(new Error(`Extraction failed (exit ${code})`));
    });
    p.on('error', reject);
  });
}

// ─── API calls ────────────────────────────────────────────────────────────────
async function apiSearch(key, q) {
  const steamUrl = `https://store.steampowered.com/api/storesearch/?term=${encodeURIComponent(q)}&cc=US&l=english`;
  const manifestUrl = `${BASE}/search?api_key=${encodeURIComponent(key)}&q=${encodeURIComponent(q)}`;

  let steamData = {};
  try {
    const r = await fetchUrl(steamUrl);
    const items = JSON.parse(r.text).items || [];
    for (const item of items) {
      if (item.id && item.tiny_image) steamData[String(item.id)] = item.tiny_image;
    }
  } catch {}

  const r = await fetchUrl(manifestUrl);
  const data = JSON.parse(r.text);
  const results = data.results || (Array.isArray(data) ? data : []);
  for (const result of results) {
    const gid = String(result.game_id || '');
    result.tiny_image = steamData[gid] || '';
  }
  return results;
}

async function apiUserStats(key) {
  const r = await fetchUrl(`${BASE}/user/stats?api_key=${encodeURIComponent(key)}`);
  return JSON.parse(r.text);
}

async function apiFetchZip(key, appId, dest) {
  const url = `${BASE}/manifest/${appId}?api_key=${encodeURIComponent(key)}`;
  const r = await fetchUrl(url);
  const folder = path.join(dest, `app_${appId}`);
  fs.mkdirSync(folder, { recursive: true });
  await extractZip(r.buffer, folder);

  const luas = [], manifests = [];
  function walk(dir) {
    for (const fn of fs.readdirSync(dir)) {
      const full = path.join(dir, fn);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (fn.endsWith('.lua')) luas.push(full);
      else if (fn.endsWith('.manifest')) manifests.push(full);
    }
  }
  walk(folder);
  return { folder, luas, manifests };
}

// ─── Image fetcher (returns base64 data URL) ──────────────────────────────────
async function fetchImageBase64(url) {
  const r = await fetchUrl(url);
  const mime = 'image/jpeg';
  return `data:${mime};base64,${r.buffer.toString('base64')}`;
}

// ─── Active child process ─────────────────────────────────────────────────────
let activeProc = null;

// ─── IPC Handlers ─────────────────────────────────────────────────────────────
ipcMain.handle('config:load', () => loadConfig());
ipcMain.handle('config:save', (_, cfg) => { saveConfig(cfg); return true; });

ipcMain.handle('dialog:pickDir', async () => {
  const win = BrowserWindow.getFocusedWindow();
  const res = await dialog.showOpenDialog(win, { properties: ['openDirectory'] });
  return res.canceled ? null : res.filePaths[0];
});

ipcMain.handle('api:search', async (_, key, q) => {
  return await apiSearch(key, q);
});

ipcMain.handle('api:userStats', async (_, key) => {
  return await apiUserStats(key);
});

ipcMain.handle('api:fetchZip', async (_, key, appId, dest) => {
  return await apiFetchZip(key, appId, dest);
});

ipcMain.handle('fs:parseLua', (_, luaPath) => {
  return parseLua(luaPath);
});

ipcMain.handle('fs:readFile', (_, filePath) => {
  return fs.readFileSync(filePath);
});

ipcMain.handle('image:fetch', async (_, url) => {
  try { return await fetchImageBase64(url); }
  catch { return null; }
});

ipcMain.handle('fs:clearDir', (_, dirPath) => {
  if (!fs.existsSync(dirPath)) return 0;
  let count = 0;
  function walk(d) {
    for (const fn of fs.readdirSync(d)) {
      const full = path.join(d, fn);
      if (fs.statSync(full).isDirectory()) { walk(full); try { fs.rmdirSync(full); } catch {} }
      else { fs.unlinkSync(full); count++; }
    }
  }
  walk(dirPath);
  return count;
});

ipcMain.handle('downloader:run', (event, opts) => {
  const { dotnet, cmd } = opts;
  return new Promise((resolve) => {
    const win = BrowserWindow.fromWebContents(event.sender);

    // Buffer log lines and flush every 100ms so UI doesn't repaint on every byte
    let logBuffer = '';
    let flushTimer = null;
    function flushLog() {
      if (logBuffer) {
        win.webContents.send('log:line', logBuffer);
        logBuffer = '';
      }
    }

    activeProc = spawn(dotnet, cmd, { windowsVerbatimArguments: false });
    activeProc.stdout.on('data', d => {
      logBuffer += d.toString();
      if (!flushTimer) flushTimer = setInterval(flushLog, 100);
    });
    activeProc.stderr.on('data', d => {
      logBuffer += d.toString();
      if (!flushTimer) flushTimer = setInterval(flushLog, 100);
    });
    activeProc.on('close', code => {
      clearInterval(flushTimer);
      flushLog(); // flush remaining
      activeProc = null;
      resolve(code);
    });
    activeProc.on('error', err => {
      clearInterval(flushTimer);
      flushLog();
      activeProc = null;
      win.webContents.send('log:line', `\nError: ${err.message}\n`);
      resolve(-1);
    });
  });
});

ipcMain.handle('downloader:stop', () => {
  if (activeProc) { activeProc.kill(); activeProc = null; }
});

ipcMain.handle('util:which', (_, name) => {
  // Simple which implementation
  const dirs = (process.env.PATH || '').split(path.delimiter);
  const exts = process.platform === 'win32' ? ['.exe', '.cmd', '.bat', ''] : [''];
  for (const dir of dirs) {
    for (const ext of exts) {
      const full = path.join(dir, name + ext);
      try { fs.accessSync(full, fs.constants.X_OK); return full; } catch {}
    }
  }
  return null;
});

ipcMain.handle('util:dllExists', () => fs.existsSync(DLL_PATH));
ipcMain.handle('util:dllPath', () => DLL_PATH);
ipcMain.handle('util:tempKeyfile', (_, luaDepots) => writeTempKeyfile(luaDepots));
ipcMain.handle('util:deleteTempFile', (_, p) => { try { fs.unlinkSync(p); } catch {} });
ipcMain.handle('util:defaultManifestDir', () =>
  path.join(path.dirname(app.getAppPath()), 'Manifests'));

// ─── Window ───────────────────────────────────────────────────────────────────
function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 700,
    minWidth: 860,
    minHeight: 600,
    backgroundColor: '#0d0d14',
    frame: false,
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

// Window controls via IPC
ipcMain.on('window:minimize', () => BrowserWindow.getFocusedWindow()?.minimize());
ipcMain.on('window:maximize', () => {
  const w = BrowserWindow.getFocusedWindow();
  w?.isMaximized() ? w.unmaximize() : w?.maximize();
});
ipcMain.on('window:close', () => BrowserWindow.getFocusedWindow()?.close());
