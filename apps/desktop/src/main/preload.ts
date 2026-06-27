import { contextBridge } from "electron";


contextBridge.exposeInMainWorld("karriesPublisher", {
  version: "0.1.0"
});
