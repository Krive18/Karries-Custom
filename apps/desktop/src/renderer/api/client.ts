const API_BASE = "http://127.0.0.1:8765";


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  const body = await response.json();
  if (!response.ok || !body.success) {
    throw new Error(body.error?.message || "请求失败");
  }
  return body.data as T;
}


export const api = {
  checkRuntime: () => request<Record<string, unknown>>("/api/runtime/check"),
  generateImageCopy: (payload: unknown) =>
    request<Record<string, unknown>>("/api/ai/image-copy", {
      method: "POST",
      body: JSON.stringify(payload)
    })
};
