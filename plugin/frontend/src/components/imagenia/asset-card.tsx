import * as React from "react"
import { ArrowUpRightIcon, Layers2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { ImageAsset } from "@/mocks/imagenia-service"
import { FavoriteButton } from "@/components/imagenia/favorite-button"

export function AssetCard({
  asset,
  highlighted,
  onOpen,
  onToggleFavorite,
}: {
  asset: ImageAsset
  highlighted: boolean
  onOpen: () => void
  onToggleFavorite: () => void
}) {
  return (
    <Card
      className={cn(
        "mb-4 break-inside-avoid cursor-pointer border-0 bg-card p-0 shadow-sm ring-1 ring-foreground/10 transition hover:-translate-y-0.5 hover:shadow-md focus-within:ring-2 focus-within:ring-ring",
        highlighted && "ring-2 ring-primary ring-offset-2 ring-offset-background",
      )}
      onClick={onOpen}
    >
      <div className="group relative overflow-hidden rounded-t-xl bg-muted">
        <img
          src={asset.imageUrl}
          alt={asset.prompt}
          className="block h-auto w-full object-cover transition duration-500 group-hover:scale-[1.015]"
        />
        <div className="absolute inset-x-0 top-0 flex items-start justify-between gap-2 bg-gradient-to-b from-black/45 to-transparent p-3">
          <Badge className="border-white/20 bg-black/30 text-white backdrop-blur-sm">
            {asset.kind === "edited" ? <Layers2Icon aria-hidden="true" /> : null}
            {asset.kind === "edited" ? "编辑" : "生成"}
          </Badge>
          <FavoriteButton active={asset.isFavorite} onToggle={onToggleFavorite} className="border-white/25 bg-black/25 text-white hover:bg-black/40 hover:text-white" />
        </div>
      </div>
      <CardContent className="flex items-start gap-3 py-3">
        <div className="min-w-0 flex-1">
          <p className="line-clamp-2 text-sm font-medium leading-5">{asset.prompt}</p>
          <p className="mt-1 text-xs text-muted-foreground">{asset.dimensions} · {formatDate(asset.createdAt)}</p>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="查看图片详情"
              onClick={(event) => {
                event.stopPropagation()
                onOpen()
              }}
            >
              <ArrowUpRightIcon aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>查看详情</TooltipContent>
        </Tooltip>
      </CardContent>
    </Card>
  )
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(value))
}
