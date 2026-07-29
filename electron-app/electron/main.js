'use strict';

/**
 * electron/main.js
 *
 * Audio capture is now done entirely in the renderer via Web Audio API
 * + Electron's built-in WASAPI loopback (setDisplayMediaRequestHandler).
 * No native modules (naudiodon) — no compilation, no SIGSEGV.
 */

const { app, BrowserWindow, Menu, ipcMain, shell, session, desktopCapturer, safeStorage } = require('electron');
const path  = require('path');
const fs    = require('fs');
const https = require('https');
const http  = require('http');

let mainWindow  = null;
let backendUrl  = 'http://localhost:8000';

function tokenPath() {
  return path.join(app.getPath('userData'), 'auth-token.bin');
}

function saveToken(token) {
  const content = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(token)
    : Buffer.from(token, 'utf8');
  fs.writeFileSync(tokenPath(), content);
}

function readToken() {
  try {
    const content = fs.readFileSync(tokenPath());
    return safeStorage.isEncryptionAvailable()
      ? safeStorage.decryptString(content)
      : content.toString('utf8');
  } catch {
    return null;
  }
}

function clearToken() {
  try {
    fs.rmSync(tokenPath(), { force: true });
  } catch {
    // Nothing to clear.
  }
}

function installMenu() {
  const menu = Menu.buildFromTemplate([
    {
      label: 'MeetFlow',
      submenu: [
        {
          label: 'Sign out',
          click: () => {
            clearToken();
            mainWindow?.webContents.send('auth-sign-out');
          },
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
  ]);
  Menu.setApplicationMenu(menu);
}

// ------------------------------------------------------------------
// WASAPI loopback: tell Chromium to use Windows system audio
// Must be set BEFORE the window loads so getDisplayMedia works.
// ------------------------------------------------------------------
function enableLoopbackHandler() {
  session.defaultSession.setDisplayMediaRequestHandler((request, callback) => {
    desktopCapturer.getSources({ types: ['screen'] }).then((sources) => {
      // video is required by the API but we discard it in the renderer
      callback({ video: sources[0], audio: 'loopback' });
    }).catch(() => callback({}));
  });
}

// ------------------------------------------------------------------
// Window
// ------------------------------------------------------------------
function loadDevServerWithRetry(win, url, attempt = 0) {
  win.loadURL(url).catch(() => {
    if (win.isDestroyed() || attempt >= 60) return;
    setTimeout(() => loadDevServerWithRetry(win, url, attempt + 1), 500);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width:  1280,
    height: 820,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          false,
    },
    title: 'MeetFlow Desktop',
    show:  false,
    backgroundColor: '#0f172a',
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

  if (isDev) {
    loadDevServerWithRetry(mainWindow, 'http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  // Set loopback handler before any window loads
  enableLoopbackHandler();
  installMenu();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ------------------------------------------------------------------
// IPC: Settings
// ------------------------------------------------------------------
ipcMain.handle('set-backend-url', (_, url) => {
  backendUrl = url.replace(/\/$/, '');
  return { ok: true };
});

ipcMain.handle('get-backend-url', () => backendUrl);

ipcMain.handle('auth-token:get', () => readToken());
ipcMain.handle('auth-token:set', (_, token) => {
  saveToken(token);
  return { ok: true };
});
ipcMain.handle('auth-token:clear', () => {
  clearToken();
  return { ok: true };
});

// ------------------------------------------------------------------
// IPC: Health check
// ------------------------------------------------------------------
ipcMain.handle('check-backend', async () => {
  try {
    const url = new URL(`${backendUrl}/health`);
    const lib = url.protocol === 'https:' ? https : http;
    return await new Promise((resolve) => {
      const req = lib.get(
        { hostname: url.hostname, port: url.port || 8000, path: '/health', timeout: 4000 },
        (res) => {
          let d = '';
          res.on('data', (c) => { d += c; });
          res.on('end', () => resolve({ ok: res.statusCode === 200, body: d }));
        },
      );
      req.on('error',   (e) => resolve({ ok: false, error: e.message }));
      req.on('timeout', ()  => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
    });
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ------------------------------------------------------------------
// IPC: Push transcript entries from renderer → renderer
// (renderer calls this after a successful chunk POST)
// ------------------------------------------------------------------
ipcMain.handle('transcript-chunk-result', (_, data) => {
  mainWindow?.webContents.send('transcript-update', data);
  return { ok: true };
});

ipcMain.handle('capture-error', (_, msg) => {
  mainWindow?.webContents.send('capture-error', msg);
  return { ok: true };
});
