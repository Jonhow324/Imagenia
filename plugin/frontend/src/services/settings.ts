/** QwenPaw 2.2.1 stores its login token in same-origin localStorage. */
const authTokenKey = "qwenpaw_auth_token"
const base = "/api/imagenia"

export interface SettingsStatus {
  openai: { configured: boolean; source: "none" | "file" | "environment" }
}

export class SettingsRequestError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.code = code
    this.name = "SettingsRequestError"
  }
}

export function bearerHeaders(): HeadersInit {
  let token = ""
  try {
    token = localStorage.getItem(authTokenKey) ?? ""
  } catch {
    // Restricted storage or disabled auth; let the host return its own 401.
  }
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authenticatedFetch(path, init)
  if (response.status === 401 || response.status === 403) {
    throw new SettingsRequestError("unauthorized", "登录已失效，请返回 QwenPaw 重新登录。")
  }
  if (!response.ok) {
    let code = "service_unavailable"
    try {
      const data = await response.json() as { error?: { code?: string } }
      if (typeof data.error?.code === "string") code = data.error.code
    } catch {
      // No server-provided details are displayed or logged.
    }
    const messages: Record<string, string> = {
      invalid_api_key: "请输入有效的 API Key。",
      not_configured: "请先配置 API Key。",
      configuration_unavailable: "私有配置暂时不可用，请检查插件数据目录。",
      service_unavailable: "服务暂时不可用，请稍后重试。",
      queue_full: "任务排队已满，请稍后再试。",
      invalid_options: "请选择受支持的画幅和质量。",
      invalid_prompt: "请输入有效的提示词。",
    }
    throw new SettingsRequestError(code, messages[code] ?? "请求未完成，请稍后重试。")
  }
  try {
    return await response.json() as T
  } catch {
    throw new SettingsRequestError("invalid_response", "插件返回了无效的响应。")
  }
}

export async function authenticatedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`${base}${path}`, { ...init, headers: { ...bearerHeaders(), ...init.headers } })
  } catch {
    throw new SettingsRequestError("network_error", "无法连接到插件服务，请稍后重试。")
  }
  if (response.status === 401 || response.status === 403) {
    throw new SettingsRequestError("unauthorized", "登录已失效，请返回 QwenPaw 重新登录。")
  }
  return response
}

export function getSettings(): Promise<SettingsStatus> {
  return request<SettingsStatus>("/settings")
}

export function saveKey(apiKey: string): Promise<SettingsStatus> {
  return request<SettingsStatus>("/settings/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  })
}

/** Only called by the explicit test button; never during load or save. */
export function testConnection(): Promise<{ status: "ok" }> {
  return request<{ status: "ok" }>("/settings/openai/test", { method: "POST" })
}
