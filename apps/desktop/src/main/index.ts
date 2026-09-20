import { BrowserWindow, app, dialog, ipcMain } from "electron";
import path from "node:path";

import { startBackend, stopBackend } from "./backendProcess";


ipcMain.handle("materials:select", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择图片/视频素材",
    properties: ["openFile", "multiSelections"],
    filters: [
      { name: "素材文件", extensions: ["jpg", "jpeg", "png", "webp", "bmp", "mp4", "mov", "webm"] },
      { name: "图片", extensions: ["jpg", "jpeg", "png", "webp", "bmp"] },
      { name: "视频", extensions: ["mp4", "mov", "webm"] }
    ]
  });

  return result.canceled ? [] : result.filePaths;
});


async function createWindow() {
  startBackend();

  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: "#f7f2eb",
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await win.loadFile(path.join(__dirname, "../customer-renderer/index.html"));
  }
}


app.whenReady().then(createWindow);

app.on("before-quit", stopBackend);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createWindow();
  }
});
