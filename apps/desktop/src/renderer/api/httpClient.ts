import type { ApiResponse } from "../types";
import {
  getPortalToken,
  type Portal
} from "../auth/portalSession";


export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}


function networkError(): ApiRequestError {
  return new ApiRequestError(
    "无法连接本地服务，请确认后端已启动后重试。",
    "NETWORK_ERROR",
    0
  );
}


export function createPortalRequest(portal: Portal) {
  return async function request<T>(
    path: string,
    init?: RequestInit
  ): Promise<T> {
    const token = getPortalToken(portal);
    const isFormData = init?.body instanceof FormData;
    let response: Response;
    try {
      response = await fetch(path, {
        ...init,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(init?.headers ?? {})
        }
      });
    } catch {
      throw networkError();
    }
    let body: ApiResponse<T>;
    if (typeof response.text === "function") {
      const rawBody = await response.text();
      if (!rawBody.trim()) {
        throw new ApiRequestError(
          "服务暂时没有返回内容，请稍后重试",
          "EMPTY_RESPONSE",
          response.status
        );
      }
      try {
        body = JSON.parse(rawBody) as ApiResponse<T>;
      } catch {
        throw new ApiRequestError(
          "服务返回格式异常，请稍后重试",
          "INVALID_RESPONSE",
          response.status
        );
      }
    } else {
      body = (await response.json()) as ApiResponse<T>;
    }
    if (!response.ok || !body.success) {
      throw new ApiRequestError(
        body.error?.message || "请求未完成",
        body.error?.code || "REQUEST_FAILED",
        response.status
      );
    }
    return body.data;
  };
}


export function createPortalBlobRequest(portal: Portal) {
  return async function requestBlob(
    path: string,
    init?: RequestInit
  ): Promise<Blob> {
    const token = getPortalToken(portal);
    let response: Response;
    try {
      response = await fetch(path, {
        ...init,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(init?.headers ?? {})
        }
      });
    } catch {
      throw networkError();
    }
    if (!response.ok) {
      let message = "素材预览加载失败";
      let code = "REQUEST_FAILED";
      try {
        const body = (await response.json()) as ApiResponse<unknown>;
        message = body.error?.message || message;
        code = body.error?.code || code;
      } catch {
        // Binary endpoints may return a non-JSON infrastructure error.
      }
      throw new ApiRequestError(message, code, response.status);
    }
    return response.blob();
  };
}
