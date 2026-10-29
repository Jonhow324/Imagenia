import { authenticatedFetch, request, SettingsRequestError } from "./settings.ts"
import type { GenerateInput, GenerationJob, ImageAsset } from "../mocks/imagenia-service"

interface JobResource {
  service_id?: string
  service_name?: string
  model_id?: string
  model?: string
  source_asset_id?: string
  options?: { size: GenerateInput["size"]; quality: GenerateInput["quality"] }
  id: string
  kind: "generate" | "edit"
  prompt: string
  status: GenerationJob["status"]
  created_at: string
  result_asset_id: string | null
  error_message: string | null
}

interface AssetResource {
  service_id?: string
  service_name?: string
  model_id?: string
  id: string
  kind: ImageAsset["kind"]
  prompt: string
  model: string
  size: ImageAsset["size"]
  quality?: ImageAsset["quality"]
  width: number
  height: number
  created_at: string
  is_favorite: boolean
  source_asset_id: string | null
}

export async function enqueueGeneration(input: GenerateInput): Promise<string> {
  const editing = Boolean(input.sourceAssetId)
  const response = await request<{ job_id: string; status: "pending" }>(editing ? "/jobs/edit" : "/jobs/generate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: input.prompt, size: input.size, quality: input.quality,
      ...(input.serviceId ? { service_id: input.serviceId, model_id: input.modelId } : {}),
      ...(editing ? { source_asset_id: input.sourceAssetId } : {}) }),
  })
  return response.job_id
}

export async function getJob(id: string): Promise<GenerationJob> {
  const job = await request<JobResource>(`/jobs/${encodeURIComponent(id)}`)
  return { id: job.id, kind: job.kind, prompt: job.prompt, status: job.status,
    createdAt: job.created_at, errorMessage: job.error_message ?? undefined,
    resultAssetId: job.result_asset_id ?? undefined, serviceId: job.service_id, serviceName: job.service_name,
    modelId: job.model_id, model: job.model, sourceAssetId: job.source_asset_id ?? undefined, options: job.options ?? undefined }
}

export async function listJobs(): Promise<GenerationJob[]> {
  const data = await request<{ items: JobResource[] }>("/jobs")
  return data.items.map((job) => ({ id: job.id, kind: job.kind, prompt: job.prompt,
    status: job.status, createdAt: job.created_at,
    errorMessage: job.error_message ?? undefined,
    resultAssetId: job.result_asset_id ?? undefined, serviceId: job.service_id, serviceName: job.service_name,
    modelId: job.model_id, model: job.model, sourceAssetId: job.source_asset_id ?? undefined, options: job.options ?? undefined }))
}

export interface AssetPage {
  items: ImageAsset[]
  nextCursor: string | null
}

export interface AssetFilters {
  favorite?: boolean
  kind?: "all" | ImageAsset["kind"]
  query?: string
  cursor?: string | null
  signal?: AbortSignal
}

function mapAsset(asset: AssetResource, url: string, imageUnavailable = false): ImageAsset {
  return { id: asset.id, kind: asset.kind, prompt: asset.prompt, model: asset.model,
    serviceId: asset.service_id, serviceName: asset.service_name, modelId: asset.model_id,
    size: asset.size, quality: asset.quality === "high" || asset.quality === "standard" ? asset.quality : undefined,
    dimensions: `${asset.width} × ${asset.height}`,
    createdAt: asset.created_at, isFavorite: asset.is_favorite,
    sourceAssetId: asset.source_asset_id ?? undefined, imageUrl: url, accent: "#64748b",
    ...(imageUnavailable ? { imageUnavailable: true } : {}) }
}

/** ASCII-only case fold, matching SQLite LIKE without treating % or _ as wildcards. */
export function promptMatchesQuery(prompt: string, query: string | undefined): boolean {
  const term = query?.trim() ?? ""
  if (!term) return true
  const fold = (value: string) => value.replace(/[A-Za-z]/g, (letter) => letter.toLowerCase())
  return fold(prompt).includes(fold(term))
}

/** Keep a newly finished asset at the top when it belongs in the current library view. */
export function prependLibraryAsset(current: ImageAsset[], asset: ImageAsset,
  filters: { favoriteOnly: boolean; kind: "all" | ImageAsset["kind"]; query?: string }): ImageAsset[] {
  if (current.some((item) => item.id === asset.id)) return current
  if (filters.favoriteOnly && !asset.isFavorite) return current
  if (filters.kind !== "all" && asset.kind !== filters.kind) return current
  if (!promptMatchesQuery(asset.prompt, filters.query)) return current
  return [asset, ...current]
}

function revokeLoaded(loaded: PromiseSettledResult<ImageAsset>[]) {
  for (const result of loaded) {
    if (result.status === "fulfilled" && result.value.imageUrl.startsWith("blob:")) {
      URL.revokeObjectURL(result.value.imageUrl)
    }
  }
}

/** A page-level failure never leaks URLs that finished loading. One unreadable image stays as a card. */
export async function listAssetPage(filters: AssetFilters = {}): Promise<AssetPage> {
  const params = new URLSearchParams()
  if (filters.favorite) params.set("favorite", "true")
  if (filters.kind && filters.kind !== "all") params.set("kind", filters.kind)
  if (filters.query?.trim()) params.set("q", filters.query.trim())
  if (filters.cursor) params.set("cursor", filters.cursor)
  const path = `/assets${params.size ? `?${params}` : ""}`
  const data = await request<{ items: AssetResource[]; next_cursor: string | null }>(path, { signal: filters.signal })
  const loaded = await Promise.allSettled(data.items.map(async (asset) => {
    try {
      return mapAsset(asset, await imageUrl(asset.id, filters.signal))
    } catch (error) {
      if (error instanceof SettingsRequestError && error.code === "image_unavailable") return mapAsset(asset, "", true)
      throw error
    }
  }))
  const failed = loaded.find((result) => result.status === "rejected")
  if (failed || filters.signal?.aborted) {
    revokeLoaded(loaded)
    throw failed && failed.status === "rejected" ? failed.reason : new SettingsRequestError("cancelled", "图片加载已取消。")
  }
  return { items: loaded.map((result) => (result as PromiseFulfilledResult<ImageAsset>).value),
    nextCursor: data.next_cursor ?? null }
}

export async function listAssets(): Promise<ImageAsset[]> {
  return (await listAssetPage()).items
}

export async function getAsset(id: string, signal?: AbortSignal): Promise<ImageAsset> {
  const resource = await request<AssetResource>(`/assets/${encodeURIComponent(id)}`, { signal })
  return mapAsset(resource, await imageUrl(resource.id, signal))
}

async function imageUrl(id: string, signal?: AbortSignal): Promise<string> {
  const response = await authenticatedFetch(`/assets/${encodeURIComponent(id)}/content`, { signal })
  // Providers may return PNG or JPEG; the backend validates and preserves the original bytes.
  if (!response.ok || !(response.headers.get("content-type") ?? "").toLowerCase().startsWith("image/")) {
    throw new SettingsRequestError("image_unavailable", "图片暂时无法加载。")
  }
  const blob = await response.blob()
  if (signal?.aborted) throw new SettingsRequestError("cancelled", "图片加载已取消。")
  return URL.createObjectURL(blob)
}

export async function favoriteAsset(id: string, favorite: boolean): Promise<ImageAsset> {
  const resource = await request<AssetResource>(`/assets/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_favorite: favorite }),
  })
  return mapAsset(resource, "")
}

export async function deleteAsset(id: string): Promise<void> {
  await request<{ deleted: true }>(`/assets/${encodeURIComponent(id)}`, { method: "DELETE" })
}
