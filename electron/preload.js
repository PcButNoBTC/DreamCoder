const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("dreamcoderDesktop", {
  isDesktop: true,
  platform: process.platform,
  chooseFolder: () => ipcRenderer.invoke("dreamcoder:choose-folder"),
  installUpdate: () => ipcRenderer.invoke("dreamcoder:install-update"),
  onUpdateReady: (fn) => ipcRenderer.on("dreamcoder:update-ready", (_e, info) => fn(info))
});
