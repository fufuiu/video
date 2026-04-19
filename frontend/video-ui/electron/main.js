const { app, BrowserWindow, ipcMain, globalShortcut } = require('electron')
const path = require('path')

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow
let isQuitting = false

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    frame: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      devTools: true
    },
    icon: path.join(__dirname, '../public/icon.png')
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173').catch(() => {
      mainWindow.loadURL('http://localhost:5174')
    })
    // 开发模式下不自动打开 DevTools，可以按 F12 手动打开
    // mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return
    const ctrl = input.control || input.meta

    if (input.key === 'F12') {
      mainWindow?.webContents.toggleDevTools()
      event.preventDefault()
    } else if (input.key === 'F11') {
      if (mainWindow) {
        mainWindow.setFullScreen(!mainWindow.isFullScreen())
      }
      event.preventDefault()
    } else if (input.key === 'F5' || (ctrl && input.key === 'r')) {
      mainWindow?.reload()
      event.preventDefault()
    } else if (ctrl && input.key === 'w') {
      mainWindow?.hide()
      event.preventDefault()
    } else if (ctrl && input.shift && input.key === 'q') {
      isQuitting = true
      app.quit()
      event.preventDefault()
    } else if (ctrl && input.key === 'q') {
      mainWindow?.hide()
      event.preventDefault()
    }
  })

  app.on('browser-window-focus', () => {
    globalShortcut.register('Alt+Left', () => {
      if (mainWindow?.webContents.canGoBack()) {
        mainWindow.webContents.goBack()
      }
    })
    globalShortcut.register('Alt+Right', () => {
      if (mainWindow?.webContents.canGoForward()) {
        mainWindow.webContents.goForward()
      }
    })
  })

  app.on('browser-window-blur', () => {
    globalShortcut.unregisterAll()
  })

  // Keep app alive on close so dev services are not terminated implicitly.
  mainWindow.on('close', (event) => {
    if (isQuitting) return
    event.preventDefault()
    mainWindow.hide()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

ipcMain.on('window-minimize', () => {
  mainWindow?.minimize()
})

ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})

ipcMain.on('window-close', () => {
  mainWindow?.hide()
})

ipcMain.handle('window-is-maximized', () => {
  return mainWindow?.isMaximized()
})

ipcMain.handle('window-is-fullscreen', () => {
  return mainWindow?.isFullScreen()
})

ipcMain.on('nav-back', () => {
  if (mainWindow?.webContents.canGoBack()) {
    mainWindow.webContents.goBack()
  }
})

ipcMain.on('nav-forward', () => {
  if (mainWindow?.webContents.canGoForward()) {
    mainWindow.webContents.goForward()
  }
})

ipcMain.handle('nav-can-go-back', () => {
  return mainWindow?.webContents.canGoBack() || false
})

ipcMain.handle('nav-can-go-forward', () => {
  return mainWindow?.webContents.canGoForward() || false
})

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) mainWindow.show()
      mainWindow.focus()
      return
    }

    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  isQuitting = true
})

app.on('window-all-closed', () => {
  // Keep process alive on all platforms; explicit quit closes app.
})
