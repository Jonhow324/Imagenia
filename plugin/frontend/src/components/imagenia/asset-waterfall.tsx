import * as React from "react"
import { CircleAlertIcon, Loader2Icon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { ImageAsset } from "@/mocks/imagenia-service"
import { AssetCard } from "@/components/imagenia/asset-card"
import { EmptyLibrary } from "@/components/imagenia/empty-library"

export function AssetWaterfall({
  assets,
  filtered,
  highlightedAssetId,
  isLoading,
  hasMore,
  loadMoreError,
  onLoadMore,
  onResetFilters,
  onOpen,
  onToggleFavorite,
}: {
  assets: ImageAsset[]
  filtered: boolean
  highlightedAssetId: string | null
  isLoading: boolean
  hasMore: boolean
  loadMoreError: boolean
  onLoadMore: () => void
  onResetFilters: () => void
  onOpen: (asset: ImageAsset) => void
  onToggleFavorite: (asset: ImageAsset) => void
}) {
  if (isLoading) {
    return (
      <div className="columns-1 gap-4 sm:columns-2 xl:columns-3" aria-label="正在加载图片">
        {["h-72", "h-96", "h-64", "h-80", "h-72", "h-96"].map((height, index) => (
          <div key={index} className="mb-4 break-inside-avoid overflow-hidden rounded-xl border bg-card p-3">
            <Skeleton className={`${height} w-full rounded-lg`} />
            <Skeleton className="mt-3 h-4 w-4/5" />
            <Skeleton className="mt-2 h-3 w-2/5" />
          </div>
        ))}
      </div>
    )
  }

  if (assets.length === 0) {
    return <EmptyLibrary filtered={filtered} onReset={onResetFilters} />
  }

  return (
    <div>
      <div className="columns-1 gap-4 sm:columns-2 xl:columns-3">
        {assets.map((asset) => (
          <AssetCard
            key={asset.id}
            asset={asset}
            highlighted={asset.id === highlightedAssetId}
            onOpen={() => onOpen(asset)}
            onToggleFavorite={() => onToggleFavorite(asset)}
          />
        ))}
      </div>
      {loadMoreError ? (
        <Alert variant="destructive" className="mt-2">
          <CircleAlertIcon aria-hidden="true" />
          <AlertTitle>没有加载到更多图片</AlertTitle>
          <AlertDescription>网络状态不稳定，请稍后重试。</AlertDescription>
        </Alert>
      ) : null}
      {hasMore ? (
        <div className="mt-5 flex justify-center">
          <Button variant="outline" onClick={onLoadMore}>
            {loadMoreError ? "重新加载" : "加载更多"}
            {!loadMoreError ? <Loader2Icon className="opacity-60" aria-hidden="true" /> : null}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
