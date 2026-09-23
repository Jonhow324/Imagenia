import * as React from "react"
import {
  HeartIcon,
  ImagesIcon,
  Settings2Icon,
  SlidersHorizontalIcon,
  SparklesIcon,
} from "lucide-react"
import { toast } from "sonner"

import { ApiKeyMissingAlert } from "@/components/imagenia/api-key-missing-alert"
import { AssetDetailSheet } from "@/components/imagenia/asset-detail-sheet"
import { AssetWaterfall } from "@/components/imagenia/asset-waterfall"
import { SettingsSheet } from "@/components/imagenia/settings-sheet"
import { GenerationForm } from "@/components/imagenia/generation-form"
import { GenerationJobCard } from "@/components/imagenia/generation-job-card"
import { PortalContainerProvider } from "@/components/imagenia/portal-root"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { getSettings, type SettingsStatus } from "@/services/settings"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Toaster } from "@/components/ui/sonner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  createMockAsset,
  createMockJob,
  initialAssets,
  initialJobs,
  type AssetKind,
  type GenerateInput,
  type GenerationJob,
  type ImageAsset,
} from "@/mocks/imagenia-service"

type KindFilter = "all" | AssetKind

export function ImageniaWorkbench() {
  const [portalContainer, setPortalContainer] = React.useState<HTMLDivElement | null>(null)
  const [assets, setAssets] = React.useState<ImageAsset[]>(initialAssets)
  const [jobs, setJobs] = React.useState<GenerationJob[]>(initialJobs)
  const [selectedAssetId, setSelectedAssetId] = React.useState<string | null>(null)
  const [editingAssetId, setEditingAssetId] = React.useState<string | null>(null)
  const [favoriteOnly, setFavoriteOnly] = React.useState(false)
  const [kindFilter, setKindFilter] = React.useState<KindFilter>("all")
  const [settingsStatus, setSettingsStatus] = React.useState<SettingsStatus | null>(null)
  const [settingsError, setSettingsError] = React.useState("")
  const [settingsLoading, setSettingsLoading] = React.useState(true)
  const configured = settingsStatus?.openai.configured ?? false
  const [settingsOpen, setSettingsOpen] = React.useState(false)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [isLoading, setIsLoading] = React.useState(true)
  const [visibleCount, setVisibleCount] = React.useState(4)
  const [loadMoreError, setLoadMoreError] = React.useState(false)
  const [loadMoreAttempted, setLoadMoreAttempted] = React.useState(false)
  const [highlightedAssetId, setHighlightedAssetId] = React.useState<string | null>(null)

  React.useEffect(() => {
    let active = true
    getSettings().then((result) => {
      if (active) setSettingsStatus(result)
    }).catch((cause: unknown) => {
      if (active) setSettingsError(cause instanceof Error ? cause.message : "无法读取配置。")
    }).finally(() => {
      if (active) setSettingsLoading(false)
    })
    return () => { active = false }
  }, [])

  React.useEffect(() => {
    const timer = window.setTimeout(() => setIsLoading(false), 550)
    return () => window.clearTimeout(timer)
  }, [])

  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId) ?? null
  const editingAsset = assets.find((asset) => asset.id === editingAssetId) ?? null
  const sourceAsset = selectedAsset?.sourceAssetId
    ? assets.find((asset) => asset.id === selectedAsset.sourceAssetId) ?? null
    : null

  const filteredAssets = assets.filter((asset) => {
    if (favoriteOnly && !asset.isFavorite) return false
    if (kindFilter !== "all" && asset.kind !== kindFilter) return false
    return true
  })
  const visibleAssets = filteredAssets.slice(0, visibleCount)
  const filtersActive = favoriteOnly || kindFilter !== "all"

  function toggleFavorite(asset: ImageAsset) {
    const nextValue = !asset.isFavorite
    setAssets((current) => current.map((item) => item.id === asset.id ? { ...item, isFavorite: nextValue } : item))
    toast.success(nextValue ? "已加入收藏" : "已取消收藏", {
      description: nextValue ? "可以通过顶部的收藏筛选快速找到它。" : "图片仍保留在全部作品中。",
    })
  }

  function deleteAsset(asset: ImageAsset) {
    setAssets((current) => current
      .filter((item) => item.id !== asset.id)
      .map((item) => item.sourceAssetId === asset.id ? { ...item, sourceAssetId: undefined } : item))
    setSelectedAssetId(null)
    if (editingAssetId === asset.id) setEditingAssetId(null)
    toast.success("图片已删除", { description: "本地文件和资产记录已移除。" })
  }

  function submitGeneration(input: GenerateInput) {
    const job = createMockJob(input)
    setIsSubmitting(true)
    setJobs((current) => [job, ...current].slice(0, 5))

    window.setTimeout(() => {
      setIsSubmitting(false)
      setJobs((current) => current.map((item) => item.id === job.id ? { ...item, status: "running" } : item))
      toast.info("任务已开始", { description: "工作台会自动轮询进度。" })
    }, 500)

    window.setTimeout(() => {
      const asset = createMockAsset(input)
      setAssets((current) => [asset, ...current])
      setVisibleCount((count) => Math.max(count + 1, 5))
      setJobs((current) => current.map((item) => item.id === job.id
        ? { ...item, status: "succeeded", resultAssetId: asset.id }
        : item))
      setEditingAssetId(null)
      setHighlightedAssetId(asset.id)
      toast.success("图像已完成", { description: "新作品已加入资料库并高亮显示。" })
      window.setTimeout(() => setHighlightedAssetId((current) => current === asset.id ? null : current), 5000)
    }, 2800)
  }

  function loadMore() {
    if (!loadMoreAttempted) {
      setLoadMoreAttempted(true)
      setLoadMoreError(true)
      return
    }
    setLoadMoreError(false)
    setVisibleCount(filteredAssets.length)
  }

  function resetFilters() {
    setFavoriteOnly(false)
    setKindFilter("all")
  }

  return (
    <main className="imagenia-root min-h-full bg-background text-foreground">
      <PortalContainerProvider container={portalContainer}>
        <TooltipProvider>
          <div className="mx-auto w-full max-w-[1540px] px-4 py-5 sm:px-6 lg:px-8 lg:py-7">
            <header className="mb-6 flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                  <SparklesIcon className="size-5" aria-hidden="true" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-semibold tracking-tight">Imagenia</h1>
                    <Badge variant="secondary">本地工作台</Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground">生成、编辑并整理你的图像资产</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant={favoriteOnly ? "secondary" : "outline"}
                  aria-pressed={favoriteOnly}
                  onClick={() => setFavoriteOnly((value) => !value)}
                >
                  <HeartIcon className={favoriteOnly ? "fill-current text-rose-600" : ""} aria-hidden="true" />
                  仅看收藏
                </Button>
                <Button type="button" variant="outline" onClick={() => setSettingsOpen(true)}>
                  <Settings2Icon aria-hidden="true" />
                  配置
                </Button>
              </div>
            </header>

            {settingsError ? (
              <Alert variant="destructive" className="mb-5">
                <AlertTitle>配置读取失败</AlertTitle>
                <AlertDescription>{settingsError}</AlertDescription>
              </Alert>
            ) : null}
            {!settingsLoading && !settingsError && !configured ? (
              <div className="mb-5">
                <ApiKeyMissingAlert onConfigure={() => setSettingsOpen(true)} />
              </div>
            ) : null}

            <div className="grid items-start gap-6 lg:grid-cols-[minmax(300px,380px)_minmax(0,1fr)]">
              <aside className="grid gap-4 lg:sticky lg:top-5">
                <GenerationForm
                  configured={configured}
                  editingAsset={editingAsset}
                  isSubmitting={isSubmitting}
                  onCancelEdit={() => setEditingAssetId(null)}
                  onSubmit={submitGeneration}
                />

                <Card className="bg-card/80">
                  <CardHeader className="border-b pb-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <CardTitle>最近任务</CardTitle>
                        <CardDescription>每 1–2 秒自动刷新状态</CardDescription>
                      </div>
                      <Badge variant="outline">{jobs.filter((job) => job.status === "pending" || job.status === "running").length} 进行中</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="grid gap-2.5">
                    {jobs.slice(0, 3).map((job) => <GenerationJobCard key={job.id} job={job} />)}
                  </CardContent>
                </Card>
              </aside>

              <section aria-labelledby="library-title" className="min-w-0">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <ImagesIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                      <h2 id="library-title" className="text-lg font-semibold">图片资料库</h2>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{filteredAssets.length} 张作品 · 全局共享</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <SlidersHorizontalIcon className="size-4 text-muted-foreground" aria-hidden="true" />
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      size="sm"
                      spacing={0}
                      value={kindFilter}
                      onValueChange={(value) => setKindFilter((value || "all") as KindFilter)}
                      aria-label="按图片类型筛选"
                    >
                      <ToggleGroupItem value="all">全部</ToggleGroupItem>
                      <ToggleGroupItem value="generated">生成</ToggleGroupItem>
                      <ToggleGroupItem value="edited">编辑</ToggleGroupItem>
                    </ToggleGroup>
                  </div>
                </div>

                <AssetWaterfall
                  assets={visibleAssets}
                  filtered={filtersActive}
                  highlightedAssetId={highlightedAssetId}
                  isLoading={isLoading}
                  hasMore={visibleCount < filteredAssets.length}
                  loadMoreError={loadMoreError}
                  onLoadMore={loadMore}
                  onResetFilters={resetFilters}
                  onOpen={(asset) => setSelectedAssetId(asset.id)}
                  onToggleFavorite={toggleFavorite}
                />
              </section>
            </div>
          </div>

          <AssetDetailSheet
            asset={selectedAsset}
            open={Boolean(selectedAsset)}
            sourceAsset={sourceAsset}
            onOpenChange={(open) => { if (!open) setSelectedAssetId(null) }}
            onEdit={(asset) => {
              setEditingAssetId(asset.id)
              setSelectedAssetId(null)
              window.scrollTo({ top: 0, behavior: "smooth" })
            }}
            onDelete={deleteAsset}
            onToggleFavorite={toggleFavorite}
            onOpenSource={(asset) => setSelectedAssetId(asset.id)}
          />

          <SettingsSheet
            open={settingsOpen}
            onOpenChange={setSettingsOpen}
            status={settingsStatus}
            onSaved={(next) => { setSettingsStatus(next); setSettingsError("") }}
          />

          <div ref={setPortalContainer} data-imagenia-portal-root />
          <Toaster position="bottom-right" richColors closeButton />
        </TooltipProvider>
      </PortalContainerProvider>
    </main>
  )
}
