import * as React from "react"
import { CheckCircle2Icon, KeyRoundIcon } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Spinner } from "@/components/ui/spinner"
import { saveKey, testConnection, type SettingsStatus } from "@/services/settings"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  status: SettingsStatus | null
  onSaved: (status: SettingsStatus) => void
}

export function SettingsSheet({ open, onOpenChange, status, onSaved }: Props) {
  const [key, setKey] = React.useState("")
  const [busy, setBusy] = React.useState<"save" | "test" | null>(null)
  const [error, setError] = React.useState("")
  const configured = status?.openai.configured ?? false

  function changeOpen(next: boolean) {
    if (!next) {
      setKey("")
      setError("")
    }
    onOpenChange(next)
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!key.trim()) {
      setError("请输入 API Key。")
      return
    }
    setBusy("save")
    setError("")
    try {
      const next = await saveKey(key.trim())
      onSaved(next)
      setKey("")
      toast.success(next.openai.source === "environment" ? "密钥已保存；当前仍优先使用环境变量" : "API Key 已保存")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "保存失败，请稍后重试。")
    } finally {
      setBusy(null)
    }
  }

  async function test() {
    setBusy("test")
    setError("")
    try {
      await testConnection()
      toast.success("连接测试通过", { description: "只执行只读认证请求，未发起图像生成。" })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "连接测试失败，请稍后重试。")
    } finally {
      setBusy(null)
    }
  }

  return (
    <Sheet open={open} onOpenChange={changeOpen}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>图像服务配置</SheetTitle>
          <SheetDescription>API Key 由插件后端保存；页面不会回显密钥。</SheetDescription>
        </SheetHeader>
        <form onSubmit={save} className="flex flex-col gap-5 px-4">
          <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-4">
            <div className="grid size-10 place-items-center rounded-lg bg-background ring-1 ring-foreground/10">
              {configured ? <CheckCircle2Icon className="size-5 text-emerald-600" aria-hidden="true" /> : <KeyRoundIcon className="size-5 text-amber-600" aria-hidden="true" />}
            </div>
            <div>
              <p className="text-sm font-medium">{configured ? "OpenAI 已配置" : "尚未配置 API Key"}</p>
              <p className="text-xs text-muted-foreground">
                {status?.openai.source === "environment" ? "来自环境变量（优先于保存的配置）" : status?.openai.source === "file" ? "来自插件私有配置" : "生成和编辑功能当前不可用"}
              </p>
            </div>
          </div>
          <FieldGroup>
            <Field data-invalid={Boolean(error)}>
              <FieldLabel htmlFor="imagenia-api-key">OpenAI API Key</FieldLabel>
              <Input id="imagenia-api-key" type="password" autoComplete="off" spellCheck={false} value={key} onChange={(event) => setKey(event.target.value)} aria-invalid={Boolean(error)} disabled={busy !== null} placeholder="输入新密钥以保存或覆盖" />
              <FieldDescription>密钥存于插件数据目录的私有文件中（0600）；环境变量优先。</FieldDescription>
              {error ? <FieldError role="alert">{error}</FieldError> : null}
            </Field>
          </FieldGroup>
          <div className="rounded-xl border p-4">
            <p className="text-sm font-medium">默认模型</p>
            <p className="mt-1 text-sm text-muted-foreground">gpt-image-1 · 由后端配置，前端不可自由修改</p>
          </div>
          <Separator />
          <p className="text-xs leading-5 text-muted-foreground">“测试连接”只检查 OpenAI 认证，不会执行可能收费的完整生图请求。</p>
          <SheetFooter className="px-0">
            <Button type="submit" disabled={busy !== null || !key.trim()}>
              {busy === "save" ? <Spinner aria-hidden="true" /> : null}
              保存 API Key
            </Button>
            <Button type="button" variant="secondary" disabled={!configured || busy !== null} onClick={test}>
              {busy === "test" ? <Spinner aria-hidden="true" /> : null}
              测试连接
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
