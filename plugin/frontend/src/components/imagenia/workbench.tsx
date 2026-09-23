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
import { enqueueGeneration, getAsset, getJob, listAssetPage, listJobs } from "@/services/generation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Toaster } from "@/components/ui/sonner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
  type AssetKind,
  type GenerateInput,
  type GenerationJob,
  type ImageAsset,
} from "@/mocks/imagenia-service"

type KindFilter = "all" | AssetKind

export function ImageniaWorkbench() {
  const [portalContainer, setPortalContainer] = React.useState<HTMLDivElement | null>(null)
  const [assets, setAssets] = React.useState<ImageAsset[]>([])
  const assetUrls = React.useRef<string[]>([])
  const [jobs, setJobs] = React.useState<GenerationJob[]>([])
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
  const [nextCursor, setNextCursor] = React.useState<string | null>(null)
  const [libraryError, setLibraryError] = React.useState("")
  const [loadMoreError, setLoadMoreError] = React.useState(false)
  const [isLoadingMore, setIsLoadingMore] = React.useState(false)
  const [reloadVersion, setReloadVersion] = React.useState(0)
  const pageController = React.useRef<AbortController | null>(null)
  const [extraDetail, setExtraDetail] = React.useState<ImageAsset | null>(null)
  const extraUrl = React.useRef<string | null>(null)
  const sourceNavigation = React.useRef<AbortController | null>(null)
  const [sourceAsset, setSourceAsset] = React.useState<ImageAsset | null>(null)
  const [sourceLoading, setSourceLoading] = React.useState(false)
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



  const selectedAsset = assets.find((asset) => asset.id === selectedAssetId)
    ?? (extraDetail?.id === selectedAssetId ? extraDetail : null)
  const editingAsset = assets.find((asset) => asset.id === editingAssetId) ?? null
  const filtersActive = favoriteOnly || kindFilter !== "all"

  React.useEffect(() => {
    const sourceId = selectedAsset?.sourceAssetId
    setSourceAsset(null)
    if (!sourceId) { setSourceLoading(false); return }
    const controller = new AbortController()
    let url: string | null = null
    setSourceLoading(true)
    getAsset(sourceId, controller.signal).then((source) => {
      url = source.imageUrl
      if (!controller.signal.aborted) setSourceAsset(source)
      else URL.revokeObjectURL(url)
    }).catch(() => { if (!controller.signal.aborted) setSourceAsset(null) })
      .finally(() => { if (!controller.signal.aborted) setSourceLoading(false) })
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url) }
  }, [selectedAsset?.sourceAssetId])

  function toggleFavorite(_asset: ImageAsset) {
    toast.info("收藏功能尚未开放，请等待后续工单。")
  }

  function deleteAsset(_asset: ImageAsset) {
    toast.info("删除功能尚未开放，图片和资产记录未被更改。")
  }

  function replaceAssets(fresh: ImageAsset[]) {
    const stale = assetUrls.current
    assetUrls.current = fresh.map((asset) => asset.imageUrl)
    setAssets(fresh)
    window.setTimeout(() => {
      for (const url of stale) URL.revokeObjectURL(url)
    }, 1000)
  }

  function refreshAssets() {
    setReloadVersion((version) => version + 1)
  }

  function closeDetail() {
    sourceNavigation.current?.abort()
    sourceNavigation.current = null
    setSelectedAssetId(null)
    setExtraDetail(null)
    if (extraUrl.current) URL.revokeObjectURL(extraUrl.current)
    extraUrl.current = null
  }

  function selectAsset(id: string) {
    sourceNavigation.current?.abort()
    sourceNavigation.current = null
    setSelectedAssetId(id)
  }

  React.useEffect(() => {
    let active = true
    listJobs().then((fresh) => { if (active) setJobs(fresh) }).catch((cause: unknown) => {
      if (active) setSettingsError(cause instanceof Error ? cause.message : "无法读取任务记录。")
    })
    return () => { active = false }
  }, [])

  React.useEffect(() => {
    const controller = new AbortController()
    pageController.current?.abort()
    setIsLoading(true)
    setIsLoadingMore(false)
    setLoadMoreError(false)
    setLibraryError("")
    setNextCursor(null)
    closeDetail()
    listAssetPage({ favorite: favoriteOnly, kind: kindFilter, signal: controller.signal }).then((page) => {
      if (!controller.signal.aborted) {
        replaceAssets(page.items)
        setNextCursor(page.nextCursor)
      } else for (const asset of page.items) URL.revokeObjectURL(asset.imageUrl)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setLibraryError(cause instanceof Error ? cause.message : "无法加载图片资料库。")
    }).finally(() => { if (!controller.signal.aborted) setIsLoading(false) })
    return () => controller.abort()
  }, [favoriteOnly, kindFilter, reloadVersion])

  React.useEffect(() => () => {
    pageController.current?.abort()
    sourceNavigation.current?.abort()
    for (const url of assetUrls.current) URL.revokeObjectURL(url)
    assetUrls.current = []
    if (extraUrl.current) URL.revokeObjectURL(extraUrl.current)
    extraUrl.current = null
  }, [])

  async function loadMore() {
    if (!nextCursor || isLoadingMore || pageController.current) return
    const controller = new AbortController()
    pageController.current = controller
    setIsLoadingMore(true)
    setLoadMoreError(false)
    try {
      const page = await listAssetPage({ favorite: favoriteOnly, kind: kindFilter,
        cursor: nextCursor, signal: controller.signal })
      if (controller.signal.aborted) {
        for (const asset of page.items) URL.revokeObjectURL(asset.imageUrl)
        return
      }
      assetUrls.current.push(...page.items.map((asset) => asset.imageUrl))
      setAssets((current) => [...current, ...page.items])
      setNextCursor(page.nextCursor)
    } catch {
      if (!controller.signal.aborted) setLoadMoreError(true)
    } finally {
      if (!controller.signal.aborted) setIsLoadingMore(false)
      if (pageController.current === controller) pageController.current = null
    }
  }

  async function openSource(asset: ImageAsset) {
    sourceNavigation.current?.abort()
    const controller = new AbortController()
    sourceNavigation.current = controller
    const inPage = assets.find((item) => item.id === asset.id)
    if (inPage) {
      setSelectedAssetId(inPage.id)
      sourceNavigation.current = null
      if (extraUrl.current) URL.revokeObjectURL(extraUrl.current)
      extraUrl.current = null
      setExtraDetail(null)
      return
    }
    try {
      const detail = await getAsset(asset.id, controller.signal)
      if (controller.signal.aborted) {
        URL.revokeObjectURL(detail.imageUrl)
        return
      }
      if (extraUrl.current) URL.revokeObjectURL(extraUrl.current)
      extraUrl.current = detail.imageUrl
      setExtraDetail(detail)
      setSelectedAssetId(detail.id)
    } catch (cause) {
      if (!controller.signal.aborted) toast.error(cause instanceof Error ? cause.message : "无法加载来源图片。")
    } finally {
      if (sourceNavigation.current === controller) sourceNavigation.current = null
    }
  }

  React.useEffect(() => {
    const activeJobs = jobs.filter((job) => job.status === "pending" || job.status === "running")
    if (!activeJobs.length) return
    let polling = false
    const timer = window.setInterval(async () => {
      if (polling) return
      polling = true
      try {
        for (const job of activeJobs) {
          const fresh = await getJob(job.id)
          if (fresh.status === "succeeded" && fresh.resultAssetId) {
            refreshAssets()
            setHighlightedAssetId(fresh.resultAssetId)
            window.setTimeout(() => setHighlightedAssetId((id) => id === fresh.resultAssetId ? null : id), 5000)
            toast.success("图像已完成", { description: "新作品已加入资料库并高亮显示。" })
          } else if (fresh.status === "failed") {
            toast.error(fresh.errorMessage ?? "生成失败，请稍后重试。")
          }
          setJobs((current) => current.map((item) => item.id === job.id ? fresh : item))
        }
      } catch (cause) {
        setSettingsError(cause instanceof Error ? cause.message : "无法读取任务状态。")
        window.clearInterval(timer)
      } finally { polling = false }
    }, 1500)
    return () => window.clearInterval(timer)
  }, [jobs])

  async function submitGeneration(input: GenerateInput) {
    if (input.sourceAssetId) {
      toast.error("编辑链路尚未开放，请等待后续工单。")
      return
    }
    setIsSubmitting(true)
    try {
      const id = await enqueueGeneration(input)
      setJobs((current) => [{ id, kind: "generate" as const, prompt: input.prompt, status: "pending" as const,
        createdAt: new Date().toISOString() }, ...current])
      toast.info("任务已加入队列")
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "提交失败，请稍后重试。")
    } finally { setIsSubmitting(false) }
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
                    <p className="mt-1 text-sm text-muted-foreground">{assets.length} 张已加载作品 · 全局共享</p>
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

                {libraryError && !isLoading ? (
                  <Alert variant="destructive">
                    <AlertTitle>图片资料库加载失败</AlertTitle>
                    <AlertDescription>{libraryError}</AlertDescription>
                    <Button type="button" variant="outline" className="mt-3" onClick={refreshAssets}>重试</Button>
                  </Alert>
                ) : <AssetWaterfall
                  assets={assets}
                  filtered={filtersActive}
                  highlightedAssetId={highlightedAssetId}
                  isLoading={isLoading}
                  isLoadingMore={isLoadingMore}
                  hasMore={Boolean(nextCursor)}
                  loadMoreError={loadMoreError}
                  onLoadMore={loadMore}
                  onResetFilters={resetFilters}
                  onOpen={(asset) => selectAsset(asset.id)}
                  onToggleFavorite={toggleFavorite}
                />}
              </section>
            </div>
          </div>

          <AssetDetailSheet
            asset={selectedAsset}
            open={Boolean(selectedAsset)}
            sourceAsset={sourceAsset}
            sourceLoading={sourceLoading}
            onOpenChange={(open) => { if (!open) closeDetail() }}
            onEdit={(asset) => {
              setEditingAssetId(asset.id)
              closeDetail()
              window.scrollTo({ top: 0, behavior: "smooth" })
            }}
            onDelete={deleteAsset}
            onToggleFavorite={toggleFavorite}
            onOpenSource={openSource}
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
