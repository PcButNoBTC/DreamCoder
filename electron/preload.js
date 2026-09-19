// Reserved for future secure bridge between Electron and the renderer.
// For now the UI talks to the local FastAPI backend over HTTP/WS.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("dreamcoderDesktop", {
  isDesktop: true,
  platform: process.platform,
});
