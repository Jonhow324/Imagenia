export type AssetKind = "generated" | "edited"
export type JobStatus = "pending" | "running" | "succeeded" | "failed"
export type ImageSize = "square" | "landscape" | "portrait"
export type ImageQuality = "standard" | "high"

export interface ImageAsset {
  id: string
  kind: AssetKind
  prompt: string
  model: string
  size: ImageSize
  dimensions: string
  createdAt: string
  isFavorite: boolean
  sourceAssetId?: string
  imageUrl: string
  accent: string
}

export interface GenerationJob {
  id: string
  kind: "generate" | "edit"
  prompt: string
  status: JobStatus
  createdAt: string
  errorMessage?: string
  resultAssetId?: string
}

export interface GenerateInput {
  prompt: string
  size: ImageSize
  quality: ImageQuality
  sourceAssetId?: string
}

const palette = {
  apricot: ["#f4d7c4", "#b56f55", "#4c2924"],
  lagoon: ["#c8e6df", "#3a8d87", "#153f47"],
  violet: ["#ddd4f5", "#7363a8", "#2e2855"],
  moss: ["#d9e4c7", "#74895a", "#31412c"],
  dusk: ["#f0cfbd", "#8e6483", "#283b59"],
} as const

type PaletteName = keyof typeof palette

function svgDataUrl(
  label: string,
  size: ImageSize,
  paletteName: PaletteName,
  variant: number,
) {
  const [light, mid, dark] = palette[paletteName]
  const [width, height] =
    size === "portrait" ? [840, 1120] : size === "landscape" ? [1200, 820] : [960, 960]
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${light}"/><stop offset=".55" stop-color="${mid}"/><stop offset="1" stop-color="${dark}"/></linearGradient>
      <filter id="b"><feGaussianBlur stdDeviation="42"/></filter>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
    <circle cx="${width * (variant % 2 ? 0.7 : 0.25)}" cy="${height * 0.24}" r="${Math.min(width, height) * 0.22}" fill="${light}" opacity=".78" filter="url(#b)"/>
    <path d="M0 ${height * 0.72} Q ${width * 0.24} ${height * 0.48}, ${width * 0.52} ${height * 0.7} T ${width} ${height * 0.55} V${height}H0Z" fill="${dark}" opacity=".62"/>
    <path d="M0 ${height * 0.82} Q ${width * 0.35} ${height * 0.62}, ${width} ${height * 0.78} V${height}H0Z" fill="${light}" opacity=".52"/>
    <text x="48" y="${height - 54}" fill="white" opacity=".88" font-family="system-ui,sans-serif" font-size="25" letter-spacing="2">${label}</text>
  </svg>`
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

export const initialAssets: ImageAsset[] = [
  {
    id: "asset-aurora",
    kind: "generated",
    prompt: "薄雾清晨，一座漂浮在云层上的极简玻璃温室，柔和电影光线",
    model: "gpt-image-1",
    size: "portrait",
    dimensions: "1024 × 1536",
    createdAt: "2026-09-22T08:42:00+08:00",
    isFavorite: true,
    imageUrl: svgDataUrl("GLASS GARDEN", "portrait", "lagoon", 1),
    accent: "#3a8d87",
  },
  {
    id: "asset-still-life",
    kind: "generated",
    prompt: "现代陶艺静物，暖色工作室，自然阴影，编辑摄影风格",
    model: "gpt-image-1",
    size: "square",
    dimensions: "1024 × 1024",
    createdAt: "2026-09-22T08:16:00+08:00",
    isFavorite: false,
    imageUrl: svgDataUrl("CERAMIC STUDY", "square", "apricot", 2),
    accent: "#b56f55",
  },
  {
    id: "asset-nocturne",
    kind: "edited",
    prompt: "保留构图，将场景调整为蓝紫色夜景并增加远处的灯光",
    model: "gpt-image-1",
    size: "landscape",
    dimensions: "1536 × 1024",
    createdAt: "2026-09-21T23:12:00+08:00",
    isFavorite: true,
    sourceAssetId: "asset-still-life",
    imageUrl: svgDataUrl("BLUE NOCTURNE", "landscape", "violet", 3),
    accent: "#7363a8",
  },
  {
    id: "asset-moss",
    kind: "generated",
    prompt: "苔藓覆盖的未来主义庭院，安静、潮湿、柔焦，建筑概念图",
    model: "gpt-image-1",
    size: "portrait",
    dimensions: "1024 × 1536",
    createdAt: "2026-09-22T21:48:00+08:00",
    isFavorite: false,
    imageUrl: svgDataUrl("MOSS ATRIUM", "portrait", "moss", 4),
    accent: "#74895a",
  },
  {
    id: "asset-dusk",
    kind: "edited",
    prompt: "将天空改为日落后的粉色暮光，增强远景层次，保持人物剪影",
    model: "gpt-image-1",
    size: "landscape",
    dimensions: "1536 × 1024",
    createdAt: "2026-09-22T19:35:00+08:00",
    isFavorite: false,
    sourceAssetId: "asset-aurora",
    imageUrl: svgDataUrl("AFTERGLOW", "landscape", "dusk", 5),
    accent: "#8e6483",
  },
]

export const initialJobs: GenerationJob[] = [
  {
    id: "job-running",
    kind: "generate",
    prompt: "月光下的黑色纸艺森林，细腻层叠",
    status: "running",
    createdAt: "2026-09-22T09:03:00+08:00",
  },
  {
    id: "job-pending",
    kind: "generate",
    prompt: "红色丝绸与金属构成的抽象雕塑",
    status: "pending",
    createdAt: "2026-09-22T09:02:00+08:00",
  },
  {
    id: "job-failed",
    kind: "edit",
    prompt: "增加玻璃反射与雨滴",
    status: "failed",
    createdAt: "2026-09-22T08:51:00+08:00",
    errorMessage: "服务暂时不可用，请稍后重新提交。",
  },
]

const mockCreatedAt = () => "2026-09-22T09:08:00+08:00"

export function createMockJob(input: GenerateInput): GenerationJob {
  return {
    id: `job-${crypto.randomUUID()}`,
    kind: input.sourceAssetId ? "edit" : "generate",
    prompt: input.prompt,
    status: "pending",
    createdAt: mockCreatedAt(),
  }
}

export function createMockAsset(input: GenerateInput): ImageAsset {
  const paletteNames = Object.keys(palette) as PaletteName[]
  const paletteName = paletteNames[Math.floor(Math.random() * paletteNames.length)]
  const id = `asset-${crypto.randomUUID()}`
  return {
    id,
    kind: input.sourceAssetId ? "edited" : "generated",
    prompt: input.prompt,
    model: "gpt-image-1",
    size: input.size,
    dimensions:
      input.size === "portrait"
        ? "1024 × 1536"
        : input.size === "landscape"
          ? "1536 × 1024"
          : "1024 × 1024",
    createdAt: mockCreatedAt(),
    isFavorite: false,
    sourceAssetId: input.sourceAssetId,
    imageUrl: svgDataUrl("NEW IMAGINATION", input.size, paletteName, 6),
    accent: palette[paletteName][1],
  }
}
