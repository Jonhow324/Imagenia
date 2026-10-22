import * as React from "react"
import { PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { deleteService, getServices, saveService, setDefaultService, testServiceConnection,
  type CatalogStatus, type ImageService, type ServiceInput, type ServiceModel } from "@/services/settings"

const blankModel = (): ServiceModel => ({ name: "", sizes: ["square", "landscape", "portrait"], qualities: ["standard", "high"], supports_edit: false })
const blankService = (): ServiceInput => ({ name: "", base_url: "https://api.openai.com/v1", enabled: true, models: [blankModel()] })

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  status: CatalogStatus | null
  onSaved: (status: CatalogStatus) => void
}

export function SettingsSheet({ open, onOpenChange, status, onSaved }: Props) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [draft, setDraft] = React.useState<ServiceInput>(blankService)
  const [key, setKey] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState("")
  const [confirmDelete, setConfirmDelete] = React.useState(false)
  const current = status?.services.find(item => item.id === selectedId)
  const readOnly = current?.read_only ?? false
  const locked = readOnly || Boolean(current?.active_jobs)

  function choose(service?: ImageService) {
    setSelectedId(service?.id ?? null)
    setDraft(service ? { name: service.name, base_url: service.base_url, enabled: service.enabled,
      models: service.models.map(model => ({ ...model, sizes: [...model.sizes], qualities: [...model.qualities] })) } : blankService())
    setKey("")
    setError("")
  }

  React.useEffect(() => {
    if (!open) { setKey(""); setError(""); return }
    let active = true
    getServices().then(next => {
      if (!active) return
      onSaved(next)
      choose(next.services.find(item => item.id === next.default?.service_id) ?? next.services[0])
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "读取配置失败。") })
    return () => { active = false }
    // Refresh active-job locks each time the settings are opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  async function perform(action: () => Promise<CatalogStatus | void>) {
    setBusy(true)
    setError("")
    try {
      const next = await action()
      if (next) onSaved(next)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败，请稍后重试。")
    } finally { setBusy(false) }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!draft.name.trim() || draft.models.some(model => !model.name.trim() || !model.sizes.length || !model.qualities.length)) {
      setError("请输入服务和模型名称，每个模型至少选择一种画幅和质量。")
      return
    }
    await perform(async () => {
      const next = await saveService({ ...draft, name: draft.name.trim(), base_url: draft.base_url.trim(),
        models: draft.models.map(model => ({ ...model, name: model.name.trim() })),
        ...(key.trim() ? { api_key: key.trim() } : {}) }, selectedId ?? undefined)
      const saved = next.services.find(item => item.id === selectedId) ?? next.services.at(-1)
      choose(saved)
      toast.success("图像服务已保存")
      return next
    })
  }

  function updateModel(index: number, change: Partial<ServiceModel>) {
    setDraft(value => ({ ...value, models: value.models.map((model, at) => at === index ? { ...model, ...change } : model) }))
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>图像服务配置</SheetTitle>
          <SheetDescription>管理 OpenAI Images 兼容接口。密钥由后端私有保存，不会回显。</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 px-4 pb-6">
          <div className="flex flex-wrap gap-2" aria-label="已配置的服务">
            {status?.services.map(service => (
              <Button key={service.id} type="button" variant={selectedId === service.id ? "default" : "outline"}
                disabled={busy} onClick={() => choose(service)}>
                {service.name}{!service.enabled ? " · 已停用" : ""}{service.read_only ? " · 只读" : ""}
              </Button>
            ))}
            <Button type="button" variant="outline" disabled={busy} onClick={() => choose()}>
              <PlusIcon data-icon="inline-start" />新增服务
            </Button>
          </div>
          {current?.active_jobs ? <Alert><AlertDescription>此服务有 {current.active_jobs} 个未完成任务。地址、密钥、已有模型名称及删除操作暂时锁定；可停用以阻止新任务。</AlertDescription></Alert> : null}
          {readOnly ? <Alert><AlertDescription>此配置来自环境变量，请在容器部署配置中修改。可以新增其他服务并将其设为默认。</AlertDescription></Alert> : null}
          {error ? <FieldError role="alert">{error}</FieldError> : null}
          <form onSubmit={save} className="flex flex-col gap-4">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="service-name">服务名称</FieldLabel>
                <Input id="service-name" value={draft.name} disabled={busy || readOnly} maxLength={100}
                  onChange={event => setDraft({ ...draft, name: event.target.value })} placeholder="例如：我的图像服务" required />
              </Field>
              <Field>
                <FieldLabel htmlFor="service-url">API 根地址</FieldLabel>
                <Input id="service-url" type="url" value={draft.base_url} disabled={busy || locked}
                  onChange={event => setDraft({ ...draft, base_url: event.target.value })} required />
                <FieldDescription>不含 /images/generations；接口需支持当前使用的生成与编辑协议。</FieldDescription>
              </Field>
              <Field>
                <FieldLabel htmlFor="service-key">API Key</FieldLabel>
                <Input id="service-key" type="password" autoComplete="off" spellCheck={false} value={key}
                  onChange={event => setKey(event.target.value)} disabled={busy || locked}
                  placeholder={current?.configured ? "已配置；留空保留原密钥" : "输入此服务的密钥"} required={!selectedId} />
              </Field>
              <Field>
                <FieldLabel>服务状态</FieldLabel>
                <Button type="button" variant="outline" aria-pressed={draft.enabled} disabled={busy || readOnly}
                  onClick={() => setDraft({ ...draft, enabled: !draft.enabled })}>{draft.enabled ? "已启用 · 点击停用" : "已停用 · 点击启用"}</Button>
              </Field>
            </FieldGroup>
            {draft.models.map((model, index) => {
              const modelLocked = locked && Boolean(model.id)
              const isDefault = selectedId === status?.default?.service_id && model.id === status?.default?.model_id
              return <Card key={model.id ?? `new-${index}`}>
                <CardContent className="flex flex-col gap-4 pt-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">模型 {index + 1}</span>
                    {isDefault ? <Badge variant="secondary">全局默认</Badge> : null}
                    <Button type="button" variant="ghost" size="sm" disabled={busy || readOnly || modelLocked || draft.models.length === 1}
                      onClick={() => setDraft({ ...draft, models: draft.models.filter((_, at) => at !== index) })}>
                      <Trash2Icon data-icon="inline-start" />移除
                    </Button>
                  </div>
                  <FieldGroup>
                    <Field>
                      <FieldLabel htmlFor={`model-name-${index}`}>模型名称</FieldLabel>
                      <Input id={`model-name-${index}`} value={model.name} disabled={busy || readOnly || modelLocked}
                        onChange={event => updateModel(index, { name: event.target.value })} placeholder="接口接受的模型 ID" required />
                    </Field>
                    <Field>
                      <FieldLabel>支持的画幅</FieldLabel>
                      <ToggleGroup type="multiple" value={model.sizes} disabled={busy || readOnly}
                        onValueChange={values => updateModel(index, { sizes: values as ServiceModel["sizes"] })}>
                        <ToggleGroupItem value="square" aria-label="支持方形">方形</ToggleGroupItem>
                        <ToggleGroupItem value="landscape" aria-label="支持横图">横图</ToggleGroupItem>
                        <ToggleGroupItem value="portrait" aria-label="支持竖图">竖图</ToggleGroupItem>
                      </ToggleGroup>
                    </Field>
                    <Field>
                      <FieldLabel>支持的质量</FieldLabel>
                      <ToggleGroup type="multiple" value={model.qualities} disabled={busy || readOnly}
                        onValueChange={values => updateModel(index, { qualities: values as ServiceModel["qualities"] })}>
                        <ToggleGroupItem value="standard" aria-label="支持标准质量">标准</ToggleGroupItem>
                        <ToggleGroupItem value="high" aria-label="支持高质量">高质量</ToggleGroupItem>
                      </ToggleGroup>
                    </Field>
                    <Field>
                      <FieldLabel>图片编辑</FieldLabel>
                      <Button type="button" variant="outline" aria-pressed={model.supports_edit} disabled={busy || readOnly}
                        onClick={() => updateModel(index, { supports_edit: !model.supports_edit })}>
                        {model.supports_edit ? "支持编辑 · 点击关闭" : "未启用编辑 · 点击开启"}
                      </Button>
                    </Field>
                  </FieldGroup>
                  {model.id && selectedId ? <Button type="button" variant="outline" size="sm"
                    disabled={busy || isDefault || !current?.enabled || !current.configured}
                    onClick={() => perform(async () => {
                      const next = await setDefaultService({ service_id: selectedId, model_id: model.id! })
                      toast.success("默认服务和模型已更新")
                      return next
                    })}>设为全局默认</Button> : null}
                </CardContent>
              </Card>
            })}
            <Button type="button" variant="outline" disabled={busy || readOnly || draft.models.length >= 50}
              onClick={() => setDraft({ ...draft, models: [...draft.models, blankModel()] })}><PlusIcon data-icon="inline-start" />添加模型</Button>
            {!readOnly ? <Button type="submit" disabled={busy}>{busy ? "处理中…" : "保存服务"}</Button> : null}
          </form>
          {selectedId ? <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={busy || !current?.configured}
              onClick={() => perform(async () => {
                await testServiceConnection(selectedId)
                toast.success("已保存的配置认证通过", { description: "仅做只读请求，未验证生图或编辑能力，未消耗生图额度。" })
              })}>测试已保存的连接</Button>
            <Button type="button" variant="destructive" disabled={busy || readOnly || Boolean(current?.active_jobs)} onClick={() => setConfirmDelete(true)}>删除服务</Button>
          </div> : null}
          <p className="text-xs text-muted-foreground">支持能力由你声明。测试连接只检查认证；实际生成和编辑能力以显式任务为准。</p>
        </div>
        <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
          <AlertDialogContent>
            <AlertDialogHeader><AlertDialogTitle>删除此图像服务？</AlertDialogTitle>
              <AlertDialogDescription>将删除服务的连接配置和密钥。历史图片、收藏、任务及来源名称会保留。</AlertDialogDescription></AlertDialogHeader>
            <AlertDialogFooter><AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction onClick={() => perform(async () => {
                const next = await deleteService(selectedId!)
                choose()
                toast.success("服务已删除，历史资产保留")
                return next
              })}>确认删除</AlertDialogAction></AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SheetContent>
    </Sheet>
  )
}
