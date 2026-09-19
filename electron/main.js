const { app, BrowserWindow, shell, dialog, ipcMain } = require("electron");
const { autoUpdater } = require("electron-updater");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

let mainWindow = null;
let backendProc = null;
const BACKEND_PORT = Number(process.env.DREAMCODER_BACKEND_PORT || 8000);
const FRONTEND = path.join(__dirname, "..", "frontend", "index.html");

function startBackend() {
  if (app.isPackaged) {
    const exe = path.join(process.resourcesPath, "backend", process.platform === "win32" ? "dreamcoder-backend.exe" : "dreamcoder-backend");
    backendProc = spawn(exe, ["--host", "127.0.0.1", "--port", String(BACKEND_PORT)], { cwd: process.resourcesPath, shell:false, stdio:"pipe", windowsHide:true });
  } else {
    const backendDir = path.join(__dirname, "..", "backend");
    const cmd = process.platform === "win32" ? "python" : "python3";
    backendProc = spawn(cmd, ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)], { cwd: backendDir, shell:false, stdio:"pipe", windowsHide:true });
  }
  backendProc.stdout.on("data", d => console.log("[backend]", String(d)));
  backendProc.stderr.on("data", d => console.error("[backend]", String(d)));
  backendProc.on("exit", code => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("dreamcoder:backend-exit", code);
  });
}

ipcMain.handle("dreamcoder:choose-folder", async () => {
  const result = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });
  return result.canceled ? null : result.filePaths[0];
});

function waitForBackend(attempt = 0) {
  if (attempt > 60) return createWindow();
  const req = http.get("http://127.0.0.1:" + BACKEND_PORT + "/", res => {
    res.resume();
    createWindow();
  });
  req.on("error", () => setTimeout(() => waitForBackend(attempt + 1), 250));
  req.setTimeout(500, () => req.destroy());
}

function createWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) return;
  mainWindow = new BrowserWindow({
    width: 1400, height: 900, minWidth: 900, minHeight: 600,
    title: "DreamCoder", backgroundColor: "#0b0e14",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true, nodeIntegration: false, sandbox: true
    }
  });
  mainWindow.loadFile(FRONTEND);
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.executeJavaScript(
      "window.DREAMCODER_API = 'http://127.0.0.1:" + BACKEND_PORT + "';"
    ).catch(() => {});
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:$/i.test(new URL(url).protocol)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(() => {
  if (!app.requestSingleInstanceLock()) { app.quit(); return; }
  startBackend();
  waitForBackend();
  if (app.isPackaged && process.env.DREAMCODER_DISABLE_UPDATES !== "1") {
    autoUpdater.autoDownload = false;
    autoUpdater.on("update-available", info => {
      if (mainWindow) mainWindow.webContents.send("dreamcoder:update-available", {version:info.version});
      autoUpdater.downloadUpdate().catch(err => console.warn("update download failed", err));
    });
    autoUpdater.on("update-downloaded", info => {
      if (mainWindow) mainWindow.webContents.send("dreamcoder:update-ready", {version:info.version});
    });
    autoUpdater.checkForUpdates().catch(err => console.warn("update check failed", err));
  }
  app.on("second-instance", () => {
    if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); }
  });
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) waitForBackend(); });
});

ipcMain.handle("dreamcoder:install-update", async () => { autoUpdater.quitAndInstall(false,true); return {ok:true}; });

app.on("before-quit", () => {
  if (backendProc) { try { backendProc.kill(); } catch (_) {} backendProc = null; }
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
