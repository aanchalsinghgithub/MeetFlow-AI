'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Settings
  setBackendUrl:  (url) => ipcRenderer.invoke('set-backend-url', url),
  getBackendUrl:  ()    => ipcRenderer.invoke('get-backend-url'),
  checkBackend:   ()    => ipcRenderer.invoke('check-backend'),

  // Flag so renderer knows it is inside Electron (loopback available)
  isElectron: true,

  // Renderer calls these to relay results back through main → renderer
  // (only needed if multiple windows existed; kept for symmetry)
  reportTranscriptChunk: (data) => ipcRenderer.invoke('transcript-chunk-result', data),
  reportCaptureError:    (msg)  => ipcRenderer.invoke('capture-error', msg),

  // Events: main → renderer
  onTranscriptUpdate: (cb) => {
    const fn = (_, d) => cb(d);
    ipcRenderer.on('transcript-update', fn);
    return () => ipcRenderer.removeListener('transcript-update', fn);
  },
  onCaptureError: (cb) => {
    const fn = (_, m) => cb(m);
    ipcRenderer.on('capture-error', fn);
    return () => ipcRenderer.removeListener('capture-error', fn);
  },
});
