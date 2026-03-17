const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // Config
  loadConfig:       ()          => ipcRenderer.invoke('config:load'),
  saveConfig:       (cfg)       => ipcRenderer.invoke('config:save', cfg),

  // Dialog
  pickDir:          ()          => ipcRenderer.invoke('dialog:pickDir'),

  // API
  search:           (key, q)    => ipcRenderer.invoke('api:search', key, q),
  userStats:        (key)       => ipcRenderer.invoke('api:userStats', key),
  fetchZip:         (k, id, d)  => ipcRenderer.invoke('api:fetchZip', k, id, d),

  // FS
  parseLua:         (p)         => ipcRenderer.invoke('fs:parseLua', p),
  clearDir:         (p)         => ipcRenderer.invoke('fs:clearDir', p),

  // Image
  fetchImage:       (url)       => ipcRenderer.invoke('image:fetch', url),

  // Downloader
  runDownloader:    (opts)      => ipcRenderer.invoke('downloader:run', opts),
  stopDownloader:   ()          => ipcRenderer.invoke('downloader:stop'),
  onLogLine:        (cb)        => ipcRenderer.on('log:line', (_, line) => cb(line)),

  // Utils
  which:            (n)         => ipcRenderer.invoke('util:which', n),
  dllExists:        ()          => ipcRenderer.invoke('util:dllExists'),
  dllPath:          ()          => ipcRenderer.invoke('util:dllPath'),
  tempKeyfile:      (d)         => ipcRenderer.invoke('util:tempKeyfile', d),
  deleteTempFile:   (p)         => ipcRenderer.invoke('util:deleteTempFile', p),
  defaultManifestDir: ()        => ipcRenderer.invoke('util:defaultManifestDir'),

  // Window controls
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close:    () => ipcRenderer.send('window:close'),
});
