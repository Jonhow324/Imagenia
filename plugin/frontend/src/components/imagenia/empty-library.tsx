import * as React from "react"
import { ImagesIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

export function EmptyLibrary({ filtered, onReset }: { filtered: boolean; onReset: () => void }) {
  return (
    <Empty className="min-h-80 rounded-xl border border-dashed bg-muted/20">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          {filtered ? <ImagesIcon aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
        </EmptyMedia>
        <EmptyTitle>{filtered ? "没有符合条件的图片" : "开始你的第一张图像"}</EmptyTitle>
        <EmptyDescription>
          {filtered ? "尝试清除收藏或类型筛选。" : "在左侧输入画面描述，完成的作品会出现在这里。"}
        </EmptyDescription>
      </EmptyHeader>
      {filtered ? (
        <EmptyContent>
          <Button variant="outline" onClick={onReset}>清除筛选</Button>
        </EmptyContent>
      ) : null}
    </Empty>
  )
}
