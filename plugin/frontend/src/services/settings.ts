/** QwenPaw 2.2.1 stores its login token in same-origin localStorage. */
const authTokenKey = "qwenpaw_auth_token"
const base = "/api/imagenia/settings"

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

function bearerHeaders(): HeadersInit {
  let token = ""
  try {
    token = localStorage.getItem(authTokenKey) ?? ""
  } catch {
    // Restricted storage or disabled auth; let the host return its own 401.
  }
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: { ...bearerHeaders(), ...init.headers },
    })
  } catch {
    throw new SettingsRequestError("network_error", "无法连接到插件服务，请稍后重试。")
  }
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
      service_unavailable: "连接测试失败，请稍后重试。",
    }
    throw new SettingsRequestError(code, messages[code] ?? "请求未完成，请稍后重试。")
  }
  try {
    return await response.json() as T
  } catch {
    throw new SettingsRequestError("invalid_response", "插件返回了无效的响应。")
  }
}

export function getSettings(): Promise<SettingsStatus> {
  return request<SettingsStatus>("")
}

export function saveKey(apiKey: string): Promise<SettingsStatus> {
  return request<SettingsStatus>("/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  })
}

/** Only called by the explicit test button; never during load or save. */
export function testConnection(): Promise<{ status: "ok" }> {
  return request<{ status: "ok" }>("/openai/test", { method: "POST" })
}
