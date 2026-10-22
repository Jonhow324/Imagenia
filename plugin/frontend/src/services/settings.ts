/** QwenPaw 2.2.1 stores its login token in same-origin localStorage. */
const authTokenKey = "qwenpaw_auth_token"
const base = "/api/imagenia"

export interface SettingsStatus {
  openai: { configured: boolean; source: "none" | "file" | "environment"; base_url: string; model: string }
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
      service_in_use: "此服务有未完成任务，暂不能修改连接信息、移除模型或删除服务。",
      read_only_service: "环境配置由容器环境变量管理，不能在页面修改。",
      service_not_found: "所选服务已不存在，请重新选择。",
      model_not_found: "所选模型已不存在，请重新选择。",
      service_disabled: "所选服务已停用，请重新选择。",
      edit_not_supported: "此模型未启用图片编辑，请选择其他模型。",
      unsupported_options: "此模型不支持所选画幅或质量。",
      invalid_service: "请检查服务名称、地址、密钥和模型列表。",
      invalid_model: "请检查模型名称是否重复，并至少选择一种画幅和质量。",
      invalid_selection: "请选择有效的服务和模型。",
      configuration_changed: "服务配置已变化，请确认后重新提交。",
      service_limit: "最多可保存 50 个服务。",
      invalid_api_key: "请输入有效的 API Key。",
      not_configured: "请先配置 API Key。",
      configuration_unavailable: "私有配置暂时不可用，请检查插件数据目录。",
      service_unavailable: "服务暂时不可用，请稍后重试。",
      queue_full: "任务排队已满，请稍后再试。",
      invalid_options: "请选择受支持的画幅和质量。",
      invalid_prompt: "请输入有效的提示词。",
      invalid_input: "请选择一张有效的来源图片。",
      not_found: "来源图片已不存在或无法访问，请重新选择。",
      source_unavailable: "来源图片已不可用，请重新选择。",
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

export function saveSettings(settings: { api_key?: string; base_url?: string; model?: string }): Promise<SettingsStatus> {
  return request<SettingsStatus>("/settings/openai", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  })
}

/** Only called by the explicit test button; never during load or save. */
export function testConnection(): Promise<{ status: "ok" }> {
  return request<{ status: "ok" }>("/settings/openai/test", { method: "POST" })
}

export interface ServiceModel {
  id?: string
  name: string
  sizes: ("square" | "landscape" | "portrait")[]
  qualities: ("standard" | "high")[]
  supports_edit: boolean
}

export interface ImageService {
  id: string
  name: string
  base_url: string
  enabled: boolean
  configured: boolean
  read_only: boolean
  active_jobs: number
  models: (ServiceModel & { id: string })[]
}

export interface ServiceSelection {
  service_id: string
  model_id: string
}

export interface CatalogStatus {
  services: ImageService[]
  default: ServiceSelection | null
}

export interface ServiceInput {
  name: string
  base_url: string
  api_key?: string
  enabled: boolean
  models: ServiceModel[]
}

export function getServices(): Promise<CatalogStatus> {
  return request<CatalogStatus>("/services")
}

export function saveService(settings: ServiceInput, id?: string): Promise<CatalogStatus> {
  return request<CatalogStatus>(id ? `/services/${encodeURIComponent(id)}` : "/services", {
    method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings),
  })
}

export function deleteService(id: string): Promise<CatalogStatus> {
  return request<CatalogStatus>(`/services/${encodeURIComponent(id)}`, { method: "DELETE" })
}

export function setDefaultService(selection: ServiceSelection): Promise<CatalogStatus> {
  return request<CatalogStatus>("/services/default", {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(selection),
  })
}

export function testServiceConnection(id: string): Promise<{ status: "ok" }> {
  return request<{ status: "ok" }>(`/services/${encodeURIComponent(id)}/test`, { method: "POST" })
}
