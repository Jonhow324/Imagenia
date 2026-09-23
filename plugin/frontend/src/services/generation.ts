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
  const response = await request<{ job_id: string; status: "pending" }>("/jobs/generate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: input.prompt, size: input.size, quality: input.quality }),
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

export async function listAssets(): Promise<ImageAsset[]> {
  const data = await request<{ items: AssetResource[] }>("/assets")
  return Promise.all(data.items.map(async (asset) => ({
    id: asset.id, kind: asset.kind, prompt: asset.prompt, model: asset.model,
    size: asset.size, dimensions: `${asset.width} × ${asset.height}`,
    createdAt: asset.created_at, isFavorite: asset.is_favorite,
    sourceAssetId: asset.source_asset_id ?? undefined,
    imageUrl: await imageUrl(asset.id), accent: "#64748b",
  })))
}

async function imageUrl(id: string): Promise<string> {
  const response = await authenticatedFetch(`/assets/${encodeURIComponent(id)}/content`)
  if (!response.ok || !(response.headers.get("content-type") ?? "").startsWith("image/png")) {
    throw new SettingsRequestError("image_unavailable", "图片暂时无法加载。")
  }
  return URL.createObjectURL(await response.blob())
}
