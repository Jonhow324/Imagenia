import * as React from "react"
import {
  HeartIcon,
  ImagesIcon,
  ListTodoIcon,
  PlusIcon,
  Settings2Icon,
  SlidersHorizontalIcon,
} from "lucide-react"
import { toast } from "sonner"

import imageniaIconUrl from "../../../../icon.svg?url"

import { ApiKeyMissingAlert } from "@/components/imagenia/api-key-missing-alert"
import { AssetDetailSheet } from "@/components/imagenia/asset-detail-sheet"
import { AssetWaterfall } from "@/components/imagenia/asset-waterfall"
import { SettingsSheet } from "@/components/imagenia/settings-sheet"
import { GenerationForm, createGenerationDraft } from "@/components/imagenia/generation-form"
import { GenerationJobCard } from "@/components/imagenia/generation-job-card"
import { PortalContainerProvider } from "@/components/imagenia/portal-root"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { getServices, type CatalogStatus } from "@/services/settings"
import { deleteAsset as removeAsset, enqueueGeneration, favoriteAsset, getAsset, getJob, listAssetPage, listJobs } from "@/services/generation"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
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
  const [editingAsset, setEditingAsset] = React.useState<ImageAsset | null>(null)
  const editingUrl = React.useRef<string | null>(null)
  const editController = React.useRef<AbortController | null>(null)
  const [favoriteOnly, setFavoriteOnly] = React.useState(false)
  const mutations = React.useRef(new Set<string>())
  const [kindFilter, setKindFilter] = React.useState<KindFilter>("all")
  const [settingsStatus, setSettingsStatus] = React.useState<CatalogStatus | null>(null)
  const [settingsError, setSettingsError] = React.useState("")
  const [settingsLoading, setSettingsLoading] = React.useState(true)
  const configured = settingsStatus?.services.some(service => service.enabled && service.configured) ?? false
  const [generationDraft, setGenerationDraft] = React.useState(createGenerationDraft)
  const [retryInput, setRetryInput] = React.useState<GenerateInput | null>(null)
  const [settingsOpen, setSettingsOpen] = React.useState(false)
  const [queueOpen, setQueueOpen] = React.useState(false)
  const [creatorOpen, setCreatorOpen] = React.useState(false)
  const [isCompact, setIsCompact] = React.useState(() => window.matchMedia("(max-width: 767px), (max-height: 539px)").matches)
  const libraryScroll = React.useRef<HTMLDivElement | null>(null)
  const activeJobs = jobs.filter(job => job.status === "pending" || job.status === "running").length

  React.useEffect(() => {
    const media = window.matchMedia("(max-width: 767px), (max-height: 539px)")
    const update = () => setIsCompact(media.matches)
    media.addEventListener("change", update)
    update()
    return () => media.removeEventListener("change", update)
  }, [])

  function revealCreator() {
    setQueueOpen(false)
    setCreatorOpen(true)
    window.requestAnimationFrame(() => document.getElementById("imagenia-prompt")?.focus({ preventScroll: true }))
  }
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
    getServices().then((result) => {
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

  async function toggleFavorite(asset: ImageAsset) {
    if (mutations.current.has(asset.id)) return
    mutations.current.add(asset.id)
    try {
      const updated = await favoriteAsset(asset.id, !asset.isFavorite)
      setAssets((current) => current.map((item) => item.id === asset.id
        ? { ...item, isFavorite: updated.isFavorite } : item))
      setExtraDetail((current) => current?.id === asset.id
        ? { ...current, isFavorite: updated.isFavorite } : current)
      toast.success(updated.isFavorite ? "已收藏图片" : "已取消收藏")
      // In filtered view the removed item and its pagination cursor must be
      // reconciled with the server; refresh also revokes old object URLs.
      if (favoriteOnly && !updated.isFavorite) refreshAssets()
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "收藏操作失败，请重试。")
    } finally {
      mutations.current.delete(asset.id)
    }
  }

  async function deleteAsset(asset: ImageAsset) {
    if (mutations.current.has(asset.id)) return
    mutations.current.add(asset.id)
    try {
      await removeAsset(asset.id)
      if (editingAsset?.id === asset.id) cancelEdit()
      closeDetail()
      refreshAssets()
      listJobs().then(setJobs).catch(() => {})
      toast.success("图片已永久删除")
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "删除失败，请重试。")
    } finally {
      mutations.current.delete(asset.id)
    }
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
    if (libraryScroll.current) libraryScroll.current.scrollTop = 0
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
    editController.current?.abort()
    if (editingUrl.current) URL.revokeObjectURL(editingUrl.current)
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

  function cancelEdit() {
    editController.current?.abort()
    editController.current = null
    if (editingUrl.current) URL.revokeObjectURL(editingUrl.current)
    editingUrl.current = null
    setEditingAsset(null)
  }

  async function beginEdit(asset: ImageAsset) {
    cancelEdit()
    const controller = new AbortController()
    editController.current = controller
    try {
      // Own a separate URL: library refresh and closing a detail can revoke theirs.
      const detail = await getAsset(asset.id, controller.signal)
      if (controller.signal.aborted) { URL.revokeObjectURL(detail.imageUrl); return }
      editingUrl.current = detail.imageUrl
      setEditingAsset(detail)
      closeDetail()
      revealCreator()
    } catch (cause) {
      if (!controller.signal.aborted) toast.error(cause instanceof Error ? cause.message : "来源图片无法加载。")
    } finally {
      if (editController.current === controller) editController.current = null
    }
  }

  async function retryGeneration(job: GenerationJob) {
    if (!job.options || !job.prompt) return
    if (job.kind === "edit") {
      if (!job.sourceAssetId) { toast.error("来源图片已不可用，请重新选择。"); return }
      try {
        const source = await getAsset(job.sourceAssetId)
        cancelEdit()
        editingUrl.current = source.imageUrl
        setEditingAsset(source)
      } catch (cause) {
        toast.error(cause instanceof Error ? cause.message : "来源图片已不可用。")
        return
      }
    } else cancelEdit()
    setRetryInput({ prompt: job.prompt, size: job.options.size, quality: job.options.quality,
      serviceId: job.serviceId, modelId: job.modelId, sourceAssetId: job.sourceAssetId })
    revealCreator()
    toast.info("已恢复参数，请确认服务和模型后提交。")
  }

  async function submitGeneration(input: GenerateInput) {
    setIsSubmitting(true)
    try {
      const id = await enqueueGeneration(input)
      setJobs((current) => [{ id, kind: (input.sourceAssetId ? "edit" : "generate") as GenerationJob["kind"], prompt: input.prompt, status: "pending" as const,
        createdAt: new Date().toISOString(), serviceId: input.serviceId, modelId: input.modelId,
        serviceName: settingsStatus?.services.find(service => service.id === input.serviceId)?.name,
        model: settingsStatus?.services.find(service => service.id === input.serviceId)?.models.find(model => model.id === input.modelId)?.name,
        options: { size: input.size, quality: input.quality }, sourceAssetId: input.sourceAssetId }, ...current])
      toast.info("任务已加入队列")
      if (input.sourceAssetId) cancelEdit()
      setCreatorOpen(false)
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "提交失败，请稍后重试。")
    } finally { setIsSubmitting(false) }
  }

  function resetFilters() {
    setFavoriteOnly(false)
    setKindFilter("all")
  }

  const generationForm = <GenerationForm
    configured={configured}
    draft={generationDraft}
    onDraftChange={setGenerationDraft}
    catalog={settingsStatus}
    retryInput={retryInput}
    editingAsset={editingAsset}
    isSubmitting={isSubmitting}
    onCancelEdit={cancelEdit}
    onSubmit={submitGeneration}
  />

  return (
    <main className="imagenia-root imagenia-workbench">
      <PortalContainerProvider container={portalContainer}>
        <TooltipProvider>
          <div className="mx-auto flex h-full w-full max-w-[1540px] flex-col gap-4 p-3 sm:p-4 lg:px-6">
            <header className="flex shrink-0 items-center justify-between gap-3 border-b pb-3">
              <div className="flex min-w-0 items-center gap-2 sm:gap-3">
                <img
                  src={imageniaIconUrl}
                  alt=""
                  aria-hidden="true"
                  width={40}
                  height={40}
                  className="size-9 shrink-0 sm:size-10"
                />
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="m-0 text-lg font-semibold tracking-tight sm:text-xl">Imagenia</h1>
                    <Badge variant="secondary" className="hidden lg:inline-flex">本地工作台</Badge>
                  </div>
                  <p className="mb-0 mt-0.5 hidden text-xs text-muted-foreground sm:block">生成、编辑并整理你的图像资产</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
                {isCompact ? <Button type="button" size="sm" onClick={revealCreator} aria-label="打开创作面板" title="打开创作面板">
                  <PlusIcon data-icon="inline-start" /><span className="hidden sm:inline">创作</span>
                </Button> : null}
                <Button type="button" variant="outline" size="sm" onClick={() => setQueueOpen(true)}
                  aria-label={`查看任务队列，${activeJobs} 个进行中`} title="查看任务队列">
                  <ListTodoIcon data-icon="inline-start" /><span className="hidden sm:inline">任务队列</span>
                  <Badge variant={activeJobs ? "default" : "secondary"}>{activeJobs}</Badge>
                </Button>
                <Button
                  type="button"
                  variant={favoriteOnly ? "secondary" : "outline"}
                  size="sm"
                  aria-label="仅看收藏"
                  title="仅看收藏"
                  aria-pressed={favoriteOnly}
                  onClick={() => setFavoriteOnly((value) => !value)}
                >
                  <HeartIcon className={favoriteOnly ? "fill-current text-rose-600" : ""} aria-hidden="true" />
                  <span className="hidden sm:inline">仅看收藏</span>
                </Button>
                <Button type="button" variant="outline" size="sm" aria-label="配置" title="配置" onClick={() => setSettingsOpen(true)}>
                  <Settings2Icon aria-hidden="true" />
                  <span className="hidden sm:inline">配置</span>
                </Button>
              </div>
            </header>

            {settingsError ? (
              <Alert variant="destructive" className="shrink-0">
                <AlertTitle>配置读取失败</AlertTitle>
                <AlertDescription>{settingsError}</AlertDescription>
              </Alert>
            ) : null}
            {!settingsLoading && !settingsError && !configured ? (
              <div className="shrink-0">
                <ApiKeyMissingAlert onConfigure={() => setSettingsOpen(true)} />
              </div>
            ) : null}

            <div className={cn("grid min-h-0 flex-1 gap-4", !isCompact && "md:grid-cols-[minmax(280px,340px)_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)]")}>
              {!isCompact ? <aside className="flex min-h-0 flex-col" aria-label="图像创作">{generationForm}</aside> : null}
              <section aria-labelledby="library-title" className="flex min-h-0 min-w-0 flex-col">
                <div className="mb-3 flex shrink-0 flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <ImagesIcon className="size-5 text-muted-foreground" aria-hidden="true" />
                      <h2 id="library-title" className="m-0 text-lg font-semibold">图片资料库</h2>
                    </div>
                    <p className="mb-0 mt-1 text-sm text-muted-foreground">{assets.length} 张已加载作品 · 全局共享</p>
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

                <div ref={libraryScroll} role="region" aria-label="图片资产列表" tabIndex={0}
                  className="min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-lg pr-2 outline-none focus-visible:ring-2 focus-visible:ring-ring">
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
                </div>
              </section>
            </div>
          </div>

          <Sheet open={queueOpen} onOpenChange={setQueueOpen}>
            <SheetContent className="flex min-h-0 w-full flex-col sm:max-w-md">
              <SheetHeader className="shrink-0 border-b">
                <SheetTitle>任务队列 <Badge variant="secondary">{activeJobs} 进行中</Badge></SheetTitle>
                <SheetDescription>最近 {jobs.length} 个任务，每 1–2 秒刷新；失败后可恢复参数，由你确认后重新提交。</SheetDescription>
              </SheetHeader>
              <div className="grid min-h-0 flex-1 auto-rows-max content-start gap-3 overflow-y-auto overscroll-contain px-4 pb-4" aria-label="最近任务列表">
                {jobs.length ? jobs.map(job => <GenerationJobCard key={job.id} job={job} onRetry={retryGeneration} />)
                  : <p className="py-8 text-center text-sm text-muted-foreground">还没有任务，提交后可在这里查看进度。</p>}
              </div>
            </SheetContent>
          </Sheet>

          {isCompact ? <Sheet open={creatorOpen} onOpenChange={setCreatorOpen}>
            <SheetContent side="bottom" className="flex min-h-0 flex-col p-3 data-[side=bottom]:h-[min(92dvh,720px)]">
              <SheetHeader className="shrink-0 px-1 pb-2 pt-0">
                <SheetTitle>{editingAsset ? "编辑图片" : "图像创作"}</SheetTitle>
                <SheetDescription className="sr-only">选择服务和模型，确认参数后提交任务。</SheetDescription>
              </SheetHeader>
              <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain">
                <div className={cn("flex flex-1 flex-col", editingAsset ? "min-h-[540px]" : "min-h-[440px]")}>{generationForm}</div>
              </div>
            </SheetContent>
          </Sheet> : null}

          <AssetDetailSheet
            asset={selectedAsset}
            open={Boolean(selectedAsset)}
            sourceAsset={sourceAsset}
            sourceLoading={sourceLoading}
            onOpenChange={(open) => { if (!open) closeDetail() }}
            onEdit={beginEdit}
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
