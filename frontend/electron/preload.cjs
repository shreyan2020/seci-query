const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktopApp', {
  platform: process.platform,
  name: 'SECI Persona Studio',
  openPath: (targetPath) => ipcRenderer.invoke('open-path', targetPath),
});
