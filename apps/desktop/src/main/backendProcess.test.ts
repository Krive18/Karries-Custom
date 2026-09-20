import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";


const mocks = vi.hoisted(() => ({
  spawn: vi.fn(),
  kill: vi.fn(),
  once: vi.fn()
}));


vi.mock("node:child_process", () => ({
  default: { spawn: mocks.spawn },
  spawn: mocks.spawn
}));


import { startBackend, stopBackend } from "./backendProcess";


describe("backendProcess", () => {
  beforeEach(() => {
    process.env.BACKEND_API_URL = "http://api.internal:9080";
    mocks.once.mockReturnValue(undefined);
    mocks.spawn.mockReturnValue({ kill: mocks.kill, once: mocks.once });
  });

  afterEach(() => {
    stopBackend();
    mocks.spawn.mockReset();
    mocks.kill.mockReset();
    mocks.once.mockReset();
    delete process.env.BACKEND_API_URL;
  });

  it("starts the FastAPI backend on the configured address", () => {
    startBackend();

    expect(mocks.spawn).toHaveBeenCalledWith(
      expect.stringMatching(/(?:python|python\.exe)$/),
      ["-m", "uvicorn", "app.main:app", "--host", "api.internal", "--port", "9080"],
      expect.objectContaining({
        cwd: expect.stringMatching(/backend$/),
        stdio: "ignore",
        windowsHide: true,
        env: expect.objectContaining({
          BACKEND_API_URL: "http://api.internal:9080",
          XHS_EMBEDDED_PUBLISH_WORKER: "1",
          XHS_WORKER_HEADLESS: "1",
          WORKER_API_TOKEN: expect.stringMatching(/^[a-f0-9]{64}$/)
        })
      })
    );
  });

  it("does not start a second backend process while one is running", () => {
    startBackend();
    startBackend();

    expect(mocks.spawn).toHaveBeenCalledTimes(1);
  });

  it("warns and skips spawning when BACKEND_API_URL is not configured", () => {
    delete process.env.BACKEND_API_URL;
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(() => startBackend()).not.toThrow();

    expect(mocks.spawn).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("BACKEND_API_URL")
    );
    warn.mockRestore();
  });

  it("warns and skips spawning when BACKEND_API_URL is invalid", () => {
    process.env.BACKEND_API_URL = "not-a-url";
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    expect(() => startBackend()).not.toThrow();

    expect(mocks.spawn).not.toHaveBeenCalled();
    warn.mockRestore();
  });

  it("allows starting the backend again after a skipped start", () => {
    delete process.env.BACKEND_API_URL;
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    startBackend();
    warn.mockRestore();

    process.env.BACKEND_API_URL = "http://api.internal:9080";
    startBackend();

    expect(mocks.spawn).toHaveBeenCalledTimes(1);
  });

  it("kills the backend process when stopped", () => {
    startBackend();

    stopBackend();

    expect(mocks.kill).toHaveBeenCalledTimes(1);
  });
});
