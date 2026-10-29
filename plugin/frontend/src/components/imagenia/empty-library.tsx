import * as React from "react"
import { ImagesIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

export function EmptyLibrary({ filtered, searching, onReset }: { filtered: boolean; searching: boolean; onReset: () => void }) {
  return (
    <Empty className="min-h-80 rounded-xl border border-dashed bg-muted/20">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          {filtered ? <ImagesIcon aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
        </EmptyMedia>
        <EmptyTitle>{filtered ? "没有符合条件的图片" : "开始你的第一张图像"}</EmptyTitle>
        <EmptyDescription>
          {searching
            ? "没有提示词包含这段文字。可以换一个关键词，或清除搜索与筛选。"
            : filtered
              ? "尝试清除收藏或类型筛选。"
              : "填写画面描述并开始生成，完成的作品会出现在这里。"}
        </EmptyDescription>
      </EmptyHeader>
      {filtered ? (
        <EmptyContent>
          <Button variant="outline" onClick={onReset}>{searching ? "清除搜索和筛选" : "清除筛选"}</Button>
        </EmptyContent>
      ) : null}
    </Empty>
  )
}
