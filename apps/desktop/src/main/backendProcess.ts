import { spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";


let backendProcess: ChildProcess | null = null;
const generatedWorkerToken = randomBytes(32).toString("hex");


function backendDirectory() {
  return path.resolve(__dirname, "../../../..", "backend");
}

function pythonExecutable() {
  const projectPython = path.resolve(
    backendDirectory(),
    "..",
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python"
  );
  return existsSync(projectPython) ? projectPython : "python";
}

function configuredBackendUrl(): URL {
  const rawUrl = process.env.BACKEND_API_URL?.trim();
  if (!rawUrl) {
    throw new Error("BACKEND_API_URL must be configured before starting the embedded backend");
  }
  const url = new URL(rawUrl);
  if (url.protocol !== "http:" || !url.hostname || !url.port) {
    throw new Error("BACKEND_API_URL must be an HTTP URL with an explicit port");
  }
  return url;
}

function backendEnvironment(url: URL): NodeJS.ProcessEnv {
  return {
    ...process.env,
    BACKEND_API_URL: url.origin,
    XHS_EMBEDDED_PUBLISH_WORKER: "1",
    XHS_WORKER_HEADLESS: "1",
    WORKER_API_TOKEN: process.env.WORKER_API_TOKEN?.trim() || generatedWorkerToken
  };
}


export function startBackend() {
  if (backendProcess) {
    return;
  }

  let backendUrl: URL;
  try {
    backendUrl = configuredBackendUrl();
  } catch (configError) {
    console.warn(
      `[backend] embedded backend disabled: ${
        configError instanceof Error ? configError.message : String(configError)
      }`
    );
    return;
  }
  backendProcess = spawn(
    pythonExecutable(),
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      backendUrl.hostname,
      "--port",
      backendUrl.port
    ],
    {
      cwd: backendDirectory(),
      env: backendEnvironment(backendUrl),
      stdio: "ignore",
      windowsHide: true
    }
  );

  backendProcess.once("error", (spawnError) => {
    console.warn(`[backend] embedded backend failed to start: ${spawnError.message}`);
    backendProcess = null;
  });

  backendProcess.once("exit", () => {
    backendProcess = null;
  });
}


export function stopBackend() {
  if (!backendProcess) {
    return;
  }

  backendProcess.kill();
  backendProcess = null;
}
