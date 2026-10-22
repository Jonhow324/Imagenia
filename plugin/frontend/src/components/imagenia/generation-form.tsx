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

export function GenerationForm({
  configured,
  catalog,
  retryInput,
  editingAsset,
  isSubmitting,
  onCancelEdit,
  onSubmit,
}: {
  configured: boolean
  catalog: CatalogStatus | null
  retryInput: GenerateInput | null
  editingAsset: ImageAsset | null
  isSubmitting: boolean
  onCancelEdit: () => void
  onSubmit: (input: GenerateInput) => void
}) {
  const [selection, setSelection] = React.useState<ServiceSelection | null>(null)
  const initialized = React.useRef(false)
  const chosen = selectedServiceModel(catalog, selection, Boolean(editingAsset))
  const [prompt, setPrompt] = React.useState("")
  const [size, setSize] = React.useState<ImageSize>("square")
  const [quality, setQuality] = React.useState<ImageQuality>("standard")
  const [error, setError] = React.useState("")
  const validOptions = Boolean(chosen.model?.sizes.includes(size) && chosen.model.qualities.includes(quality))

  React.useEffect(() => {
    if (catalog && (!initialized.current || (selection === null && catalog.default !== null))) {
      initialized.current = true
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

  React.useEffect(() => {
    if (!retryInput) return
    setPrompt(retryInput.prompt)
    setSize(retryInput.size)
    setQuality(retryInput.quality)
    const next = { service_id: retryInput.serviceId ?? "", model_id: retryInput.modelId ?? "" }
    setSelection(next)
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
    setError("")
    onSubmit({ prompt: normalized, size, quality, serviceId: selection.service_id, modelId: selection.model_id, sourceAssetId: editingAsset?.id })
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

            <Button type="submit" size="lg" disabled={!configured || !chosen.valid || !validOptions || isSubmitting} className="w-full">
              {isSubmitting ? <Spinner aria-hidden="true" /> : <SparklesIcon aria-hidden="true" />}
              {isSubmitting ? "正在加入队列…" : editingAsset ? "生成编辑版本" : "开始生成"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
