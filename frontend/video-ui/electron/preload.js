const { contextBridge, ipcRenderer } = require('electron')

// 暴露安全的 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 窗口控制
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  maximizeWindow: () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),
  quitApp: () => ipcRenderer.send('window-close'), // 暴露关闭窗口方法
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  
  // 导航控制
  goBack: () => ipcRenderer.send('nav-back'),
  goForward: () => ipcRenderer.send('nav-forward'),
  canGoBack: () => ipcRenderer.invoke('nav-can-go-back'),
  canGoForward: () => ipcRenderer.invoke('nav-can-go-forward'),
  isFullScreen: () => ipcRenderer.invoke('window-is-fullscreen')
})
