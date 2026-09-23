import * as React from "react"
import { CalendarIcon, ImageIcon, PencilLineIcon, ShapesIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { ImageAsset } from "@/mocks/imagenia-service"
import { DeleteAssetDialog } from "@/components/imagenia/delete-asset-dialog"
import { FavoriteButton } from "@/components/imagenia/favorite-button"

export function AssetDetailSheet({
  asset,
  open,
  sourceAsset,
  sourceLoading,
  onOpenChange,
  onEdit,
  onDelete,
  onToggleFavorite,
  onOpenSource,
}: {
  asset: ImageAsset | null
  open: boolean
  sourceAsset: ImageAsset | null
  sourceLoading: boolean
  onOpenChange: (open: boolean) => void
  onEdit: (asset: ImageAsset) => void
  onDelete: (asset: ImageAsset) => void
  onToggleFavorite: (asset: ImageAsset) => void
  onOpenSource: (asset: ImageAsset) => void
}) {
  if (!asset) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(94vw,560px)] overflow-y-auto p-0 sm:max-w-xl">
        <SheetHeader className="border-b px-5 py-4 pr-14">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{asset.kind === "edited" ? "编辑结果" : "生成结果"}</Badge>
            <span className="text-xs text-muted-foreground">{asset.dimensions}</span>
          </div>
          <SheetTitle className="text-lg">图片详情</SheetTitle>
          <SheetDescription>查看生成信息，或以当前图片继续编辑。</SheetDescription>
        </SheetHeader>

        <div className="grid gap-5 p-5">
          <div className="overflow-hidden rounded-xl bg-muted ring-1 ring-foreground/10">
            <img src={asset.imageUrl} alt={asset.prompt} className="h-auto w-full object-cover" />
          </div>

          <section aria-labelledby="prompt-heading" className="grid gap-2">
            <h3 id="prompt-heading" className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">提示词</h3>
            <p className="text-sm leading-6">{asset.prompt}</p>
          </section>

          <Separator />

          <dl className="grid grid-cols-2 gap-4 text-sm">
            <Meta icon={ShapesIcon} label="模型" value={asset.model} />
            <Meta icon={ImageIcon} label="画幅" value={`${sizeLabel(asset.size)} · ${asset.dimensions}`} />
            <Meta icon={CalendarIcon} label="创建时间" value={formatDateTime(asset.createdAt)} />
            <Meta icon={PencilLineIcon} label="类型" value={asset.kind === "edited" ? "基于图片编辑" : "文本生成"} />
          </dl>

          {asset.sourceAssetId ? (
            <section className="grid gap-2" aria-labelledby="source-heading">
              <h3 id="source-heading" className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">直接来源</h3>
              {sourceAsset ? (
                <button type="button" onClick={() => onOpenSource(sourceAsset)} className="flex items-center gap-3 rounded-lg border bg-muted/30 p-2.5 text-left transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <img src={sourceAsset.imageUrl} alt="来源图片" className="size-14 rounded-md object-cover" />
                  <span className="line-clamp-2 text-sm">{sourceAsset.prompt}</span>
                </button>
              ) : (
                <p className="text-sm text-muted-foreground">{sourceLoading ? "正在加载来源图片…" : "来源图片不可用或已被删除。"}</p>
              )}
            </section>
          ) : null}
        </div>

        <SheetFooter className="sticky bottom-0 flex-row border-t bg-background/95 p-4 backdrop-blur">
          <FavoriteButton active={asset.isFavorite} onToggle={() => onToggleFavorite(asset)} className="mr-auto" />
          <DeleteAssetDialog assetLabel={asset.prompt} onConfirm={() => onDelete(asset)} />
          <Button onClick={() => onEdit(asset)}>
            <PencilLineIcon aria-hidden="true" />
            以此编辑
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function Meta({ icon: Icon, label, value }: { icon: typeof CalendarIcon; label: string; value: string }) {
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
      <Icon className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="col-start-2 text-sm font-medium">{value}</dd>
    </div>
  )
}

function sizeLabel(size: ImageAsset["size"]) {
  return size === "square" ? "方形" : size === "landscape" ? "横向" : "竖向"
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value))
}
