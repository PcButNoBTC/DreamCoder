/**
 * DreamCoder desktop shell (Electron)
 *
 * Starts a local Python backend if possible, then loads the frontend.
 * Run from the electron/ folder after `npm install`.
 */

const { app, BrowserWindow, shell, dialog, ipcMain } = require("electron");
const { autoUpdater } = require("electron-updater");
const path = require("path");
const { spawn } = require("child_process");\nconst http = require("http");

let mainWindow = null;
let backendProc = null;
let backendReady = false;
app.setName("DreamCoder");

const BACKEND_PORT = 8000;
const FRONTEND = path.join(__dirname, "..", "frontend", "index.html");

function startBackend() {
  const backendDir = path.join(__dirname, "..", "backend");
  // Prefer python -m uvicorn so PATH issues are avoided on Windows
  const cmd = process.platform === "win32" ? "python" : "python3";
  backendProc = spawn(
    cmd,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    { cwd: backendDir, shell: false, stdio: "pipe", windowsHide: true }
  );
  backendProc.stdout.on("data", (d) => console.log(`[backend] ${d}`));
  backendProc.stderr.on("data", (d) => console.error(`[backend] ${d}`));
  backendProc.on("exit", (code) => { backendReady=false; console.log(`backend exited ${code}`); if(mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("dreamcoder:backend-exit", code); });
}

ipcMain.handle("dreamcoder:choose-folder", async () => {\n  const result = await dialog.showOpenDialog({ properties: ["openDirectory", "createDirectory"] });\n  return result.canceled ? null : result.filePaths[0];\n});\n\nfunction waitForBackend(attempt = 0) {\n  if (attempt > 30) return createWindow();\n  const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/`, (res) => {\n    res.resume();\n    createWindow();\n  });\n  req.on("error", () => setTimeout(() => waitForBackend(attempt + 1), 250));\n  req.setTimeout(250, () => req.destroy());\n}\n\nfunction createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: "#0b0e14",
    title: "DreamCoder",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Inject API base so the UI talks to the local backend
  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.executeJavaScript(
      `window.DREAMCODER_API = "http://127.0.0.1:${BACKEND_PORT}";`
    );
  });

  mainWindow.loadFile(FRONTEND);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  startBackend();
  // small delay so uvicorn can bind
  waitForBackend();
  if (app.isPackaged && process.env.DREAMCODER_DISABLE_UPDATES !== "1") { autoUpdater.checkForUpdatesAndNotify().catch(err => console.warn("update check failed", err)); }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("before-quit", () => { if (backendProc) { try { backendProc.kill("SIGTERM"); } catch (_) {} } });

app.on("window-all-closed", () => {
  if (backendProc) {
    backendProc.kill();
    backendProc = null;
  }
  if (process.platform !== "darwin") app.quit();
});
