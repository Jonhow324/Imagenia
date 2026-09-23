import * as React from "react"
import { ImagePlusIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type { GenerateInput, ImageAsset, ImageQuality, ImageSize } from "@/mocks/imagenia-service"

export function GenerationForm({
  configured,
  editingAsset,
  isSubmitting,
  onCancelEdit,
  onSubmit,
}: {
  configured: boolean
  editingAsset: ImageAsset | null
  isSubmitting: boolean
  onCancelEdit: () => void
  onSubmit: (input: GenerateInput) => void
}) {
  const [prompt, setPrompt] = React.useState("")
  const [size, setSize] = React.useState<ImageSize>("square")
  const [quality, setQuality] = React.useState<ImageQuality>("standard")
  const [error, setError] = React.useState("")

  React.useEffect(() => {
    if (editingAsset) {
      setPrompt(`以这张图片为基础，${editingAsset.prompt}`)
      setSize(editingAsset.size)
      setError("")
    } else {
      setPrompt("")
      setSize("square")
      setQuality("standard")
      setError("")
    }
  }, [editingAsset])

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalized = prompt.trim()
    if (normalized.length < 8) {
      setError("请至少输入 8 个字符，让画面意图更清楚。")
      return
    }
    setError("")
    onSubmit({ prompt: normalized, size, quality, sourceAssetId: editingAsset?.id })
  }

  return (
    <Card className="border-0 bg-card/95 shadow-sm ring-1 ring-foreground/10">
      <CardHeader className="border-b pb-4">
        <div className="flex items-start justify-between gap-3">
          <div className="grid gap-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              {editingAsset ? <ImagePlusIcon className="size-4" aria-hidden="true" /> : <SparklesIcon className="size-4" aria-hidden="true" />}
              {editingAsset ? "编辑图片" : "创造新图像"}
            </CardTitle>
            <CardDescription>
              {editingAsset ? "编辑会生成一张新资产，不会覆盖原图。" : "描述画面，Imagenia 会把任务加入本地队列。"}
            </CardDescription>
          </div>
          {editingAsset ? (
            <Button type="button" variant="ghost" size="sm" onClick={onCancelEdit}>
              取消编辑
            </Button>
          ) : null}
        </div>
        {editingAsset ? (
          <div className="mt-2 flex items-center gap-3 rounded-lg border bg-muted/50 p-2.5">
            <img className="size-12 rounded-md object-cover" src={editingAsset.imageUrl} alt="当前编辑来源" />
            <div className="min-w-0">
              <p className="text-xs font-medium">来源图片</p>
              <p className="truncate text-xs text-muted-foreground">{editingAsset.prompt}</p>
            </div>
          </div>
        ) : null}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} noValidate>
          <FieldGroup>
            <Field data-invalid={Boolean(error)}>
              <FieldLabel htmlFor="imagenia-prompt">画面描述</FieldLabel>
              <Textarea
                id="imagenia-prompt"
                aria-invalid={Boolean(error)}
                value={prompt}
                disabled={!configured || isSubmitting}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="例如：雨后的上海弄堂，暖色窗光，电影感，35mm 胶片质感……"
                className="min-h-32 resize-none"
              />
              <FieldDescription>提示词会作为资产信息保存在本机，但不会写入普通运行日志。</FieldDescription>
              {error ? <FieldError>{error}</FieldError> : null}
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field>
                <FieldLabel htmlFor="imagenia-size">画幅</FieldLabel>
                <Select value={size} onValueChange={(value) => setSize(value as ImageSize)} disabled={!configured || isSubmitting}>
                  <SelectTrigger id="imagenia-size" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="square">方形 · 1:1</SelectItem>
                    <SelectItem value="landscape">横向 · 3:2</SelectItem>
                    <SelectItem value="portrait">竖向 · 2:3</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="imagenia-quality">质量</FieldLabel>
                <Select value={quality} onValueChange={(value) => setQuality(value as ImageQuality)} disabled={!configured || isSubmitting}>
                  <SelectTrigger id="imagenia-quality" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard">标准</SelectItem>
                    <SelectItem value="high">高质量</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <Button type="submit" size="lg" disabled={!configured || isSubmitting} className="w-full">
              {isSubmitting ? <Spinner aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
              {isSubmitting ? "正在加入队列…" : editingAsset ? "生成编辑版本" : "开始生成"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
