const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("dreamcoderDesktop", {
  isDesktop: true,
  platform: process.platform,
  chooseFolder: () => ipcRenderer.invoke("dreamcoder:choose-folder")
});
