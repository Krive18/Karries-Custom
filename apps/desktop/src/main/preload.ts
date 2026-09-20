import { contextBridge, ipcRenderer } from "electron";


contextBridge.exposeInMainWorld("karriesPublisher", {
  version: "0.1.0",
  selectMaterials: () => ipcRenderer.invoke("materials:select") as Promise<string[]>
});
