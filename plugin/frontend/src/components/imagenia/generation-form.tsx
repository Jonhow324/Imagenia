import * as React from "react"
import { ImagePlusIcon, SparklesIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { initialServiceSelection, rememberServiceSelection, selectedServiceModel } from "@/services/service-selection"
import type { CatalogStatus, ServiceSelection } from "@/services/settings"
import type { GenerateInput, ImageAsset, ImageQuality, ImageSize } from "@/mocks/imagenia-service"

export interface GenerationDraft {
  prompt: string
  size: ImageSize
  quality: ImageQuality
  selection: ServiceSelection | null
  sourceAssetId?: string
  restoredInput?: GenerateInput | null
}

export function createGenerationDraft(): GenerationDraft {
  return { prompt: "", size: "square", quality: "standard", selection: null }
}

export function GenerationForm({
  configured,
  draft,
  onDraftChange,
  catalog,
  retryInput,
  editingAsset,
  isSubmitting,
  onCancelEdit,
  onSubmit,
}: {
  configured: boolean
  draft: GenerationDraft
  onDraftChange: React.Dispatch<React.SetStateAction<GenerationDraft>>
  catalog: CatalogStatus | null
  retryInput: GenerateInput | null
  editingAsset: ImageAsset | null
  isSubmitting: boolean
  onCancelEdit: () => void
  onSubmit: (input: GenerateInput) => void
}) {
  const { selection, prompt, size, quality } = draft
  const setSelection = (selection: ServiceSelection | null) => onDraftChange(value => ({ ...value, selection }))
  const setPrompt = (prompt: string) => onDraftChange(value => ({ ...value, prompt }))
  const setSize = (size: ImageSize) => onDraftChange(value => ({ ...value, size }))
  const setQuality = (quality: ImageQuality) => onDraftChange(value => ({ ...value, quality }))
  const chosen = selectedServiceModel(catalog, selection, Boolean(editingAsset))
  const [error, setError] = React.useState("")
  const validOptions = Boolean(chosen.model?.sizes.includes(size) && chosen.model.qualities.includes(quality))

  React.useEffect(() => {
    if (catalog && selection === null) {
      const initial = initialServiceSelection(catalog)
      setSelection(initial)
      const target = selectedServiceModel(catalog, initial, false).model
      if (target) { setSize(target.sizes[0]); setQuality(target.qualities[0]) }
    }
  }, [catalog])

  function choose(next: ServiceSelection) {
    setSelection(next)
    rememberServiceSelection(next)
    const target = selectedServiceModel(catalog, next, Boolean(editingAsset)).model
    if (target) {
      if (!target.sizes.includes(size)) setSize(target.sizes[0])
      if (!target.qualities.includes(quality)) setQuality(target.qualities[0])
    }
    setError("")
  }

  React.useEffect(() => {
    if (!editingAsset || draft.sourceAssetId === editingAsset.id) return
    const model = selectedServiceModel(catalog, selection, true).model
    const preferredQuality = editingAsset.quality ?? "standard"
    onDraftChange(value => ({ ...value, sourceAssetId: editingAsset.id,
      prompt: `以这张图片为基础，${editingAsset.prompt}`,
      size: model?.sizes.includes(editingAsset.size) ? editingAsset.size : model?.sizes[0] ?? editingAsset.size,
      quality: model?.qualities.includes(preferredQuality) ? preferredQuality : model?.qualities[0] ?? "standard" }))
    setError("")
  }, [editingAsset])

  React.useEffect(() => {
    if (!retryInput || draft.restoredInput === retryInput) return
    onDraftChange(value => ({ ...value, prompt: retryInput.prompt, size: retryInput.size,
      quality: retryInput.quality, restoredInput: retryInput,
      selection: { service_id: retryInput.serviceId ?? "", model_id: retryInput.modelId ?? "" } }))
    setError("")
  }, [retryInput])

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selection || !chosen.valid || !validOptions) {
      setError("请确认服务、模型、画幅和质量后再提交。")
      return
    }
    rememberServiceSelection(selection)
    const normalized = prompt.trim()
    if (normalized.length < 8) {
      setError("请至少输入 8 个字符，让画面意图更清楚。")
      return
    }
    if (normalized.length > 4000) {
      setError("提示词不能超过 4000 个字符。")
      return
    }
    setError("")
    onSubmit({ prompt: normalized, size, quality, serviceId: selection.service_id, modelId: selection.model_id, sourceAssetId: editingAsset?.id })
  }

  return (
    <Card size="sm" className="min-h-0 flex-1 border-0 bg-card/95 shadow-sm ring-1 ring-foreground/10">
      <CardHeader className="shrink-0 border-b">
        <div className="flex items-start justify-between gap-3">
          <div className="grid gap-1">
            <CardTitle className="flex items-center gap-2">
              {editingAsset ? <ImagePlusIcon className="size-4" aria-hidden="true" /> : <SparklesIcon className="size-4" aria-hidden="true" />}
              {editingAsset ? "编辑图片" : "创造新图像"}
            </CardTitle>
            <CardDescription className="text-xs">
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
            <img className="size-9 shrink-0 rounded-md object-cover" src={editingAsset.imageUrl} alt="当前编辑来源" />
            <div className="min-w-0">
              <p className="m-0 text-xs font-medium">来源图片</p>
              <p className="m-0 truncate text-xs text-muted-foreground">{editingAsset.prompt}</p>
            </div>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col" noValidate>
          <FieldGroup className="min-h-0 flex-1 gap-3">
            <div className="grid shrink-0 grid-cols-2 gap-3">
            <Field>
              <FieldLabel htmlFor="imagenia-service">图像服务</FieldLabel>
              <Select value={chosen.service?.id ?? ""} disabled={isSubmitting}
                onValueChange={serviceId => {
                  const target = catalog?.services.find(service => service.id === serviceId)
                  const model = target?.models.find(item => !editingAsset || item.supports_edit)
                  if (model) choose({ service_id: serviceId, model_id: model.id })
                }}>
                <SelectTrigger id="imagenia-service" className="w-full"><SelectValue placeholder="请选择服务" /></SelectTrigger>
                <SelectContent><SelectGroup>
                  {catalog?.services.filter(service => service.enabled && service.configured &&
                    service.models.some(model => !editingAsset || model.supports_edit)).map(service =>
                    <SelectItem key={service.id} value={service.id}>{service.name}</SelectItem>)}
                </SelectGroup></SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="imagenia-model">模型</FieldLabel>
              <Select value={chosen.model?.id ?? ""} disabled={isSubmitting || !chosen.service?.enabled}
                onValueChange={modelId => {
                  // Ignore the hidden form control's empty event while options are replaced.
                  if (chosen.service?.models.some(model => model.id === modelId && (!editingAsset || model.supports_edit))) {
                    choose({ service_id: chosen.service.id, model_id: modelId })
                  }
                }}>
                <SelectTrigger id="imagenia-model" className="w-full"><SelectValue placeholder="请选择模型" /></SelectTrigger>
                <SelectContent><SelectGroup>
                  {chosen.service?.models.filter(model => !editingAsset || model.supports_edit).map(model =>
                    <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>)}
                </SelectGroup></SelectContent>
              </Select>
              {!chosen.valid && configured ? <FieldError>所选服务或模型不可用，或未启用编辑能力。请重新选择；不会自动切换服务。</FieldError> : null}
              {chosen.valid && !validOptions ? <FieldError>此模型不支持当前画幅或质量，请重新选择参数。</FieldError> : null}
            </Field>
            </div>
            <Field className="min-h-0 flex-1" data-invalid={Boolean(error)}>
              <FieldLabel htmlFor="imagenia-prompt">画面描述</FieldLabel>
              <Textarea
                id="imagenia-prompt"
                aria-invalid={Boolean(error)}
                value={prompt}
                disabled={!configured || isSubmitting}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="例如：雨后的上海弄堂，暖色窗光，电影感，35mm 胶片质感……"
                className="min-h-16 flex-1 resize-none"
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault()
                    event.currentTarget.form?.requestSubmit()
                  }
                }}
              />
              <div className="flex items-start justify-between gap-3">
                <FieldDescription className="m-0 text-xs">提示词保存在本机，不写入运行日志。Ctrl 或 ⌘ 与 Enter 可提交。</FieldDescription>
                <span className={`shrink-0 text-xs tabular-nums ${prompt.length > 4000 ? "text-destructive" : "text-muted-foreground"}`}>{prompt.length}/4000</span>
              </div>
              {error ? <FieldError>{error}</FieldError> : null}
            </Field>

            <div className="grid shrink-0 grid-cols-2 gap-3">
              <Field>
                <FieldLabel htmlFor="imagenia-size">画幅</FieldLabel>
                <Select value={size} onValueChange={value => { if (chosen.model?.sizes.includes(value as ImageSize)) setSize(value as ImageSize) }} disabled={!configured || isSubmitting}>
                  <SelectTrigger id="imagenia-size" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>{chosen.model?.sizes.map(value => <SelectItem key={value} value={value}>
                      {{ square: "方形 · 1:1", landscape: "横向 · 3:2", portrait: "竖向 · 2:3" }[value]}
                    </SelectItem>)}</SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="imagenia-quality">质量</FieldLabel>
                <Select value={quality} onValueChange={value => { if (chosen.model?.qualities.includes(value as ImageQuality)) setQuality(value as ImageQuality) }} disabled={!configured || isSubmitting}>
                  <SelectTrigger id="imagenia-quality" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>{chosen.model?.qualities.map(value => <SelectItem key={value} value={value}>
                      {value === "standard" ? "标准" : "高质量"}
                    </SelectItem>)}</SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </div>

            <Button type="submit" size="lg" disabled={!configured || !chosen.valid || !validOptions || isSubmitting} className="w-full shrink-0">
              {isSubmitting ? <Spinner aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
              {isSubmitting ? "正在加入队列…" : editingAsset ? "生成编辑版本" : "开始生成"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
