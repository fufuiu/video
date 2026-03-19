"use strict";
const { app, BrowserWindow, ipcMain, globalShortcut } = require("electron");
const path = require("path");
const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
let mainWindow;
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1e3,
    minHeight: 700,
    frame: false,
    autoHideMenuBar: true,
    // 自动隐藏菜单栏
    titleBarStyle: "hidden",
    // 隐藏原生标题栏
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
      devTools: true
    },
    icon: path.join(__dirname, "../public/icon.png")
  });
  if (isDev) {
    mainWindow.loadURL("http://localhost:5173").catch(() => {
      mainWindow.loadURL("http://localhost:5174");
    });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
  app.on("browser-window-focus", () => {
    globalShortcut.register("F12", () => {
      mainWindow?.webContents.toggleDevTools();
    });
    globalShortcut.register("F11", () => {
      if (mainWindow) {
        const isFullScreen = mainWindow.isFullScreen();
        mainWindow.setFullScreen(!isFullScreen);
      }
    });
    globalShortcut.register("CommandOrControl+R", () => {
      mainWindow?.reload();
    });
    globalShortcut.register("F5", () => {
      mainWindow?.reload();
    });
    globalShortcut.register("Alt+Left", () => {
      if (mainWindow?.webContents.canGoBack()) {
        mainWindow.webContents.goBack();
      }
    });
    globalShortcut.register("Alt+Right", () => {
      if (mainWindow?.webContents.canGoForward()) {
        mainWindow.webContents.goForward();
      }
    });
    globalShortcut.register("CommandOrControl+W", () => {
      if (mainWindow) {
        mainWindow.hide();
      }
    });
    globalShortcut.register("CommandOrControl+Q", () => {
      app.exit(0);
    });
  });
  app.on("browser-window-blur", () => {
    globalShortcut.unregisterAll();
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}
ipcMain.on("window-minimize", () => {
  mainWindow?.minimize();
});
ipcMain.on("window-maximize", () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on("window-close", () => {
  mainWindow?.hide();
});
ipcMain.handle("window-is-maximized", () => {
  return mainWindow?.isMaximized();
});
ipcMain.handle("window-is-fullscreen", () => {
  return mainWindow?.isFullScreen();
});
ipcMain.on("nav-back", () => {
  if (mainWindow?.webContents.canGoBack()) {
    mainWindow.webContents.goBack();
  }
});
ipcMain.on("nav-forward", () => {
  if (mainWindow?.webContents.canGoForward()) {
    mainWindow.webContents.goForward();
  }
});
ipcMain.handle("nav-can-go-back", () => {
  return mainWindow?.webContents.canGoBack() || false;
});
ipcMain.handle("nav-can-go-forward", () => {
  return mainWindow?.webContents.canGoForward() || false;
});
app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
