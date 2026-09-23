import { authenticatedFetch, request, SettingsRequestError } from "./settings.ts"
import type { GenerateInput, GenerationJob, ImageAsset } from "../mocks/imagenia-service"

interface JobResource {
  id: string
  kind: "generate" | "edit"
  prompt: string
  status: GenerationJob["status"]
  created_at: string
  result_asset_id: string | null
  error_message: string | null
}

interface AssetResource {
  id: string
  kind: ImageAsset["kind"]
  prompt: string
  model: string
  size: ImageAsset["size"]
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
      ...(editing ? { source_asset_id: input.sourceAssetId } : {}) }),
  })
  return response.job_id
}

export async function getJob(id: string): Promise<GenerationJob> {
  const job = await request<JobResource>(`/jobs/${encodeURIComponent(id)}`)
  return { id: job.id, kind: job.kind, prompt: job.prompt, status: job.status,
    createdAt: job.created_at, errorMessage: job.error_message ?? undefined,
    resultAssetId: job.result_asset_id ?? undefined }
}

export async function listJobs(): Promise<GenerationJob[]> {
  const data = await request<{ items: JobResource[] }>("/jobs")
  return data.items.map((job) => ({ id: job.id, kind: job.kind, prompt: job.prompt,
    status: job.status, createdAt: job.created_at,
    errorMessage: job.error_message ?? undefined,
    resultAssetId: job.result_asset_id ?? undefined }))
}

export interface AssetPage {
  items: ImageAsset[]
  nextCursor: string | null
}

export interface AssetFilters {
  favorite?: boolean
  kind?: "all" | ImageAsset["kind"]
  cursor?: string | null
  signal?: AbortSignal
}

function mapAsset(asset: AssetResource, url: string): ImageAsset {
  return { id: asset.id, kind: asset.kind, prompt: asset.prompt, model: asset.model,
    size: asset.size, dimensions: `${asset.width} × ${asset.height}`,
    createdAt: asset.created_at, isFavorite: asset.is_favorite,
    sourceAssetId: asset.source_asset_id ?? undefined, imageUrl: url, accent: "#64748b" }
}

/** A failed page never leaks URLs that finished loading before the failure. */
export async function listAssetPage(filters: AssetFilters = {}): Promise<AssetPage> {
  const params = new URLSearchParams()
  if (filters.favorite) params.set("favorite", "true")
  if (filters.kind && filters.kind !== "all") params.set("kind", filters.kind)
  if (filters.cursor) params.set("cursor", filters.cursor)
  const path = `/assets${params.size ? `?${params}` : ""}`
  const data = await request<{ items: AssetResource[]; next_cursor: string | null }>(path, { signal: filters.signal })
  const loaded = await Promise.allSettled(data.items.map(async (asset) =>
    mapAsset(asset, await imageUrl(asset.id, filters.signal))))
  const failed = loaded.find((result) => result.status === "rejected")
  if (failed || filters.signal?.aborted) {
    for (const result of loaded) if (result.status === "fulfilled") URL.revokeObjectURL(result.value.imageUrl)
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
  if (!response.ok || !(response.headers.get("content-type") ?? "").startsWith("image/png")) {
    throw new SettingsRequestError("image_unavailable", "图片暂时无法加载。")
  }
  const blob = await response.blob()
  if (signal?.aborted) throw new SettingsRequestError("cancelled", "图片加载已取消。")
  return URL.createObjectURL(blob)
}
